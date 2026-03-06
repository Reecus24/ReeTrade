"""
Reinforcement Learning Trading AI
==================================
Echte lernende KI die:
- Marktdaten analysiert
- Trades ausprobiert
- Aus Ergebnissen lernt
- Strategie kontinuierlich verbessert
"""

import logging
import numpy as np
import pickle
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import json

logger = logging.getLogger(__name__)

# ============ MARKET STATE (Was die KI "sieht") ============

@dataclass
class MarketState:
    """Alles was die KI über den Markt weiß"""
    
    # Preis-Daten
    current_price: float = 0
    price_change_1h: float = 0  # % Änderung letzte Stunde
    price_change_4h: float = 0  # % Änderung letzte 4 Stunden
    price_change_24h: float = 0  # % Änderung letzte 24 Stunden
    
    # Kerzen-Muster
    last_candle_body: float = 0  # Positiv = grün, Negativ = rot
    last_candle_wick_ratio: float = 0  # Docht-Verhältnis
    consecutive_green: int = 0
    consecutive_red: int = 0
    
    # Technische Indikatoren
    rsi: float = 50
    rsi_trend: float = 0  # Steigend/Fallend
    macd_histogram: float = 0
    macd_signal: float = 0  # Über/Unter Signal-Linie
    
    # Volumen
    volume_ratio: float = 1.0  # Aktuell vs Durchschnitt
    volume_trend: float = 0  # Steigend/Fallend
    
    # Trend-Indikatoren
    ema_20_distance: float = 0  # Preis-Abstand zu EMA20 in %
    ema_50_distance: float = 0
    ema_cross: int = 0  # 1 = Golden Cross, -1 = Death Cross, 0 = Nichts
    adx: float = 25  # Trend-Stärke
    
    # Position-Kontext (wenn Trade offen)
    has_position: bool = False
    position_pnl_pct: float = 0
    position_hold_hours: float = 0
    distance_to_stop_loss: float = 0
    distance_to_take_profit: float = 0
    
    # ============ PHASE 2: ORDERBOOK & MICROSTRUCTURE ============
    # Spread & Mid Price
    spread_pct: float = 0  # Bid-Ask Spread in %
    mid_price: float = 0  # (best_bid + best_ask) / 2
    
    # Orderbook Imbalance
    orderbook_imbalance: float = 1.0  # bid_vol / ask_vol (>1 = buying pressure)
    bid_volume_sum: float = 0  # Sum of top 5 bid volumes
    ask_volume_sum: float = 0  # Sum of top 5 ask volumes
    
    # Microtrend Returns (für 10-Min Trading kritisch!)
    return_30s: float = 0  # Price change last 30 seconds
    return_60s: float = 0  # Price change last 60 seconds
    return_180s: float = 0  # Price change last 180 seconds
    
    # Volatility (realized)
    volatility_1m: float = 0  # 1-minute realized volatility
    
    def to_array(self) -> np.ndarray:
        """Konvertiere zu Feature-Array für KI (32 Features)"""
        return np.array([
            # Original features (22)
            self.price_change_1h,
            self.price_change_4h,
            self.price_change_24h,
            self.last_candle_body,
            self.last_candle_wick_ratio,
            self.consecutive_green,
            self.consecutive_red,
            self.rsi / 100,  # Normalisiert auf 0-1
            self.rsi_trend,
            self.macd_histogram,
            self.macd_signal,
            self.volume_ratio,
            self.volume_trend,
            self.ema_20_distance / 10,  # Normalisiert
            self.ema_50_distance / 10,
            self.ema_cross,
            self.adx / 100,
            int(self.has_position),
            self.position_pnl_pct / 10,
            self.position_hold_hours / 24,
            self.distance_to_stop_loss / 10,
            self.distance_to_take_profit / 10,
            # NEW: Orderbook & Microstructure (10 features)
            self.spread_pct * 10,  # Spread normalized (0.1% -> 1.0)
            min(self.orderbook_imbalance, 5.0) / 5.0,  # Capped at 5, normalized
            self.return_30s * 100,  # Micro returns amplified
            self.return_60s * 100,
            self.return_180s * 100,
            min(self.bid_volume_sum, 1000000) / 1000000,  # Normalized
            min(self.ask_volume_sum, 1000000) / 1000000,
            self.volatility_1m * 100,  # Volatility amplified
            0,  # Reserved for future use
            0   # Reserved for future use
        ], dtype=np.float32)
    
    @staticmethod
    def state_size() -> int:
        return 32  # Increased from 22 to 32


# ============ ACTIONS (Was die KI tun kann) ============

class Action:
    HOLD = 0      # Nichts tun
    BUY = 1       # Kaufen
    SELL = 2      # Verkaufen
    
    @staticmethod
    def to_string(action: int) -> str:
        return {0: "HOLD", 1: "BUY", 2: "SELL"}.get(action, "UNKNOWN")


# ============ EXPERIENCE REPLAY (Gedächtnis der KI) ============

@dataclass
class Experience:
    """Eine Erfahrung die die KI gemacht hat"""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool  # Episode beendet (Trade geschlossen)


class PrioritizedReplayMemory:
    """
    Prioritized Experience Replay (PER)
    
    Erfahrungen mit höherem TD-Error werden häufiger gesamplet.
    Dies beschleunigt das Lernen signifikant.
    
    priority_i = |TD_error_i| + epsilon
    P(i) = priority_i^alpha / sum(priority_j^alpha)
    
    Optional: Importance Sampling weights w_i = (N * P(i))^(-beta)
    """
    
    def __init__(
        self, 
        capacity: int = 10000,
        alpha: float = 0.6,  # Prioritization exponent (0 = uniform, 1 = full prioritization)
        beta_start: float = 0.4,  # Importance sampling start (anneals to 1.0)
        beta_frames: int = 10000,  # Frames to anneal beta
        epsilon: float = 0.01  # Small constant to avoid zero priority
    ):
        self.capacity = capacity
        self.alpha = alpha
        self.beta_start = beta_start
        self.beta_frames = beta_frames
        self.epsilon = epsilon
        
        # Storage
        self.buffer: List[Experience] = []
        self.priorities: np.ndarray = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        self.frame = 0
        
        # Track max priority for new experiences
        self.max_priority = 1.0
    
    @property
    def beta(self) -> float:
        """Current beta value (anneals from beta_start to 1.0)"""
        return min(1.0, self.beta_start + (1.0 - self.beta_start) * self.frame / self.beta_frames)
    
    def push(self, experience: Experience):
        """Add experience with max priority (so it gets sampled at least once)"""
        if len(self.buffer) < self.capacity:
            self.buffer.append(experience)
        else:
            self.buffer[self.position] = experience
        
        # New experiences get max priority
        self.priorities[self.position] = self.max_priority
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size: int) -> tuple:
        """
        Sample batch with prioritization
        
        Returns:
            (experiences, indices, weights)
        """
        self.frame += 1
        
        if len(self.buffer) == 0:
            return [], [], []
        
        n = len(self.buffer)
        batch_size = min(batch_size, n)
        
        # Calculate sampling probabilities
        priorities = self.priorities[:n]
        probs = priorities ** self.alpha
        probs_sum = probs.sum()
        
        if probs_sum == 0:
            probs = np.ones(n) / n
        else:
            probs = probs / probs_sum
        
        # Sample indices based on priority
        try:
            indices = np.random.choice(n, batch_size, p=probs, replace=False)
        except ValueError:
            # Fallback to uniform if probabilities are invalid
            indices = np.random.choice(n, batch_size, replace=False)
        
        # Calculate importance sampling weights
        # w_i = (N * P(i))^(-beta)
        weights = (n * probs[indices]) ** (-self.beta)
        weights = weights / weights.max()  # Normalize
        
        experiences = [self.buffer[i] for i in indices]
        
        return experiences, indices, weights
    
    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """
        Update priorities based on TD errors
        
        priority = |td_error| + epsilon
        """
        for idx, td_error in zip(indices, td_errors):
            priority = abs(td_error) + self.epsilon
            self.priorities[idx] = priority
            self.max_priority = max(self.max_priority, priority)
    
    def __len__(self) -> int:
        return len(self.buffer)


# Legacy alias for backwards compatibility
class ReplayMemory(PrioritizedReplayMemory):
    """Alias für PrioritizedReplayMemory (backwards compatible)"""
    pass


# ============ Q-LEARNING KI (Das "Gehirn") ============

class QLearningBrain:
    """
    Q-Learning basierte Trading-KI
    
    Q(state, action) = Erwarteter zukünftiger Gewinn
    
    Die KI lernt welche Aktionen in welchen Marktsituationen
    zu Gewinn führen.
    """
    
    def __init__(
        self,
        state_size: int = MarketState.state_size(),
        action_size: int = 3,  # HOLD, BUY, SELL
        learning_rate: float = 0.001,
        gamma: float = 0.95,  # Discount für zukünftige Rewards
        epsilon_start: float = 1.0,  # Start-Exploration
        epsilon_end: float = 0.05,  # End-Exploration (5% minimum)
        epsilon_decay: float = 0.995  # Schnellerer Decay für effizienteres Lernen
    ):
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.gamma = gamma
        
        # Exploration vs Exploitation
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        
        # Q-Table (vereinfacht) oder Neural Network
        self._init_model()
        
        # Erfahrungs-Speicher
        self.memory = ReplayMemory(capacity=10000)
        
        # Statistiken
        self.total_trades = 0
        self.winning_trades = 0
        self.total_reward = 0
        self.training_episodes = 0
    
    def _init_model(self):
        """Initialisiere Q-Funktion (Neural Network)"""
        try:
            from sklearn.neural_network import MLPRegressor
            
            # Ein Netzwerk pro Action
            self.q_networks = {
                action: MLPRegressor(
                    hidden_layer_sizes=(64, 32),
                    activation='relu',
                    learning_rate_init=self.learning_rate,
                    max_iter=1,
                    warm_start=True,
                    random_state=42
                )
                for action in range(self.action_size)
            }
            
            # Initial fit mit Dummy-Daten
            dummy_X = np.zeros((1, self.state_size))
            dummy_y = np.array([0.0])
            for net in self.q_networks.values():
                net.fit(dummy_X, dummy_y)
            
            self.model_type = "neural_network"
            logger.info("RL Brain: Neural Network initialisiert")
            
        except ImportError:
            # Fallback: Simple Q-Table mit State-Discretization
            self.q_table = {}
            self.model_type = "q_table"
            logger.info("RL Brain: Q-Table initialisiert (sklearn nicht verfügbar)")
    
    def _discretize_state(self, state: np.ndarray) -> tuple:
        """Diskretisiere State für Q-Table"""
        # Runde auf 1 Dezimalstelle für Q-Table Lookup
        return tuple(np.round(state, 1))
    
    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Hole Q-Werte für alle Actions"""
        if self.model_type == "neural_network":
            state_2d = state.reshape(1, -1)
            return np.array([
                self.q_networks[a].predict(state_2d)[0]
                for a in range(self.action_size)
            ])
        else:
            # Q-Table
            key = self._discretize_state(state)
            if key not in self.q_table:
                self.q_table[key] = np.zeros(self.action_size)
            return self.q_table[key]
    
    def choose_action(self, state: np.ndarray, can_buy: bool = True, has_position: bool = False) -> int:
        """
        Wähle Action basierend auf aktuellem State
        
        Epsilon-Greedy: Manchmal explorieren, manchmal beste Action wählen
        """
        # Exploration: Zufällige Action
        if random.random() < self.epsilon:
            valid_actions = [Action.HOLD]
            if can_buy and not has_position:
                valid_actions.append(Action.BUY)
            if has_position:
                valid_actions.append(Action.SELL)
            return random.choice(valid_actions)
        
        # Exploitation: Beste bekannte Action
        q_values = self.get_q_values(state)
        
        # Maskiere ungültige Actions
        if has_position:
            q_values[Action.BUY] = float('-inf')  # Kann nicht kaufen wenn schon Position
        else:
            q_values[Action.SELL] = float('-inf')  # Kann nicht verkaufen ohne Position
        
        if not can_buy:
            q_values[Action.BUY] = float('-inf')
        
        return int(np.argmax(q_values))
    
    def learn(self, experience: Experience):
        """
        Lerne aus einer Erfahrung mit Prioritized Experience Replay (PER)
        
        - Neue Erfahrungen bekommen max priority
        - TD-Error bestimmt zukünftige Priorität
        - Importance sampling weights korrigieren Bias
        """
        self.memory.push(experience)
        
        # Batch-Learning wenn genug Erfahrungen
        if len(self.memory) < 32:
            return
        
        # Sample mit Priorisierung
        batch, indices, weights = self.memory.sample(32)
        
        if not batch:
            return
        
        td_errors = []
        
        for i, exp in enumerate(batch):
            # Q-Learning Update mit TD-Error
            current_q = self.get_q_values(exp.state)[exp.action]
            
            if exp.done:
                target_q = exp.reward
            else:
                next_q_values = self.get_q_values(exp.next_state)
                target_q = exp.reward + self.gamma * np.max(next_q_values)
            
            # TD-Error für Priority Update
            td_error = target_q - current_q
            td_errors.append(td_error)
            
            # Importance sampling weight (korrigiert Bias durch Priorisierung)
            weight = weights[i] if isinstance(weights, (list, np.ndarray)) and len(weights) > i else 1.0
            
            # Update Q-Funktion (weighted)
            if self.model_type == "neural_network":
                # Partial fit für Neural Network
                # Note: sklearn doesn't support sample weights in partial_fit, 
                # so we scale the target instead
                state_2d = exp.state.reshape(1, -1)
                weighted_target = current_q + weight * (target_q - current_q)
                self.q_networks[exp.action].partial_fit(state_2d, np.array([weighted_target]))
            else:
                # Q-Table Update
                key = self._discretize_state(exp.state)
                if key not in self.q_table:
                    self.q_table[key] = np.zeros(self.action_size)
                
                # Weighted Q-Learning Formula
                self.q_table[key][exp.action] += weight * self.learning_rate * td_error
        
        # ============ PER: UPDATE PRIORITIES ============
        if indices and td_errors:
            self.memory.update_priorities(np.array(indices), np.array(td_errors))
        
        # Decay Exploration
        old_epsilon = self.epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        self.training_episodes += 1
        
        # Log Lernfortschritt alle 10 Episoden
        if self.training_episodes % 10 == 0:
            avg_td_error = np.mean(np.abs(td_errors)) if td_errors else 0
            logger.info("[RL] 🎓 LERNFORTSCHRITT (PER):")
            logger.info(f"[RL]    → Episoden: {self.training_episodes}")
            logger.info(f"[RL]    → Exploration: {old_epsilon*100:.1f}% → {self.epsilon*100:.1f}%")
            logger.info(f"[RL]    → Avg TD-Error: {avg_td_error:.4f}")
            logger.info(f"[RL]    → Memory Beta: {self.memory.beta:.2f} (importance sampling)")
            logger.info(f"[RL]    → Die KI verlässt sich jetzt zu {(1-self.epsilon)*100:.1f}% auf gelerntes Wissen")
    
    def record_trade_result(self, reward: float, was_profitable: bool):
        """Zeichne Trade-Ergebnis auf"""
        self.total_trades += 1
        self.total_reward += reward
        if was_profitable:
            self.winning_trades += 1
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0
        return self.winning_trades / self.total_trades
    
    def get_status(self) -> Dict:
        return {
            "model_type": self.model_type,
            "epsilon": self.epsilon,
            "exploration_pct": self.epsilon * 100,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.win_rate,
            "total_reward": self.total_reward,
            "memory_size": len(self.memory),
            "training_episodes": self.training_episodes,
            "is_learning": self.epsilon > self.epsilon_end + 0.01
        }


# ============ TRADING AI (Haupt-Interface) ============

class RLTradingAI:
    """
    Reinforcement Learning Trading AI
    
    - Analysiert Marktdaten
    - Trifft Entscheidungen
    - Lernt aus Ergebnissen
    """
    
    MODEL_PATH = "/opt/reetrade/data/rl_brain.pkl"  # Persistent path
    
    def __init__(self, db=None):
        self.db = db
        self.brain = QLearningBrain()
        
        # Aktuelle Episode (offener Trade)
        self.current_episode: Dict[str, Dict] = {}  # {symbol: episode_data}
        
        # Lade gespeichertes Modell
        self._load_model()
    
    def _load_model(self):
        """Lade trainiertes Modell MIT Memory UND Neural Networks"""
        try:
            if os.path.exists(self.MODEL_PATH):
                with open(self.MODEL_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.brain.epsilon = data.get('epsilon', self.brain.epsilon)
                    self.brain.total_trades = data.get('total_trades', 0)
                    self.brain.winning_trades = data.get('winning_trades', 0)
                    self.brain.total_reward = data.get('total_reward', 0)
                    self.brain.training_episodes = data.get('training_episodes', 0)
                    
                    # Lade Q-Table wenn vorhanden
                    if 'q_table' in data and self.brain.model_type == 'q_table':
                        self.brain.q_table = data['q_table']
                        logger.info(f"[RL] Q-Table geladen mit {len(self.brain.q_table)} Einträgen")
                    
                    # KRITISCH: Lade Neural Networks (q_networks Dictionary)
                    if 'q_networks' in data and data['q_networks']:
                        self.brain.q_networks = data['q_networks']
                        self.brain.model_type = 'neural_network'
                        logger.info("[RL] ✅ Neural Networks (3 MLPs) geladen!")
                    
                    # WICHTIG: Memory laden!
                    if 'memory' in data and data['memory']:
                        for exp in data['memory']:
                            self.brain.memory.push(exp)
                        logger.info(f"[RL] Memory geladen: {len(data['memory'])} Erfahrungen")
                    
                    # Lade auch Priorities wenn vorhanden
                    if 'memory_priorities' in data and data['memory_priorities']:
                        for i, priority in enumerate(data['memory_priorities']):
                            if i < len(self.brain.memory):
                                self.brain.memory.priorities[i] = priority
                    
                    logger.info(f"[RL] ✅ Model geladen: {self.brain.total_trades} Trades, {self.brain.win_rate:.1%} Win-Rate, Memory: {len(self.brain.memory)}, Typ: {self.brain.model_type}")
            else:
                logger.info(f"[RL] Kein gespeichertes Model gefunden unter {self.MODEL_PATH} - starte neu")
        except Exception as e:
            logger.warning(f"[RL] ⚠️ Konnte Model nicht laden: {e} - starte neu")
    
    def _save_model(self):
        """Speichere Modell MIT Memory UND Neural Networks"""
        try:
            # Erstelle Ordner falls nicht vorhanden
            import os
            os.makedirs(os.path.dirname(self.MODEL_PATH), exist_ok=True)
            
            data = {
                'epsilon': self.brain.epsilon,
                'total_trades': self.brain.total_trades,
                'winning_trades': self.brain.winning_trades,
                'total_reward': self.brain.total_reward,
                'training_episodes': self.brain.training_episodes,
                'model_type': self.brain.model_type,
                # WICHTIG: Memory auch speichern!
                'memory': list(self.brain.memory.buffer) if hasattr(self.brain.memory, 'buffer') else [],
                'memory_priorities': list(self.brain.memory.priorities[:len(self.brain.memory)]) if hasattr(self.brain.memory, 'priorities') else [],
            }
            
            # Speichere Q-Table wenn vorhanden
            if self.brain.model_type == 'q_table':
                data['q_table'] = self.brain.q_table
            
            # KRITISCH: Speichere Neural Networks (q_networks Dictionary)
            if hasattr(self.brain, 'q_networks') and self.brain.q_networks:
                data['q_networks'] = self.brain.q_networks
                logger.info("[RL] Neural Networks (3 MLPs) werden gespeichert")
            
            with open(self.MODEL_PATH, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"[RL] ✅ Model gespeichert: {self.brain.total_trades} Trades, Memory: {len(self.brain.memory)}, Typ: {self.brain.model_type}")
        except Exception as e:
            logger.error(f"[RL] ❌ Konnte Model nicht speichern: {e}")
    
    async def analyze_market(self, symbol: str, klines: List, ticker: Dict, position=None) -> MarketState:
        """
        Analysiere Marktdaten und erstelle State
        
        Args:
            symbol: Trading-Paar
            klines: Kerzen-Daten
            ticker: 24h Ticker
            position: Aktuelle Position (falls vorhanden)
        """
        state = MarketState()
        
        try:
            if not klines or len(klines) < 50:
                return state
            
            # Aktuelle Preise
            closes = [float(k[4]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            opens = [float(k[1]) for k in klines]
            volumes = [float(k[5]) for k in klines]
            
            state.current_price = closes[-1]
            
            # Preis-Änderungen
            if len(closes) > 4:
                state.price_change_1h = (closes[-1] - closes[-5]) / closes[-5] * 100
            if len(closes) > 16:
                state.price_change_4h = (closes[-1] - closes[-17]) / closes[-17] * 100
            if len(closes) > 96:
                state.price_change_24h = (closes[-1] - closes[-97]) / closes[-97] * 100
            
            # Letzte Kerze
            last_open = opens[-1]
            last_close = closes[-1]
            last_high = highs[-1]
            last_low = lows[-1]
            
            body = last_close - last_open
            candle_range = last_high - last_low if last_high > last_low else 0.0001
            
            state.last_candle_body = body / candle_range
            
            upper_wick = last_high - max(last_open, last_close)
            lower_wick = min(last_open, last_close) - last_low
            state.last_candle_wick_ratio = (upper_wick - lower_wick) / candle_range
            
            # Consecutive Candles
            green_count = 0
            red_count = 0
            for i in range(-1, max(-10, -len(closes)), -1):
                if closes[i] > opens[i]:
                    green_count += 1
                    red_count = 0
                else:
                    red_count += 1
                    green_count = 0
                if green_count > 0 and red_count > 0:
                    break
            
            state.consecutive_green = green_count
            state.consecutive_red = red_count
            
            # RSI (14 Perioden)
            if len(closes) >= 15:
                deltas = np.diff(closes[-15:])
                gains = np.where(deltas > 0, deltas, 0)
                losses = np.where(deltas < 0, -deltas, 0)
                
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    state.rsi = 100 - (100 / (1 + rs))
                else:
                    state.rsi = 100 if avg_gain > 0 else 50
            
            # RSI Trend
            if len(closes) >= 20:
                prev_closes = closes[-20:-5]
                prev_deltas = np.diff(prev_closes)
                prev_gains = np.where(prev_deltas > 0, prev_deltas, 0)
                prev_losses = np.where(prev_deltas < 0, -prev_deltas, 0)
                prev_avg_gain = np.mean(prev_gains)
                prev_avg_loss = np.mean(prev_losses)
                if prev_avg_loss > 0:
                    prev_rs = prev_avg_gain / prev_avg_loss
                    prev_rsi = 100 - (100 / (1 + prev_rs))
                    state.rsi_trend = (state.rsi - prev_rsi) / 10
            
            # Volumen
            avg_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else volumes[-1]
            state.volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
            
            if len(volumes) >= 5:
                recent_avg = np.mean(volumes[-5:])
                older_avg = np.mean(volumes[-10:-5]) if len(volumes) >= 10 else recent_avg
                state.volume_trend = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
            
            # EMAs
            ema_20 = self._calc_ema(closes, 20)
            ema_50 = self._calc_ema(closes, 50)
            
            state.ema_20_distance = (closes[-1] - ema_20) / ema_20 * 100 if ema_20 > 0 else 0
            state.ema_50_distance = (closes[-1] - ema_50) / ema_50 * 100 if ema_50 > 0 else 0
            
            # EMA Cross
            if len(closes) >= 51:
                prev_ema_20 = self._calc_ema(closes[:-1], 20)
                prev_ema_50 = self._calc_ema(closes[:-1], 50)
                
                if prev_ema_20 < prev_ema_50 and ema_20 > ema_50:
                    state.ema_cross = 1  # Golden Cross
                elif prev_ema_20 > prev_ema_50 and ema_20 < ema_50:
                    state.ema_cross = -1  # Death Cross
            
            # ADX (vereinfacht)
            state.adx = float(ticker.get('priceChangePercent', 0)) if ticker else 25
            
            # Position-Kontext
            if position:
                state.has_position = True
                
                # Handle both Position object and dict
                if isinstance(position, dict):
                    entry_price = position.get('entry_price', 0)
                    entry_time = position.get('entry_time')
                    stop_loss = position.get('stop_loss')
                    take_profit = position.get('take_profit')
                else:
                    entry_price = position.entry_price
                    entry_time = getattr(position, 'entry_time', None)
                    stop_loss = getattr(position, 'stop_loss', None)
                    take_profit = getattr(position, 'take_profit', None)
                
                if entry_price and entry_price > 0:
                    state.position_pnl_pct = (state.current_price - entry_price) / entry_price * 100
                
                if entry_time:
                    if isinstance(entry_time, datetime):
                        state.position_hold_hours = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                
                if stop_loss and stop_loss > 0:
                    state.distance_to_stop_loss = (state.current_price - stop_loss) / stop_loss * 100
                
                if take_profit and take_profit > 0:
                    state.distance_to_take_profit = (take_profit - state.current_price) / state.current_price * 100
            
            # ============ PHASE 2: MICROSTRUCTURE FEATURES ============
            # Berechne Volatility aus 1-Minute Returns (falls genug Daten)
            if len(closes) >= 10:
                returns_1m = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, min(11, len(closes)))]
                state.volatility_1m = np.std(returns_1m) if returns_1m else 0
            
            # Microtrend Returns (30s, 60s, 180s entsprechend 0.5, 1, 3 Minuten Kerzen)
            # Bei 1-Minute Kerzen: 30s ~= 0.5 Kerzen, 60s = 1 Kerze, 180s = 3 Kerzen
            if len(closes) >= 4:
                # return_30s approximiert als halbe 1-Minute Bewegung
                state.return_30s = (closes[-1] - closes[-2]) / closes[-2] / 2 if closes[-2] > 0 else 0
                # return_60s = 1 Kerze zurück
                state.return_60s = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] > 0 else 0
                # return_180s = 3 Kerzen zurück
                if len(closes) >= 4:
                    state.return_180s = (closes[-1] - closes[-4]) / closes[-4] if closes[-4] > 0 else 0
            
        except Exception as e:
            logger.error(f"Market analysis error: {e}")
        
        return state
    
    async def analyze_market_with_orderbook(
        self, 
        symbol: str, 
        klines: List, 
        ticker: Dict, 
        position=None,
        orderbook_snapshot: Dict = None
    ) -> MarketState:
        """
        Erweiterte Marktanalyse MIT Orderbook-Daten
        
        Args:
            symbol: Trading-Paar
            klines: Kerzen-Daten
            ticker: 24h Ticker
            position: Aktuelle Position (falls vorhanden)
            orderbook_snapshot: Orderbook Snapshot von mexc.get_orderbook_snapshot()
        """
        # Basis-Analyse
        state = await self.analyze_market(symbol, klines, ticker, position)
        
        # Füge Orderbook-Features hinzu
        if orderbook_snapshot:
            try:
                state.spread_pct = orderbook_snapshot.get('spread_pct', 0)
                state.mid_price = orderbook_snapshot.get('mid_price', state.current_price)
                state.orderbook_imbalance = orderbook_snapshot.get('orderbook_imbalance', 1.0)
                state.bid_volume_sum = orderbook_snapshot.get('bid_volume_sum', 0)
                state.ask_volume_sum = orderbook_snapshot.get('ask_volume_sum', 0)
                
                logger.debug(f"[RL] {symbol} Orderbook: Spread={state.spread_pct:.4f}% | Imbalance={state.orderbook_imbalance:.2f}")
            except Exception as e:
                logger.warning(f"Orderbook feature error for {symbol}: {e}")
        
        return state
    
    def _calc_ema(self, data: List[float], period: int) -> float:
        """Berechne EMA"""
        if len(data) < period:
            return data[-1] if data else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    async def should_buy(self, symbol: str, state: MarketState, can_afford: bool = True) -> Dict:
        """
        Soll gekauft werden? - 100% KI-ENTSCHEIDUNG
        
        WICHTIG: Konservativere Buy-Exploration (30% statt 50%)
        """
        if state.has_position:
            return {
                'should_buy': False,
                'confidence': 0,
                'reasoning': 'Bereits Position vorhanden',
                'action': 'HOLD',
                'exploration': False
            }
        
        if not can_afford:
            return {
                'should_buy': False,
                'confidence': 0,
                'reasoning': 'Nicht genug Kapital',
                'action': 'HOLD',
                'exploration': False
            }
        
        state_array = state.to_array()
        q_values = self.brain.get_q_values(state_array)
        
        # KI-Entscheidung mit Exploration
        is_exploration = random.random() < self.brain.epsilon
        
        if is_exploration:
            # KONSERVATIVE Buy-Exploration: Nur 30% Chance zu kaufen
            # Verhindert zu viele zufällige Käufe
            action = Action.BUY if random.random() < 0.3 else Action.HOLD
            reason = f"🎲 EXPLORATION: {Action.to_string(action)} (30% Buy-Chance)"
        else:
            # Exploitation: Nutze gelerntes Wissen
            action = Action.BUY if q_values[1] > q_values[0] else Action.HOLD
            reason = f"🧠 KI: {Action.to_string(action)} | Q[BUY]={q_values[1]:.3f} vs Q[HOLD]={q_values[0]:.3f}"
        
        confidence = max(0, min(100, 50 + abs(q_values[1] - q_values[0]) * 30))
        
        if action == Action.BUY:
            logger.info(f"[RL] {symbol}: {reason} | Trades: {self.brain.total_trades}, Win: {self.brain.win_rate*100:.0f}%")
        
        return {
            'should_buy': action == Action.BUY,
            'confidence': confidence,
            'reasoning': reason,
            'action': Action.to_string(action),
            'exploration': is_exploration
        }
    
    async def should_sell(self, symbol: str, state: MarketState) -> Dict:
        """
        Soll verkauft werden? - 100% KI-ENTSCHEIDUNG
        
        ANTI-FLIP PROTECTION:
        - Mindest-Haltezeit: 90 Sekunden (verhindert Flip-Trading)
        - Exploration Guard: Bei hohem Epsilon kein zufälliges SELL unter 180s
        - SELL nur durch Exploitation oder Emergency, NICHT durch random Exploration
        - Hard Exit: 10 Minuten wird in worker.py erzwungen
        """
        if not state.has_position:
            return {
                'should_sell': False,
                'confidence': 0,
                'reasoning': 'Keine Position vorhanden',
                'action': 'HOLD',
                'exploration': False,
                'q_values': None,
                'sell_source': None
            }
        
        pnl = state.position_pnl_pct  # Dies ist jetzt NET PnL!
        hold_hours = state.position_hold_hours if hasattr(state, 'position_hold_hours') else 0
        hold_seconds = hold_hours * 3600
        
        # ============ KONSTANTEN ============
        MIN_HOLD_SECONDS = 90          # Absolute Mindesthaltezeit
        EXPLORATION_SELL_SECONDS = 180  # Random SELL erst ab hier (bei hohem epsilon)
        EMERGENCY_THRESHOLD = -5.0      # Emergency Exit Schwelle
        HIGH_EPSILON_THRESHOLD = 0.5    # Ab hier gilt "hohe Exploration"
        
        epsilon = self.brain.epsilon
        is_high_exploration = epsilon > HIGH_EPSILON_THRESHOLD
        
        # ============ PHASE 1: ABSOLUTE MINDESTHALTEZEIT (90s) ============
        if hold_seconds < MIN_HOLD_SECONDS:
            # Emergency Exit auch vor Mindesthaltezeit erlaubt
            if pnl <= EMERGENCY_THRESHOLD:
                return {
                    'should_sell': True,
                    'confidence': 100,
                    'reasoning': f'🚨 EMERGENCY: Net PnL {pnl:.1f}% <= {EMERGENCY_THRESHOLD}% (Hold: {hold_seconds:.0f}s)',
                    'action': 'SELL',
                    'exploration': False,
                    'exit_reason': 'emergency',
                    'q_values': None,
                    'sell_source': 'emergency'
                }
            
            return {
                'should_sell': False,
                'confidence': 0,
                'reasoning': f'⏳ Mindesthaltezeit: {hold_seconds:.0f}s < {MIN_HOLD_SECONDS}s | Net PnL: {pnl:+.2f}%',
                'action': 'HOLD',
                'exploration': False,
                'q_values': None,
                'sell_source': None
            }
        
        # ============ PHASE 2: Q-VALUES BERECHNEN ============
        state_array = state.to_array()
        q_values = self.brain.get_q_values(state_array)
        q_dict = {'hold': float(q_values[0]), 'buy': float(q_values[1]), 'sell': float(q_values[2])}
        
        # Exploitation-basierte Entscheidung
        exploitation_says_sell = q_values[2] > q_values[0]
        q_diff = q_values[2] - q_values[0]  # Positiv = SELL besser
        
        # ============ PHASE 3: EXPLORATION GUARD FÜR SELL ============
        # Bei hohem Epsilon: Random SELL erst ab 180s, davor nur Exploitation/Emergency
        
        is_exploration_phase = random.random() < epsilon
        
        if is_high_exploration and hold_seconds < EXPLORATION_SELL_SECONDS:
            # Hohe Exploration + unter 180s: SELL nur durch Exploitation oder Emergency
            
            if pnl <= EMERGENCY_THRESHOLD:
                return {
                    'should_sell': True,
                    'confidence': 100,
                    'reasoning': f'🚨 EMERGENCY: Net PnL {pnl:.1f}% (Hold: {hold_seconds:.0f}s)',
                    'action': 'SELL',
                    'exploration': False,
                    'exit_reason': 'emergency',
                    'q_values': q_dict,
                    'sell_source': 'emergency'
                }
            
            if exploitation_says_sell and q_diff > 0.1:  # Starkes Exploitation-Signal
                reason = f"🧠 EXPLOITATION SELL: Q[SELL]={q_values[2]:.3f} >> Q[HOLD]={q_values[0]:.3f} | Net PnL: {pnl:+.2f}%"
                logger.info(f"[RL] {symbol}: {reason}")
                return {
                    'should_sell': True,
                    'confidence': max(0, min(100, 50 + q_diff * 50)),
                    'reasoning': reason,
                    'action': 'SELL',
                    'exploration': False,
                    'exit_reason': 'ai_exit',
                    'q_values': q_dict,
                    'sell_source': 'exploitation'
                }
            
            # Kein SELL - zu früh für random exploration
            return {
                'should_sell': False,
                'confidence': 0,
                'reasoning': f'⏳ Exploration Guard: {hold_seconds:.0f}s < {EXPLORATION_SELL_SECONDS}s (ε={epsilon:.2f}) | Net PnL: {pnl:+.2f}%',
                'action': 'HOLD',
                'exploration': False,
                'q_values': q_dict,
                'sell_source': None
            }
        
        # ============ PHASE 4: NORMALE ENTSCHEIDUNG (>180s oder niedrige Exploration) ============
        
        if is_exploration_phase:
            # Exploration: SELL-Wahrscheinlichkeit steigt mit Haltezeit
            # Damit die KI auch längere Haltezeiten explorieren kann!
            
            # Base: 2% pro Minute nach 180s
            # Bei 3 Min (180s) = 0%, 4 Min (240s) = 2%, 5 Min (300s) = 4%, etc.
            # Hard Exit ist bei 10 Min (600s) ohnehin
            minutes_over_guard = max(0, (hold_seconds - EXPLORATION_SELL_SECONDS) / 60)
            sell_prob_per_check = min(0.05, 0.005 + minutes_over_guard * 0.01)  # 0.5% + 1% pro Minute, max 5%
            
            # Alternative: Time-weighted probability
            # Je länger gehalten, desto höher die SELL-Chance (aber immer noch niedrig)
            
            if random.random() < sell_prob_per_check:
                reason = f"🎲 EXPLORATION SELL: Random ({sell_prob_per_check*100:.1f}%) | Net PnL: {pnl:+.2f}% | Hold: {hold_seconds:.0f}s | ε={epsilon:.2f}"
                logger.info(f"[RL] {symbol}: {reason}")
                return {
                    'should_sell': True,
                    'confidence': 30,
                    'reasoning': reason,
                    'action': 'SELL',
                    'exploration': True,
                    'exit_reason': 'ai_exit',
                    'q_values': q_dict,
                    'sell_source': 'random_exploration'
                }
            else:
                reason = f"🎲 EXPLORATION HOLD: Net PnL: {pnl:+.2f}% | Hold: {hold_seconds:.0f}s (sell_prob={sell_prob_per_check*100:.1f}%)"
                return {
                    'should_sell': False,
                    'confidence': 0,
                    'reasoning': reason,
                    'action': 'HOLD',
                    'exploration': True,
                    'q_values': q_dict,
                    'sell_source': None
                }
        else:
            # Exploitation: Nutze gelerntes Wissen
            if exploitation_says_sell:
                reason = f"🧠 EXPLOITATION SELL: Q[SELL]={q_values[2]:.3f} > Q[HOLD]={q_values[0]:.3f} | Net PnL: {pnl:+.2f}%"
                logger.info(f"[RL] {symbol}: {reason}")
                return {
                    'should_sell': True,
                    'confidence': max(0, min(100, 50 + q_diff * 30)),
                    'reasoning': reason,
                    'action': 'SELL',
                    'exploration': False,
                    'exit_reason': 'ai_exit',
                    'q_values': q_dict,
                    'sell_source': 'exploitation'
                }
            else:
                reason = f"🧠 EXPLOITATION HOLD: Q[HOLD]={q_values[0]:.3f} >= Q[SELL]={q_values[2]:.3f} | Net PnL: {pnl:+.2f}%"
                return {
                    'should_sell': False,
                    'confidence': max(0, min(100, 50 + abs(q_diff) * 30)),
                    'reasoning': reason,
                    'action': 'HOLD',
                    'exploration': False,
                    'q_values': q_dict,
                    'sell_source': None
                }
    
    async def start_episode(self, symbol: str, state: MarketState, entry_price: float, entry_value: float = 0.0):
        """Starte neue Episode (Trade eröffnet)"""
        self.current_episode[symbol] = {
            'start_state': state.to_array(),
            'entry_price': entry_price,
            'entry_value': entry_value,  # Notional in USDT
            'start_time': datetime.now(timezone.utc),
            'states': [state.to_array()],
            'actions': [Action.BUY]
        }
        logger.info(f"[RL] Episode gestartet: {symbol} @ ${entry_price:.4f} | Value: ${entry_value:.2f}")
    
    async def update_episode(self, symbol: str, state: MarketState, action: int):
        """Update Episode mit neuem State"""
        if symbol in self.current_episode:
            self.current_episode[symbol]['states'].append(state.to_array())
            self.current_episode[symbol]['actions'].append(action)
    
    async def end_episode(
        self, 
        symbol: str, 
        final_state: MarketState, 
        exit_price: float, 
        pnl_pct: float,
        fees_paid: float = 0.0,
        slippage_cost: float = 0.0,
        exit_reason: str = "ai_exit",
        gross_pnl_usdt: float = 0.0
    ):
        """
        Beende Episode (Trade geschlossen) und lerne daraus
        
        NET PnL REWARD SYSTEM:
        - reward = net_pnl_pct (nach Gebühren und Slippage)
        - Keine Zeit-Bonus/Malus mehr
        - KI lernt aus realistischen Netto-Ergebnissen
        """
        if symbol not in self.current_episode:
            # Episode nicht gefunden - erstelle eine synthetische Episode
            # Dies passiert wenn der Server zwischen Trade-Open und Trade-Close neugestartet wurde
            logger.warning(f"[RL] ⚠️ {symbol}: Keine aktive Episode gefunden - erstelle synthetische Episode für Lernen")
            
            # Erstelle synthetische Episode mit finalem State
            synthetic_episode = {
                'start_state': final_state.to_array(),
                'entry_price': exit_price / (1 + pnl_pct/100) if pnl_pct != 0 else exit_price,
                'entry_value': 30.0,  # Geschätzter Standardwert
                'start_time': datetime.now(timezone.utc) - timedelta(seconds=180),  # Geschätzte Dauer
                'states': [final_state.to_array()],
                'actions': [Action.BUY]
            }
            self.current_episode[symbol] = synthetic_episode
        
        episode = self.current_episode[symbol]
        duration_seconds = (datetime.now(timezone.utc) - episode['start_time']).total_seconds()
        duration_minutes = duration_seconds / 60
        
        # ============ NET PnL REWARD SYSTEM ============
        # Berechne Net PnL nach Kosten
        # gross_pnl = entry_value * (pnl_pct / 100)
        # net_pnl = gross_pnl - fees - slippage
        
        entry_price = episode['entry_price']
        
        # Wenn gross_pnl_usdt nicht übergeben, berechne aus pnl_pct
        if gross_pnl_usdt == 0 and pnl_pct != 0:
            # Schätze basierend auf typischer Position
            gross_pnl_usdt = pnl_pct  # Vereinfacht: verwende pnl_pct als Proxy
        
        # Net PnL nach allen Kosten
        total_costs = fees_paid + slippage_cost
        net_pnl_usdt = gross_pnl_usdt - total_costs
        
        # Net PnL Prozent (für Reward)
        # Schätze entry_value wenn nicht bekannt
        entry_value = episode.get('entry_value', entry_price * 100)  # Fallback
        if entry_value > 0:
            net_pnl_pct = (net_pnl_usdt / entry_value) * 100
        else:
            net_pnl_pct = pnl_pct - (total_costs / max(entry_price, 1) * 100)
        
        # REWARD = Net PnL Prozent (KEINE Zeit-Multiplikatoren!)
        reward = net_pnl_pct
        
        # ============ ÄNDERUNG 3: FLIP-PENALTY ============
        # Trades unter 60 Sekunden bekommen Straf-Penalty
        # Das lehrt die KI: ultra short trades = negative reward
        FLIP_THRESHOLD_SECONDS = 60
        FLIP_PENALTY = 0.15  # 0.15% Strafe für Flip-Trades
        
        if duration_seconds < FLIP_THRESHOLD_SECONDS:
            reward -= FLIP_PENALTY
            logger.warning(f"[RL] ⚠️ {symbol}: FLIP-PENALTY! Duration {duration_seconds:.0f}s < {FLIP_THRESHOLD_SECONDS}s | Reward: {reward:+.3f}%")
        
        # Logging
        cost_info = f"Fees: ${fees_paid:.4f}, Slip: ${slippage_cost:.4f}" if fees_paid > 0 or slippage_cost > 0 else "Costs: estimated"
        logger.info(f"[RL] 💰 {symbol}: Gross PnL: {pnl_pct:+.2f}% → Net: {net_pnl_pct:+.2f}% | {cost_info}")
        
        # ============ TRAINING FILTER ============
        # Filtere fehlerhafte Trades aus dem Training
        should_learn = True
        
        # API Error oder extrem kurze Trades (< 5s) nicht lernen
        if exit_reason == "api_error":
            should_learn = False
            logger.warning(f"[RL] ⚠️ {symbol}: API Error Trade - NICHT in Training")
        
        # Extremer Slippage (> 2%) markieren
        if entry_value > 0 and slippage_cost > 0:
            slippage_pct = (slippage_cost / entry_value) * 100
            if slippage_pct > 2.0:
                logger.warning(f"[RL] ⚠️ {symbol}: Hoher Slippage {slippage_pct:.2f}% - Trade markiert")
                # Weiterhin lernen, aber mit reduziertem Reward
                reward *= 0.5
        
        if should_learn:
            # Lerne aus der Erfahrung
            states = episode['states']
            actions = episode['actions']
            
            for i in range(len(states) - 1):
                exp = Experience(
                    state=states[i],
                    action=actions[i],
                    reward=reward / len(states),
                    next_state=states[i + 1],
                    done=(i == len(states) - 2)
                )
                self.brain.learn(exp)
            
            # Finale Experience
            exp = Experience(
                state=states[-1],
                action=Action.SELL,
                reward=reward,
                next_state=final_state.to_array(),
                done=True
            )
            self.brain.learn(exp)
        
        # Statistiken (immer aktualisieren)
        self.brain.record_trade_result(reward, net_pnl_pct > 0)
        
        # Speichere Modell
        self._save_model()
        
        # Cleanup
        del self.current_episode[symbol]
        
        emoji = "✅" if net_pnl_pct > 0 else "❌"
        exit_label = f"[{exit_reason.upper()}]" if exit_reason != "ai_exit" else ""
        logger.info(f"[RL] {emoji} Episode beendet: {symbol} {exit_label}")
        logger.info(f"[RL]    → Gross PnL: {pnl_pct:+.2f}% | Net PnL: {net_pnl_pct:+.2f}%")
        logger.info(f"[RL]    → Dauer: {duration_seconds:.0f}s ({duration_minutes:.1f}min)")
        logger.info(f"[RL]    → Kosten: ${total_costs:.4f} | Reward: {reward:.3f}")
        
        # Detailliertes Lern-Log
        logger.info(f"[RL] 📊 LERNSTATUS nach {symbol}:")
        logger.info(f"[RL]    → Gesamte Trades: {self.brain.total_trades}")
        logger.info(f"[RL]    → Gewonnen: {self.brain.winning_trades} ({self.brain.win_rate*100:.1f}%)")
        logger.info(f"[RL]    → Gesamt-Reward: {self.brain.total_reward:.2f}")
        logger.info(f"[RL]    → Exploration: {self.brain.epsilon*100:.1f}% (sinkt mit Erfahrung)")
        logger.info(f"[RL]    → Erfahrungen im Speicher: {len(self.brain.memory)}")
        logger.info(f"[RL]    → Training-Episoden: {self.brain.training_episodes}")
    
    def get_status(self) -> Dict:
        """Hole KI-Status"""
        brain_status = self.brain.get_status()
        return {
            **brain_status,
            "active_episodes": list(self.current_episode.keys()),
            "model_path": self.MODEL_PATH,
            "description": f"RL Trading AI - {brain_status['total_trades']} Trades, {brain_status['win_rate']*100:.1f}% Win-Rate"
        }


# Singleton
_rl_ai: Optional[RLTradingAI] = None

def get_rl_trading_ai(db=None) -> RLTradingAI:
    """Get or create RL Trading AI singleton"""
    global _rl_ai
    if _rl_ai is None:
        _rl_ai = RLTradingAI(db)
    elif db and _rl_ai.db is None:
        _rl_ai.db = db
    return _rl_ai
