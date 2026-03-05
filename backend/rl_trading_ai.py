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
    
    def to_array(self) -> np.ndarray:
        """Konvertiere zu Feature-Array für KI"""
        return np.array([
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
            self.distance_to_take_profit / 10
        ], dtype=np.float32)
    
    @staticmethod
    def state_size() -> int:
        return 22


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


class ReplayMemory:
    """Speicher für Erfahrungen - KI lernt aus der Vergangenheit"""
    
    def __init__(self, capacity: int = 10000):
        self.memory = deque(maxlen=capacity)
    
    def push(self, experience: Experience):
        self.memory.append(experience)
    
    def sample(self, batch_size: int) -> List[Experience]:
        return random.sample(self.memory, min(batch_size, len(self.memory)))
    
    def __len__(self) -> int:
        return len(self.memory)


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
        epsilon_end: float = 0.1,  # End-Exploration
        epsilon_decay: float = 0.995  # Wie schnell Exploration sinkt
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
        """Lerne aus einer Erfahrung"""
        self.memory.push(experience)
        
        # Batch-Learning wenn genug Erfahrungen
        if len(self.memory) < 32:
            return
        
        batch = self.memory.sample(32)
        
        for exp in batch:
            # Q-Learning Update
            current_q = self.get_q_values(exp.state)[exp.action]
            
            if exp.done:
                target_q = exp.reward
            else:
                next_q_values = self.get_q_values(exp.next_state)
                target_q = exp.reward + self.gamma * np.max(next_q_values)
            
            # Update Q-Funktion
            if self.model_type == "neural_network":
                # Partial fit für Neural Network
                state_2d = exp.state.reshape(1, -1)
                self.q_networks[exp.action].partial_fit(state_2d, np.array([target_q]))
            else:
                # Q-Table Update
                key = self._discretize_state(exp.state)
                if key not in self.q_table:
                    self.q_table[key] = np.zeros(self.action_size)
                
                # Q-Learning Formula
                self.q_table[key][exp.action] += self.learning_rate * (
                    target_q - self.q_table[key][exp.action]
                )
        
        # Decay Exploration
        old_epsilon = self.epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        self.training_episodes += 1
        
        # Log Lernfortschritt alle 10 Episoden
        if self.training_episodes % 10 == 0:
            logger.info(f"[RL] 🎓 LERNFORTSCHRITT:")
            logger.info(f"[RL]    → Episoden: {self.training_episodes}")
            logger.info(f"[RL]    → Exploration: {old_epsilon*100:.1f}% → {self.epsilon*100:.1f}%")
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
    
    MODEL_PATH = "/tmp/reetrade_rl_brain.pkl"
    
    def __init__(self, db=None):
        self.db = db
        self.brain = QLearningBrain()
        
        # Aktuelle Episode (offener Trade)
        self.current_episode: Dict[str, Dict] = {}  # {symbol: episode_data}
        
        # Lade gespeichertes Modell
        self._load_model()
    
    def _load_model(self):
        """Lade trainiertes Modell"""
        try:
            if os.path.exists(self.MODEL_PATH):
                with open(self.MODEL_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.brain.epsilon = data.get('epsilon', self.brain.epsilon)
                    self.brain.total_trades = data.get('total_trades', 0)
                    self.brain.winning_trades = data.get('winning_trades', 0)
                    self.brain.total_reward = data.get('total_reward', 0)
                    if 'q_table' in data and self.brain.model_type == 'q_table':
                        self.brain.q_table = data['q_table']
                    logger.info(f"RL Model geladen: {self.brain.total_trades} Trades, {self.brain.win_rate:.1%} Win-Rate")
        except Exception as e:
            logger.warning(f"Konnte RL Model nicht laden: {e}")
    
    def _save_model(self):
        """Speichere Modell"""
        try:
            data = {
                'epsilon': self.brain.epsilon,
                'total_trades': self.brain.total_trades,
                'winning_trades': self.brain.winning_trades,
                'total_reward': self.brain.total_reward,
                'training_episodes': self.brain.training_episodes
            }
            if self.brain.model_type == 'q_table':
                data['q_table'] = self.brain.q_table
            
            with open(self.MODEL_PATH, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Konnte RL Model nicht speichern: {e}")
    
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
                state.position_pnl_pct = (state.current_price - position.entry_price) / position.entry_price * 100
                
                if hasattr(position, 'entry_time') and position.entry_time:
                    state.position_hold_hours = (datetime.now(timezone.utc) - position.entry_time).total_seconds() / 3600
                
                if position.stop_loss:
                    state.distance_to_stop_loss = (state.current_price - position.stop_loss) / position.stop_loss * 100
                
                if position.take_profit:
                    state.distance_to_take_profit = (position.take_profit - state.current_price) / state.current_price * 100
            
        except Exception as e:
            logger.error(f"Market analysis error: {e}")
        
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
        
        Die KI entscheidet selbstständig basierend auf:
        - Gelernten Q-Values (was hat in der Vergangenheit funktioniert?)
        - Exploration (neue Strategien ausprobieren)
        
        Das Reward-System sagt der KI was das Ziel ist:
        → Schnelle profitable Trades = hoher Reward
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
            # Exploration: Zufällig BUY oder HOLD (50/50)
            action = Action.BUY if random.random() < 0.5 else Action.HOLD
            reason = f"🎲 EXPLORATION: {Action.to_string(action)} (zufällig, um zu lernen)"
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
        
        Die KI entscheidet selbstständig basierend auf:
        - Gelernten Q-Values (was hat in der Vergangenheit funktioniert?)
        - Exploration (neue Strategien ausprobieren)
        
        Das Reward-System sagt der KI was das Ziel ist:
        → Schnelle profitable Trades = hoher Reward
        → Langes Halten = niedriger Reward
        """
        if not state.has_position:
            return {
                'should_sell': False,
                'confidence': 0,
                'reasoning': 'Keine Position vorhanden',
                'action': 'HOLD',
                'exploration': False
            }
        
        pnl = state.position_pnl_pct
        state_array = state.to_array()
        q_values = self.brain.get_q_values(state_array)
        
        # KI-Entscheidung mit Exploration
        is_exploration = random.random() < self.brain.epsilon
        
        if is_exploration:
            # Exploration: Zufällig SELL oder HOLD (50/50)
            action = Action.SELL if random.random() < 0.5 else Action.HOLD
            reason = f"🎲 EXPLORATION: {Action.to_string(action)} (zufällig) | PnL: {pnl:+.2f}%"
        else:
            # Exploitation: Nutze gelerntes Wissen
            action = Action.SELL if q_values[2] > q_values[0] else Action.HOLD
            reason = f"🧠 KI: {Action.to_string(action)} | Q[SELL]={q_values[2]:.3f} vs Q[HOLD]={q_values[0]:.3f} | PnL: {pnl:+.2f}%"
        
        confidence = max(0, min(100, 50 + abs(q_values[2] - q_values[0]) * 30))
        
        if action == Action.SELL:
            logger.info(f"[RL] {symbol}: {reason}")
        
        return {
            'should_sell': action == Action.SELL,
            'confidence': confidence,
            'reasoning': reason,
            'action': Action.to_string(action),
            'exploration': is_exploration
        }
    
    async def start_episode(self, symbol: str, state: MarketState, entry_price: float):
        """Starte neue Episode (Trade eröffnet)"""
        self.current_episode[symbol] = {
            'start_state': state.to_array(),
            'entry_price': entry_price,
            'start_time': datetime.now(timezone.utc),
            'states': [state.to_array()],
            'actions': [Action.BUY]
        }
        logger.info(f"[RL] Episode gestartet: {symbol} @ ${entry_price:.4f}")
    
    async def update_episode(self, symbol: str, state: MarketState, action: int):
        """Update Episode mit neuem State"""
        if symbol in self.current_episode:
            self.current_episode[symbol]['states'].append(state.to_array())
            self.current_episode[symbol]['actions'].append(action)
    
    async def end_episode(self, symbol: str, final_state: MarketState, exit_price: float, pnl_pct: float):
        """
        Beende Episode (Trade geschlossen) und lerne daraus
        
        HOCHFREQUENZ-TRADING REWARDS:
        - Schnelle profitable Trades = HOHER Reward
        - Langes Halten = BESTRAFUNG
        - Kleine Gewinne schnell > Große Gewinne langsam
        """
        if symbol not in self.current_episode:
            return
        
        episode = self.current_episode[symbol]
        duration_hours = (datetime.now(timezone.utc) - episode['start_time']).total_seconds() / 3600
        duration_minutes = duration_hours * 60
        
        # ============ HOCHFREQUENZ REWARD SYSTEM ============
        # Basis: PnL Prozent
        reward = pnl_pct
        
        # BONUS für schnelle Trades (Hochfrequenz!)
        if pnl_pct > 0:
            if duration_minutes < 5:      # Unter 5 Min = MEGA BONUS
                reward *= 3.0
                logger.info(f"[RL] ⚡ BLITZ-TRADE! {duration_minutes:.1f}min → 3x Reward")
            elif duration_minutes < 15:   # Unter 15 Min = Großer Bonus
                reward *= 2.0
                logger.info(f"[RL] 🚀 SCHNELL-TRADE! {duration_minutes:.1f}min → 2x Reward")
            elif duration_minutes < 30:   # Unter 30 Min = Bonus
                reward *= 1.5
            elif duration_hours > 2:      # Über 2 Stunden = Reduziert
                reward *= 0.5
                logger.info(f"[RL] 🐢 Zu langsam gehalten ({duration_hours:.1f}h) → 0.5x Reward")
        
        # BESTRAFUNG für langes Halten bei Verlust
        if pnl_pct < 0:
            if duration_hours > 1:  # Verlust über 1 Stunde gehalten
                reward *= 1.5  # Verstärke negative Strafe
                logger.info(f"[RL] ⚠️ Verlust zu lange gehalten → Extra Strafe")
            if duration_minutes < 10 and pnl_pct > -1:  # Schneller kleiner Verlust ist OK
                reward *= 0.5  # Reduziere Strafe für schnelles Aussteigen
                logger.info(f"[RL] 👍 Schnell bei kleinem Verlust raus → Reduzierte Strafe")
        
        # BONUS für viele Trades (KI soll aktiv sein)
        if self.brain.total_trades > 0 and self.brain.total_trades % 10 == 0:
            reward += 1.0  # Bonus alle 10 Trades
        
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
        
        # Statistiken
        self.brain.record_trade_result(reward, pnl_pct > 0)
        
        # Speichere Modell
        self._save_model()
        
        # Cleanup
        del self.current_episode[symbol]
        
        emoji = "✅" if pnl_pct > 0 else "❌"
        logger.info(f"[RL] {emoji} Episode beendet: {symbol} | PnL: {pnl_pct:.2f}% | Dauer: {duration_minutes:.0f}min | Reward: {reward:.2f}")
        
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
