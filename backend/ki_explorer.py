"""
KI Explorer Mode - Experimenteller Trading Modus für ML Training

Dieser Modus variiert absichtlich die Trading-Parameter um der KI
zu zeigen welche Kombinationen am besten funktionieren.

WICHTIG: Nur mit kleinen Beträgen nutzen! Das ist zum Lernen, nicht zum Profit.
"""

import random
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExplorationStrategy(Enum):
    """Verschiedene Exploration-Strategien"""
    RANDOM = "random"  # Komplett zufällig
    GRID = "grid"  # Systematisch alle Kombinationen
    BAYESIAN = "bayesian"  # Fokus auf vielversprechende Bereiche


@dataclass
class ExplorerParameters:
    """Zufällig generierte Parameter für einen Trade"""
    
    # Entry Bedingungen
    rsi_threshold: float  # 20-50
    adx_minimum: float  # 5-35
    volume_factor: float  # 0.5-2.0 (multiplier für min volume)
    
    # Position Sizing
    position_pct: float  # 5-40% vom verfügbaren USDT
    
    # Risk Management
    stop_loss_pct: float  # 3-15%
    take_profit_rr: float  # 1.0-3.5 (Risk:Reward Ratio)
    
    # Timing
    use_momentum_filter: bool
    use_regime_filter: bool
    
    # Extras
    partial_profit_enabled: bool
    partial_profit_pct: float  # 5-12% trigger
    trailing_stop_enabled: bool
    
    # Futures Vorbereitung
    suggested_leverage: int  # 1-10x (für später)
    direction_preference: str  # "long_only", "short_only", "both"
    
    def to_dict(self) -> Dict:
        return asdict(self)


class KIExplorerEngine:
    """
    Engine die zufällige aber sinnvolle Parameter-Kombinationen generiert
    für maximales Lernen der KI.
    """
    
    def __init__(self):
        self.exploration_count = 0
        self.parameter_history = []
    
    def generate_random_parameters(self) -> ExplorerParameters:
        """Generiert zufällige Parameter-Kombination"""
        
        params = ExplorerParameters(
            # Entry - breite Variation
            rsi_threshold=random.uniform(20, 50),
            adx_minimum=random.uniform(5, 35),
            volume_factor=random.uniform(0.5, 2.0),
            
            # Position - verschiedene Größen testen
            position_pct=random.uniform(5, 40),
            
            # Risk - verschiedene SL/TP testen
            stop_loss_pct=random.uniform(3, 15),
            take_profit_rr=random.uniform(1.0, 3.5),
            
            # Timing Filters - mal an, mal aus
            use_momentum_filter=random.choice([True, False]),
            use_regime_filter=random.choice([True, False]),
            
            # Extras - verschiedene Strategien
            partial_profit_enabled=random.choice([True, False]),
            partial_profit_pct=random.uniform(5, 12),
            trailing_stop_enabled=random.choice([True, False]),
            
            # Futures Prep
            suggested_leverage=random.randint(1, 10),
            direction_preference=random.choice(["long_only", "short_only", "both"])
        )
        
        self.exploration_count += 1
        self.parameter_history.append(params.to_dict())
        
        logger.info(f"[EXPLORER] Generated params #{self.exploration_count}: "
                   f"RSI<{params.rsi_threshold:.0f}, ADX>{params.adx_minimum:.0f}, "
                   f"SL={params.stop_loss_pct:.1f}%, TP=1:{params.take_profit_rr:.1f}")
        
        return params
    
    def generate_grid_parameters(self, grid_index: int) -> ExplorerParameters:
        """Systematische Grid-Exploration"""
        
        # Grid-Werte
        rsi_values = [25, 30, 35, 40, 45]
        adx_values = [10, 15, 20, 25, 30]
        sl_values = [4, 6, 8, 10, 12]
        tp_values = [1.2, 1.5, 2.0, 2.5, 3.0]
        
        # Index in Grid-Position umwandeln
        total_combinations = len(rsi_values) * len(adx_values) * len(sl_values) * len(tp_values)
        idx = grid_index % total_combinations
        
        rsi_idx = idx % len(rsi_values)
        adx_idx = (idx // len(rsi_values)) % len(adx_values)
        sl_idx = (idx // (len(rsi_values) * len(adx_values))) % len(sl_values)
        tp_idx = (idx // (len(rsi_values) * len(adx_values) * len(sl_values))) % len(tp_values)
        
        params = ExplorerParameters(
            rsi_threshold=rsi_values[rsi_idx],
            adx_minimum=adx_values[adx_idx],
            volume_factor=1.0,
            position_pct=random.uniform(10, 25),  # Moderate Position
            stop_loss_pct=sl_values[sl_idx],
            take_profit_rr=tp_values[tp_idx],
            use_momentum_filter=True,
            use_regime_filter=True,
            partial_profit_enabled=random.choice([True, False]),
            partial_profit_pct=8.0,
            trailing_stop_enabled=False,
            suggested_leverage=random.randint(2, 5),
            direction_preference="long_only"
        )
        
        self.exploration_count += 1
        return params
    
    def should_take_trade(self, 
                          params: ExplorerParameters,
                          current_rsi: float,
                          current_adx: float,
                          regime: str,
                          momentum: float) -> Tuple[bool, str]:
        """
        Entscheidet ob Trade genommen wird basierend auf Explorer-Params
        Returns: (should_trade, reason)
        """
        
        reasons = []
        
        # RSI Check
        if current_rsi > params.rsi_threshold:
            return False, f"RSI {current_rsi:.0f} > Threshold {params.rsi_threshold:.0f}"
        reasons.append(f"RSI={current_rsi:.0f}✓")
        
        # ADX Check
        if current_adx < params.adx_minimum:
            return False, f"ADX {current_adx:.0f} < Minimum {params.adx_minimum:.0f}"
        reasons.append(f"ADX={current_adx:.0f}✓")
        
        # Regime Filter (wenn aktiviert)
        if params.use_regime_filter:
            if regime == "BEARISH" and params.direction_preference == "long_only":
                return False, f"Regime BEARISH, nur LONG erlaubt"
            if regime == "BULLISH" and params.direction_preference == "short_only":
                return False, f"Regime BULLISH, nur SHORT erlaubt"
        
        # Momentum Filter (wenn aktiviert)
        if params.use_momentum_filter:
            if momentum < -20 and params.direction_preference == "long_only":
                return False, f"Momentum {momentum:.0f} zu negativ für LONG"
        
        return True, " | ".join(reasons)
    
    def calculate_sl_tp(self, 
                        params: ExplorerParameters,
                        entry_price: float,
                        atr_value: float) -> Tuple[float, float, float, float]:
        """
        Berechnet SL und TP basierend auf Explorer-Params
        Returns: (sl_price, sl_pct, tp_price, tp_pct)
        """
        
        # Stop Loss
        sl_pct = params.stop_loss_pct
        sl_price = entry_price * (1 - sl_pct / 100)
        
        # Take Profit basierend auf Risk:Reward
        tp_pct = sl_pct * params.take_profit_rr
        tp_price = entry_price * (1 + tp_pct / 100)
        
        return sl_price, sl_pct, tp_price, tp_pct
    
    def get_exploration_stats(self) -> Dict:
        """Statistiken über bisherige Exploration"""
        
        if not self.parameter_history:
            return {"total_explorations": 0}
        
        # Durchschnittswerte berechnen
        avg_rsi = sum(p['rsi_threshold'] for p in self.parameter_history) / len(self.parameter_history)
        avg_adx = sum(p['adx_minimum'] for p in self.parameter_history) / len(self.parameter_history)
        avg_sl = sum(p['stop_loss_pct'] for p in self.parameter_history) / len(self.parameter_history)
        avg_tp = sum(p['take_profit_rr'] for p in self.parameter_history) / len(self.parameter_history)
        
        return {
            "total_explorations": self.exploration_count,
            "avg_rsi_threshold": round(avg_rsi, 1),
            "avg_adx_minimum": round(avg_adx, 1),
            "avg_stop_loss_pct": round(avg_sl, 1),
            "avg_take_profit_rr": round(avg_tp, 2),
            "parameter_range": {
                "rsi": [min(p['rsi_threshold'] for p in self.parameter_history),
                       max(p['rsi_threshold'] for p in self.parameter_history)],
                "adx": [min(p['adx_minimum'] for p in self.parameter_history),
                       max(p['adx_minimum'] for p in self.parameter_history)],
                "sl": [min(p['stop_loss_pct'] for p in self.parameter_history),
                      max(p['stop_loss_pct'] for p in self.parameter_history)]
            }
        }


# Singleton
ki_explorer = KIExplorerEngine()
