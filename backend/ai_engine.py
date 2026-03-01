"""
AI Trading Engine - Regelbasiertes Entscheidungssystem
Überschreibt manuelle Settings basierend auf Marktbedingungen
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    MANUAL = "manual"
    AI_CONSERVATIVE = "ai_conservative"
    AI_MODERATE = "ai_moderate"
    AI_AGGRESSIVE = "ai_aggressive"


class MarketRegime(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"


@dataclass
class MarketConditions:
    """Current market conditions for AI decision making"""
    regime: MarketRegime
    volatility_percentile: float  # 0-100, ATR relative to recent history
    momentum_score: float  # -100 to +100
    adx_value: float  # 0-100, trend strength
    rsi_value: float  # 0-100


@dataclass
class AccountState:
    """Current account state for risk management"""
    total_equity: float
    available_budget: float
    current_drawdown_pct: float  # Negative value, e.g., -5.2 means 5.2% drawdown
    open_positions_count: int
    today_pnl: float
    today_trades_count: int


@dataclass
class AIOverride:
    """Tracks what the AI changed from manual settings"""
    field: str
    manual_value: any
    ai_value: any
    reason: str


@dataclass
class AIDecision:
    """Complete AI trading decision"""
    should_trade: bool
    position_size_usdt: float
    stop_loss_pct: float
    take_profit_pct: float
    max_positions: int
    
    # Position Size Range (NEW)
    min_position_usdt: float = 0.0
    max_position_usdt: float = 0.0
    
    # Overrides tracking
    overrides: List[AIOverride] = field(default_factory=list)
    
    # Reasoning
    reasoning: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-100
    
    # Risk assessment
    risk_score: float = 0.0  # 0-100, higher = riskier
    
    def add_override(self, field: str, manual: any, ai: any, reason: str):
        self.overrides.append(AIOverride(field, manual, ai, reason))
        
    def add_reason(self, reason: str):
        self.reasoning.append(reason)


# ============ RISK PROFILE DEFINITIONS ============

RISK_PROFILES = {
    TradingMode.AI_CONSERVATIVE: {
        "name": "Konservativ",
        "description": "Längere Haltezeit, weniger Trades, engere Stops",
        # Base values (will be adjusted by market conditions)
        "base_position_pct": 2.0,       # % of budget per trade
        "max_position_pct": 3.0,        # Maximum position size
        "base_stop_loss_pct": 1.5,      # Stop loss distance (enger = schneller raus)
        "base_take_profit_rr": 3.0,     # Risk:Reward ratio (höher = länger halten)
        "max_positions": 2,
        # Regime restrictions
        "allowed_regimes": [MarketRegime.BULLISH],
        "min_adx": 20,                  # Minimum trend strength
        # Drawdown limits
        "max_drawdown_pct": 8.0,        # Pause trading if exceeded
        "drawdown_reduce_at": 4.0,      # Start reducing size at this drawdown
        # Volatility adjustments
        "high_volatility_reduce": 0.5,  # Multiply position by this if high vol
        "low_volatility_boost": 1.0,    # No boost for conservative
    },
    TradingMode.AI_MODERATE: {
        "name": "Moderat",
        "description": "Ausgewogener Ansatz, mittlere Haltezeit",
        "base_position_pct": 3.5,
        "max_position_pct": 5.0,
        "base_stop_loss_pct": 2.5,
        "base_take_profit_rr": 2.5,
        "max_positions": 3,
        "allowed_regimes": [MarketRegime.BULLISH, MarketRegime.SIDEWAYS],
        "min_adx": 15,
        "max_drawdown_pct": 12.0,
        "drawdown_reduce_at": 6.0,
        "high_volatility_reduce": 0.6,
        "low_volatility_boost": 1.2,
    },
    TradingMode.AI_AGGRESSIVE: {
        "name": "Aggressiv",
        "description": "Schnelles Trading, häufiger kaufen/verkaufen",
        "base_position_pct": 5.0,
        "max_position_pct": 8.0,
        "base_stop_loss_pct": 3.0,          # Engerer Stop Loss
        "base_take_profit_rr": 2.5,         # Höheres R:R = bessere Gewinn/Verlust Balance
        "max_positions": 5,
        "allowed_regimes": [MarketRegime.BULLISH, MarketRegime.SIDEWAYS],  # Kein BEARISH - zu riskant
        "min_adx": 5,                       # Niedrig - erlaubt auch schwache Trends
        "max_drawdown_pct": 20.0,
        "drawdown_reduce_at": 10.0,
        "high_volatility_reduce": 0.7,
        "low_volatility_boost": 1.5,
    }
}


class AITradingEngine:
    """
    Regelbasierte AI für Trading-Entscheidungen
    Überschreibt manuelle Settings basierend auf Marktbedingungen
    """
    
    def __init__(self):
        self.last_decision: Optional[AIDecision] = None
        self.decision_history: List[Dict] = []
    
    def make_decision(
        self,
        mode: TradingMode,
        market: MarketConditions,
        account: AccountState,
        manual_settings: Dict
    ) -> AIDecision:
        """
        Make a complete trading decision based on market conditions and account state.
        
        Args:
            mode: Current trading mode (manual or AI profile)
            market: Current market conditions
            account: Current account state
            manual_settings: User's manual settings (for override comparison)
        
        Returns:
            AIDecision with all parameters and override tracking
        """
        
        # Manual mode - return manual settings unchanged
        if mode == TradingMode.MANUAL:
            return AIDecision(
                should_trade=True,
                position_size_usdt=manual_settings.get('live_max_order_usdt', 50),
                stop_loss_pct=2.5,
                take_profit_pct=5.0,
                max_positions=manual_settings.get('max_positions', 3),
                confidence=100.0,
                reasoning=["Manual Mode - keine AI-Anpassungen"]
            )
        
        # Get risk profile
        profile = RISK_PROFILES.get(mode)
        if not profile:
            logger.error(f"Unknown trading mode: {mode}")
            return self._fallback_decision(manual_settings)
        
        decision = AIDecision(
            should_trade=True,
            position_size_usdt=0,
            stop_loss_pct=profile['base_stop_loss_pct'],
            take_profit_pct=profile['base_stop_loss_pct'] * profile['base_take_profit_rr'],
            max_positions=profile['max_positions'],
            confidence=80.0
        )
        
        decision.add_reason(f"AI Profil: {profile['name']}")
        
        # ============ REGIME CHECK ============
        if market.regime not in profile['allowed_regimes']:
            decision.should_trade = False
            decision.add_reason(f"❌ Regime {market.regime.value} nicht erlaubt für {profile['name']}")
            decision.confidence = 0
            return decision
        
        decision.add_reason(f"✅ Regime {market.regime.value} ist erlaubt")
        
        # ============ ADX CHECK ============
        if market.adx_value < profile['min_adx']:
            decision.should_trade = False
            decision.add_reason(f"❌ ADX {market.adx_value:.1f} < Minimum {profile['min_adx']}")
            decision.confidence = 0
            return decision
        
        decision.add_reason(f"✅ ADX {market.adx_value:.1f} zeigt ausreichend Trendstärke")
        
        # ============ DRAWDOWN CHECK ============
        abs_drawdown = abs(account.current_drawdown_pct)
        
        if abs_drawdown >= profile['max_drawdown_pct']:
            decision.should_trade = False
            decision.add_reason(f"🛑 Drawdown {abs_drawdown:.1f}% >= Max {profile['max_drawdown_pct']}% - Trading pausiert")
            decision.confidence = 0
            return decision
        
        # ============ CALCULATE POSITION SIZE ============
        base_position_pct = profile['base_position_pct']
        max_position_pct = profile['max_position_pct']
        position_multiplier = 1.0
        
        # Adjust for drawdown
        if abs_drawdown >= profile['drawdown_reduce_at']:
            drawdown_factor = 1 - ((abs_drawdown - profile['drawdown_reduce_at']) / 
                                   (profile['max_drawdown_pct'] - profile['drawdown_reduce_at']))
            position_multiplier *= max(0.3, drawdown_factor)
            decision.add_reason(f"📉 Drawdown-Anpassung: Position x{drawdown_factor:.2f}")
        
        # Adjust for volatility (0-100 percentile)
        if market.volatility_percentile > 70:
            # High volatility - reduce position
            vol_factor = profile['high_volatility_reduce']
            position_multiplier *= vol_factor
            decision.add_reason(f"📊 Hohe Volatilität ({market.volatility_percentile:.0f}%): Position x{vol_factor}")
        elif market.volatility_percentile < 30:
            # Low volatility - can increase slightly
            vol_factor = profile['low_volatility_boost']
            position_multiplier *= vol_factor
            decision.add_reason(f"📊 Niedrige Volatilität ({market.volatility_percentile:.0f}%): Position x{vol_factor}")
        
        # Adjust for momentum
        if market.momentum_score > 50:
            # Strong momentum - slightly larger position
            momentum_boost = 1 + (market.momentum_score - 50) / 200  # Max 1.25x
            position_multiplier *= momentum_boost
            decision.add_reason(f"🚀 Starkes Momentum ({market.momentum_score:.0f}): Position x{momentum_boost:.2f}")
        elif market.momentum_score < -20:
            # Negative momentum in allowed regime - reduce
            momentum_factor = 0.7
            position_multiplier *= momentum_factor
            decision.add_reason(f"⚠️ Schwaches Momentum ({market.momentum_score:.0f}): Position x{momentum_factor}")
        
        # Calculate final position size
        final_position_pct = min(base_position_pct * position_multiplier, max_position_pct)
        position_size_usdt = account.available_budget * (final_position_pct / 100)
        
        # Calculate Min/Max Position Range (NEW)
        min_position_usdt = account.available_budget * (base_position_pct * 0.5 / 100)  # Min with max reduction
        max_position_usdt = account.available_budget * (max_position_pct / 100)
        
        # Cap to available budget
        position_size_usdt = min(position_size_usdt, account.available_budget * 0.95)
        position_size_usdt = round(position_size_usdt, 2)
        min_position_usdt = round(min_position_usdt, 2)
        max_position_usdt = round(min(max_position_usdt, account.available_budget * 0.95), 2)
        
        decision.position_size_usdt = position_size_usdt
        decision.min_position_usdt = min_position_usdt
        decision.max_position_usdt = max_position_usdt
        decision.add_reason(f"💰 Position Size: ${position_size_usdt:.2f} (Range: ${min_position_usdt:.0f}-${max_position_usdt:.0f})")
        
        # ============ ADJUST STOP LOSS FOR VOLATILITY ============
        base_sl = profile['base_stop_loss_pct']
        if market.volatility_percentile > 60:
            # Wider stop for high volatility (max 1.5x multiplier)
            sl_multiplier = min(1.5, 1 + (market.volatility_percentile - 60) / 100)
            decision.stop_loss_pct = base_sl * sl_multiplier
            decision.add_reason(f"🎯 Stop Loss erweitert wegen Volatilität: {decision.stop_loss_pct:.1f}%")
        else:
            decision.stop_loss_pct = base_sl
        
        # Take profit based on R:R ratio
        decision.take_profit_pct = decision.stop_loss_pct * profile['base_take_profit_rr']
        decision.add_reason(f"🎯 Take Profit: {decision.take_profit_pct:.1f}% (R:R {profile['base_take_profit_rr']}:1)")
        
        # ============ MAX POSITIONS ADJUSTMENT ============
        base_max_pos = profile['max_positions']
        
        # Reduce max positions if in drawdown
        if abs_drawdown >= profile['drawdown_reduce_at']:
            decision.max_positions = max(1, base_max_pos - 1)
            decision.add_reason(f"📊 Max Positionen reduziert wegen Drawdown: {decision.max_positions}")
        else:
            decision.max_positions = base_max_pos
        
        # ============ TRACK OVERRIDES ============
        manual_position = manual_settings.get('live_max_order_usdt', 50)
        if abs(position_size_usdt - manual_position) > 5:
            decision.add_override(
                'position_size',
                f"${manual_position:.0f}",
                f"${position_size_usdt:.0f}",
                "AI-Anpassung basierend auf Marktbedingungen"
            )
        
        manual_max_pos = manual_settings.get('max_positions', 3)
        if decision.max_positions != manual_max_pos:
            decision.add_override(
                'max_positions',
                manual_max_pos,
                decision.max_positions,
                f"Angepasst für {profile['name']} Profil"
            )
        
        # ============ CALCULATE RISK SCORE ============
        risk_factors = [
            market.volatility_percentile / 100 * 30,  # Max 30 points for volatility
            abs_drawdown / profile['max_drawdown_pct'] * 25,  # Max 25 for drawdown
            (100 - market.adx_value) / 100 * 20,  # Max 20 for weak trend
            account.open_positions_count / decision.max_positions * 25  # Max 25 for position count
        ]
        decision.risk_score = min(100, sum(risk_factors))
        
        # Adjust confidence based on conditions
        decision.confidence = max(20, 100 - decision.risk_score)
        
        # Store decision
        self.last_decision = decision
        self.decision_history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'mode': mode.value,
            'should_trade': decision.should_trade,
            'position_size': decision.position_size_usdt,
            'confidence': decision.confidence,
            'risk_score': decision.risk_score
        })
        
        # Keep only last 100 decisions
        if len(self.decision_history) > 100:
            self.decision_history = self.decision_history[-100:]
        
        return decision
    
    def _fallback_decision(self, manual_settings: Dict) -> AIDecision:
        """Fallback to conservative manual settings if AI fails"""
        return AIDecision(
            should_trade=True,
            position_size_usdt=min(30, manual_settings.get('live_max_order_usdt', 30)),
            stop_loss_pct=2.0,
            take_profit_pct=4.0,
            max_positions=2,
            confidence=50.0,
            reasoning=["⚠️ Fallback zu konservativen Werten"]
        )
    
    def get_profile_info(self, mode: TradingMode) -> Dict:
        """Get information about a risk profile"""
        if mode == TradingMode.MANUAL:
            return {
                "name": "Manual",
                "description": "Deine eigenen Einstellungen",
                "features": ["Volle Kontrolle", "Keine AI-Anpassungen"]
            }
        
        profile = RISK_PROFILES.get(mode, {})
        return {
            "name": profile.get('name', 'Unknown'),
            "description": profile.get('description', ''),
            "features": [
                f"Position: {profile.get('base_position_pct', 0)}-{profile.get('max_position_pct', 0)}%",
                f"Max {profile.get('max_positions', 0)} Positionen",
                f"Stop Loss: {profile.get('base_stop_loss_pct', 0)}%",
                f"Max Drawdown: {profile.get('max_drawdown_pct', 0)}%",
                f"Max {profile.get('max_daily_trades', 0)} Trades/Tag"
            ]
        }


# Global instance
ai_engine = AITradingEngine()
