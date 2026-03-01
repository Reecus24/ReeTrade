"""
AI Trading Engine V2 - Fully Dynamic & Adaptive
===============================================
- ATR-based Stop Loss & Take Profit
- Dynamic Risk Scaling based on performance
- Confidence-weighted position sizing
- Auto profile switching on drawdown
- Performance safety (loss streaks, daily limits)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    MANUAL = "manual"
    AI_CONSERVATIVE = "ai_conservative"
    AI_MODERATE = "ai_moderate"
    AI_AGGRESSIVE = "ai_aggressive"


class MarketRegime(str, Enum):
    BULLISH = "bullish"
    SIDEWAYS = "sideways"
    BEARISH = "bearish"


@dataclass
class MarketConditions:
    """Real-time market conditions for a symbol"""
    regime: MarketRegime
    adx_value: float
    atr_value: float  # Actual ATR value for SL/TP calculation
    atr_percent: float  # ATR as percentage of price
    volatility_percentile: float  # 0-100
    momentum_score: float  # -100 to +100
    rsi_value: float
    current_price: float
    volume_24h: float = 0  # 24h trading volume in USDT for low-cap detection


@dataclass
class AccountState:
    """Current account state for risk management"""
    total_equity: float
    usdt_free: float  # Available USDT in wallet
    current_drawdown_pct: float
    open_positions_count: int
    open_positions_value: float  # Total value in open positions
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    today_pnl: float = 0
    today_trades_count: int = 0
    is_paused: bool = False
    pause_until: Optional[datetime] = None
    current_profile: Optional[TradingMode] = None  # For auto-switching


@dataclass
class AIDecision:
    """AI trading decision with full transparency"""
    should_trade: bool
    position_size_usdt: float
    position_size_percent: float  # % of available USDT
    stop_loss_price: float
    stop_loss_pct: float
    take_profit_price: float
    take_profit_pct: float
    risk_reward_ratio: float
    confidence: float  # 0-100
    risk_score: float  # 0-100
    risk_per_trade_pct: float
    reasoning: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    profile_override: Optional[TradingMode] = None  # If auto-switched
    
    def add_reason(self, reason: str):
        self.reasoning.append(reason)
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)


# ============ AI PROFILE CONFIGURATIONS ============

RISK_PROFILES_V2 = {
    TradingMode.AI_AGGRESSIVE: {
        "name": "Aggressiv",
        "emoji": "🔴",
        "description": "Optimiert für hohe Trefferquote - Mehr realisierte Gewinne",
        
        # Position Sizing (% of available USDT)
        "position_pct_min": 15.0,
        "position_pct_max": 35.0,
        "max_positions": 5,
        
        # Risk per Trade
        "risk_pct_base": 5.0,  # 4-6%
        "risk_pct_min": 3.0,
        "risk_pct_max": 7.0,
        
        # ATR-based Stop Loss with MAX CAP - TIGHTER for higher win rate
        "sl_atr_multiplier_base": 2.0,  # 1.8-2.2x ATR (tighter)
        "sl_atr_multiplier_min": 1.8,
        "sl_atr_multiplier_max": 2.2,
        "sl_max_pct": 8.0,  # MAX 8% Stop Loss Cap (was 10%)
        
        # Low-Cap Coin Adjustments - STRICTER
        "lowcap_sl_reduction": 0.75,  # 75% of normal SL -> Max 6% for low-cap
        "lowcap_position_reduction": 0.5,  # 50% of normal position for low-cap
        "lowcap_volume_threshold": 500000,  # 24h Volume < $500k = low-cap
        
        # Take Profit (R:R ratio) - LOWER for higher win rate
        "tp_rr_base": 1.5,  # Minimum 1:1.5 (was 1:2.5)
        "tp_rr_max": 2.0,  # At strong momentum (was 1:3.5)
        
        # PARTIAL PROFIT TAKING - NEW!
        "partial_profit_enabled": True,
        "partial_profit_trigger_pct": 8.0,  # Trigger at +8%
        "partial_profit_close_pct": 50.0,  # Close 50% of position
        "partial_profit_move_sl_to_entry": True,  # Move SL to break-even after partial
        
        # Market Conditions - Accept ALL regimes for maximum opportunity scanning
        "allowed_regimes": [MarketRegime.BULLISH, MarketRegime.SIDEWAYS, MarketRegime.BEARISH],
        "min_adx": 15,  # Higher ADX threshold for stronger trends (was 5)
        "momentum_tp_boost_adx": 30,  # ADX > 30 = extend TP
        
        # Confidence Scaling
        "high_confidence_threshold": 85,
        "low_confidence_threshold": 60,
        
        # Drawdown Safety
        "risk_reduce_drawdown": 15.0,  # At 15% DD -> halve risk
        "profile_switch_drawdown": 25.0,  # At 25% DD -> switch to Moderate
        
        # ADX Risk Scaling
        "adx_risk_boost_threshold": 25,  # ADX > 25 -> increase risk
        "adx_risk_reduce_threshold": 15,  # ADX < 15 -> reduce risk
    },
    
    TradingMode.AI_MODERATE: {
        "name": "Moderat",
        "emoji": "🟡",
        "description": "Balanced Growth - Stabiles Wachstum mit Kontrolle",
        
        # Position Sizing
        "position_pct_min": 8.0,
        "position_pct_max": 18.0,
        "max_positions": 2,
        
        # Risk per Trade
        "risk_pct_base": 2.0,  # 1.5-2.5%
        "risk_pct_min": 1.5,
        "risk_pct_max": 3.0,
        
        # ATR-based Stop Loss with MAX CAP
        "sl_atr_multiplier_base": 1.8,
        "sl_atr_multiplier_min": 1.5,
        "sl_atr_multiplier_max": 2.0,
        "sl_max_pct": 6.0,  # MAX 6% Stop Loss Cap
        
        # Low-Cap Coin Adjustments
        "lowcap_sl_reduction": 0.5,  # 50% of normal SL for low-cap
        "lowcap_position_reduction": 0.4,  # 40% of normal position for low-cap
        "lowcap_volume_threshold": 1000000,  # 24h Volume < $1M = low-cap
        
        # Take Profit
        "tp_rr_base": 2.0,
        "tp_rr_max": 2.5,
        
        # Market Conditions
        "allowed_regimes": [MarketRegime.BULLISH, MarketRegime.SIDEWAYS],  # BULLISH + SIDEWAYS
        "min_adx": 10,
        "momentum_tp_boost_adx": 25,
        
        # Confidence Scaling
        "high_confidence_threshold": 80,
        "low_confidence_threshold": 65,
        
        # Drawdown Safety
        "risk_reduce_drawdown": 10.0,
        "profile_switch_drawdown": 20.0,  # Switch to Conservative
        
        # ADX Risk Scaling
        "adx_risk_boost_threshold": 25,
        "adx_risk_reduce_threshold": 15,
    },
    
    TradingMode.AI_CONSERVATIVE: {
        "name": "Konservativ",
        "emoji": "🟢",
        "description": "Capital Preservation - Kapitalschutz hat Priorität",
        
        # Position Sizing
        "position_pct_min": 3.0,
        "position_pct_max": 8.0,
        "max_positions": 2,
        
        # Risk per Trade
        "risk_pct_base": 0.75,  # 0.5-1%
        "risk_pct_min": 0.5,
        "risk_pct_max": 1.0,
        
        # ATR-based Stop Loss with MAX CAP
        "sl_atr_multiplier_base": 1.5,
        "sl_atr_multiplier_min": 1.2,
        "sl_atr_multiplier_max": 1.8,
        "sl_max_pct": 4.0,  # MAX 4% Stop Loss Cap
        
        # Low-Cap Coin Adjustments - very strict
        "lowcap_sl_reduction": 0.4,  # 40% of normal SL for low-cap
        "lowcap_position_reduction": 0.3,  # 30% of normal position for low-cap
        "lowcap_volume_threshold": 2000000,  # 24h Volume < $2M = low-cap
        
        # Take Profit
        "tp_rr_base": 1.5,
        "tp_rr_max": 2.0,
        
        # Market Conditions
        "allowed_regimes": [MarketRegime.BULLISH],  # Only clear Bullish
        "min_adx": 15,  # Must have clear trend
        "momentum_tp_boost_adx": 30,
        
        # Confidence Scaling - no high confidence boost
        "high_confidence_threshold": 90,
        "low_confidence_threshold": 70,
        
        # Drawdown Safety
        "risk_reduce_drawdown": 8.0,  # Very sensitive
        "profile_switch_drawdown": 15.0,  # Pause trading
        
        # ADX Risk Scaling
        "adx_risk_boost_threshold": 30,
        "adx_risk_reduce_threshold": 20,
    }
}


class AITradingEngineV2:
    """
    Advanced AI Trading Engine with:
    - Dynamic ATR-based SL/TP
    - Adaptive risk scaling
    - Performance tracking
    - Auto profile switching
    """
    
    def __init__(self):
        self.performance_tracker: Dict[str, Dict] = {}  # user_id -> performance data
    
    def get_user_performance(self, user_id: str) -> Dict:
        """Get or initialize user performance tracking"""
        if user_id not in self.performance_tracker:
            self.performance_tracker[user_id] = {
                'consecutive_losses': 0,
                'consecutive_wins': 0,
                'total_trades_today': 0,
                'pnl_today': 0,
                'last_trade_time': None,
                'paused_until': None,
                'auto_switched_profile': None,
                'risk_multiplier': 1.0,  # Dynamic risk adjustment
            }
        return self.performance_tracker[user_id]
    
    def update_performance(self, user_id: str, won: bool, pnl: float):
        """Update performance after a trade closes"""
        perf = self.get_user_performance(user_id)
        
        if won:
            perf['consecutive_wins'] += 1
            perf['consecutive_losses'] = 0
            
            # 3 wins in a row -> increase risk by 1%
            if perf['consecutive_wins'] >= 3:
                perf['risk_multiplier'] = min(1.5, perf['risk_multiplier'] + 0.1)
                perf['consecutive_wins'] = 0
        else:
            perf['consecutive_losses'] += 1
            perf['consecutive_wins'] = 0
            
            # 2 losses in a row -> halve risk
            if perf['consecutive_losses'] >= 2:
                perf['risk_multiplier'] = max(0.25, perf['risk_multiplier'] * 0.5)
            
            # 3 losses in a row -> pause for 1 hour
            if perf['consecutive_losses'] >= 3:
                perf['paused_until'] = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.warning(f"User {user_id}: 3 consecutive losses, pausing for 1 hour")
        
        perf['pnl_today'] += pnl
        perf['total_trades_today'] += 1
        perf['last_trade_time'] = datetime.now(timezone.utc)
    
    def is_trading_paused(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """Check if trading is paused for user"""
        perf = self.get_user_performance(user_id)
        
        if perf.get('paused_until'):
            if datetime.now(timezone.utc) < perf['paused_until']:
                remaining = (perf['paused_until'] - datetime.now(timezone.utc)).seconds // 60
                return True, f"Paused for {remaining} min (3 consecutive losses)"
            else:
                perf['paused_until'] = None
                perf['consecutive_losses'] = 0
        
        return False, None
    
    def calculate_confidence(
        self,
        market: MarketConditions,
        account: AccountState,
        profile: Dict
    ) -> float:
        """Calculate trade confidence score (0-100)"""
        confidence = 50.0  # Base
        
        # Regime confidence
        if market.regime == MarketRegime.BULLISH:
            confidence += 20
        elif market.regime == MarketRegime.SIDEWAYS:
            confidence += 5
        else:
            confidence -= 30
        
        # ADX confidence (trend strength)
        if market.adx_value >= 30:
            confidence += 15
        elif market.adx_value >= 20:
            confidence += 10
        elif market.adx_value >= 15:
            confidence += 5
        else:
            confidence -= 10
        
        # RSI confidence
        if 40 <= market.rsi_value <= 60:
            confidence += 5  # Neutral zone
        elif 30 <= market.rsi_value <= 70:
            confidence += 0
        else:
            confidence -= 10  # Overbought/oversold
        
        # Momentum confidence
        if market.momentum_score > 50:
            confidence += 10
        elif market.momentum_score > 20:
            confidence += 5
        elif market.momentum_score < -20:
            confidence -= 10
        
        # Account state confidence
        if account.current_drawdown_pct > 15:
            confidence -= 15
        elif account.current_drawdown_pct > 10:
            confidence -= 10
        elif account.current_drawdown_pct > 5:
            confidence -= 5
        
        # Position count confidence
        if account.open_positions_count >= profile['max_positions']:
            confidence -= 20
        elif account.open_positions_count >= profile['max_positions'] - 1:
            confidence -= 10
        
        return max(0, min(100, confidence))
    
    def calculate_risk_per_trade(
        self,
        user_id: str,
        market: MarketConditions,
        account: AccountState,
        profile: Dict,
        confidence: float
    ) -> float:
        """Calculate dynamic risk per trade"""
        perf = self.get_user_performance(user_id)
        
        base_risk = profile['risk_pct_base']
        
        # Apply performance multiplier
        risk = base_risk * perf.get('risk_multiplier', 1.0)
        
        # ADX-based adjustment
        if market.adx_value > profile['adx_risk_boost_threshold']:
            risk *= 1.2  # Increase risk in strong trends
        elif market.adx_value < profile['adx_risk_reduce_threshold']:
            risk *= 0.7  # Reduce risk in weak trends
        
        # Volatility adjustment
        if market.volatility_percentile > 80:
            risk *= 0.7  # Reduce in high volatility
        elif market.volatility_percentile < 20:
            risk *= 1.1  # Slightly increase in low volatility
        
        # Drawdown adjustment
        if account.current_drawdown_pct > profile['risk_reduce_drawdown']:
            risk *= 0.5  # Halve risk when near drawdown limit
        
        # Confidence adjustment
        if confidence < profile['low_confidence_threshold']:
            risk *= 0.5
        elif confidence > profile['high_confidence_threshold']:
            risk *= 1.2
        
        # Clamp to profile limits
        return max(profile['risk_pct_min'], min(profile['risk_pct_max'], risk))
    
    def calculate_position_size(
        self,
        market: MarketConditions,
        account: AccountState,
        profile: Dict,
        confidence: float,
        trading_budget_remaining: float
    ) -> Tuple[float, float]:
        """
        Calculate position size based on available USDT
        Returns: (position_size_usdt, position_percent)
        """
        available_usdt = account.usdt_free
        
        # Base position percent from profile
        base_pct = (profile['position_pct_min'] + profile['position_pct_max']) / 2
        
        # Confidence-based scaling
        if confidence >= profile['high_confidence_threshold']:
            # High confidence -> upper range
            position_pct = profile['position_pct_max']
        elif confidence >= profile['low_confidence_threshold']:
            # Normal confidence -> scale between min and mid
            conf_range = profile['high_confidence_threshold'] - profile['low_confidence_threshold']
            conf_position = (confidence - profile['low_confidence_threshold']) / conf_range
            position_pct = profile['position_pct_min'] + (base_pct - profile['position_pct_min']) * conf_position
        else:
            # Low confidence -> minimum or skip
            position_pct = profile['position_pct_min'] * 0.5
        
        # ADX-based adjustment
        if market.adx_value > 30:
            position_pct *= 1.15  # Boost in strong trends
        elif market.adx_value < 15:
            position_pct *= 0.8  # Reduce in weak trends
        
        # Clamp to profile limits
        position_pct = max(profile['position_pct_min'], min(profile['position_pct_max'], position_pct))
        
        # Calculate actual position size
        position_size = available_usdt * (position_pct / 100)
        
        # Apply trading budget cap
        position_size = min(position_size, trading_budget_remaining)
        
        # Recalculate actual percent
        actual_pct = (position_size / available_usdt * 100) if available_usdt > 0 else 0
        
        return position_size, actual_pct
    
    def is_low_cap_coin(self, market: MarketConditions, profile: Dict) -> bool:
        """Check if coin is low-cap based on 24h volume threshold"""
        volume_threshold = profile.get('lowcap_volume_threshold', 1000000)
        return market.volume_24h < volume_threshold and market.volume_24h > 0
    
    def calculate_atr_stop_loss(
        self,
        market: MarketConditions,
        profile: Dict
    ) -> Tuple[float, float, bool]:
        """
        Calculate ATR-based stop loss with MAX CAP
        Returns: (stop_loss_price, stop_loss_percent, is_low_cap)
        """
        # Base ATR multiplier
        atr_mult = profile['sl_atr_multiplier_base']
        
        # Volatility adjustment - tighter stop in high volatility
        if market.volatility_percentile > 70:
            atr_mult = profile['sl_atr_multiplier_min']
        elif market.volatility_percentile < 30:
            atr_mult = profile['sl_atr_multiplier_max']
        
        # Low-Cap Detection - apply tighter stop for volatile low-cap coins
        is_low_cap = self.is_low_cap_coin(market, profile)
        if is_low_cap:
            lowcap_reduction = profile.get('lowcap_sl_reduction', 0.5)
            atr_mult *= lowcap_reduction  # Reduce ATR multiplier
        
        # Calculate stop loss distance
        sl_distance = market.atr_value * atr_mult
        sl_pct = (sl_distance / market.current_price) * 100
        
        # Apply MAX STOP LOSS CAP
        sl_max_pct = profile.get('sl_max_pct', 10.0)
        if sl_pct > sl_max_pct:
            sl_pct = sl_max_pct
            sl_distance = market.current_price * (sl_pct / 100)
        
        sl_price = market.current_price - sl_distance
        
        return sl_price, sl_pct, is_low_cap
    
    def calculate_take_profit(
        self,
        market: MarketConditions,
        profile: Dict,
        sl_pct: float
    ) -> Tuple[float, float, float]:
        """
        Calculate take profit based on R:R ratio
        Returns: (take_profit_price, take_profit_percent, risk_reward_ratio)
        """
        # Base R:R ratio
        rr_ratio = profile['tp_rr_base']
        
        # Momentum-based extension
        if market.adx_value > profile['momentum_tp_boost_adx']:
            rr_ratio = profile['tp_rr_max']
        elif market.adx_value > 25:
            rr_ratio = (profile['tp_rr_base'] + profile['tp_rr_max']) / 2
        
        # Calculate take profit
        tp_pct = sl_pct * rr_ratio
        tp_distance = market.current_price * (tp_pct / 100)
        tp_price = market.current_price + tp_distance
        
        return tp_price, tp_pct, rr_ratio
    
    def check_auto_profile_switch(
        self,
        user_id: str,
        trading_mode: TradingMode,
        account: AccountState,
        profile: Dict
    ) -> Optional[TradingMode]:
        """Check if profile should auto-switch due to drawdown"""
        perf = self.get_user_performance(user_id)
        
        # Check drawdown threshold
        if account.current_drawdown_pct >= profile.get('profile_switch_drawdown', 100):
            if trading_mode == TradingMode.AI_AGGRESSIVE:
                perf['auto_switched_profile'] = TradingMode.AI_MODERATE
                return TradingMode.AI_MODERATE
            elif trading_mode == TradingMode.AI_MODERATE:
                perf['auto_switched_profile'] = TradingMode.AI_CONSERVATIVE
                return TradingMode.AI_CONSERVATIVE
            elif trading_mode == TradingMode.AI_CONSERVATIVE:
                # Pause trading
                perf['paused_until'] = datetime.now(timezone.utc) + timedelta(hours=4)
                return None
        
        return None
    
    def make_decision(
        self,
        user_id: str,
        trading_mode: TradingMode,
        market: MarketConditions,
        account: AccountState,
        trading_budget_remaining: float
    ) -> AIDecision:
        """
        Make a comprehensive AI trading decision
        """
        profile = RISK_PROFILES_V2.get(trading_mode)
        if not profile:
            return AIDecision(
                should_trade=False,
                position_size_usdt=0,
                position_size_percent=0,
                stop_loss_price=0,
                stop_loss_pct=0,
                take_profit_price=0,
                take_profit_pct=0,
                risk_reward_ratio=0,
                confidence=0,
                risk_score=0,
                risk_per_trade_pct=0,
                reasoning=["Invalid trading mode"]
            )
        
        decision = AIDecision(
            should_trade=True,
            position_size_usdt=0,
            position_size_percent=0,
            stop_loss_price=0,
            stop_loss_pct=0,
            take_profit_price=0,
            take_profit_pct=0,
            risk_reward_ratio=0,
            confidence=0,
            risk_score=50,
            risk_per_trade_pct=0
        )
        
        decision.add_reason(f"{profile['emoji']} Profil: {profile['name']}")
        
        # ============ CHECK TRADING PAUSED ============
        is_paused, pause_reason = self.is_trading_paused(user_id)
        if is_paused:
            decision.should_trade = False
            decision.add_reason(f"⏸️ {pause_reason}")
            return decision
        
        # ============ CHECK AUTO PROFILE SWITCH ============
        new_profile = self.check_auto_profile_switch(user_id, trading_mode, account, profile)
        if new_profile:
            decision.profile_override = new_profile
            profile = RISK_PROFILES_V2[new_profile]
            decision.add_warning(f"⚠️ Auto-Switch zu {profile['name']} wegen Drawdown")
        elif new_profile is None and account.current_drawdown_pct >= profile.get('profile_switch_drawdown', 100):
            decision.should_trade = False
            decision.add_reason(f"🛑 Trading pausiert - Drawdown {account.current_drawdown_pct:.1f}% zu hoch")
            return decision
        
        # ============ CHECK REGIME ============
        if market.regime not in profile['allowed_regimes']:
            decision.should_trade = False
            decision.add_reason(f"❌ Regime {market.regime.value.upper()} nicht erlaubt für {profile['name']}")
            return decision
        decision.add_reason(f"✓ Regime: {market.regime.value.upper()}")
        
        # ============ CHECK ADX ============
        if market.adx_value < profile['min_adx']:
            decision.should_trade = False
            decision.add_reason(f"❌ ADX {market.adx_value:.1f} < Minimum {profile['min_adx']}")
            return decision
        decision.add_reason(f"✓ ADX: {market.adx_value:.1f}")
        
        # ============ CHECK POSITION COUNT ============
        if account.open_positions_count >= profile['max_positions']:
            decision.should_trade = False
            decision.add_reason(f"❌ Max Positionen erreicht ({account.open_positions_count}/{profile['max_positions']})")
            return decision
        
        # ============ CALCULATE CONFIDENCE ============
        confidence = self.calculate_confidence(market, account, profile)
        decision.confidence = confidence
        
        # Check minimum confidence
        if confidence < 50:
            decision.should_trade = False
            decision.add_reason(f"❌ Confidence {confidence:.0f}% zu niedrig (Min: 50%)")
            return decision
        
        decision.add_reason(f"✓ Confidence: {confidence:.0f}%")
        
        # ============ CALCULATE RISK PER TRADE ============
        risk_pct = self.calculate_risk_per_trade(user_id, market, account, profile, confidence)
        decision.risk_per_trade_pct = risk_pct
        decision.add_reason(f"📊 Risk/Trade: {risk_pct:.2f}%")
        
        # ============ CALCULATE POSITION SIZE ============
        position_size, position_pct = self.calculate_position_size(
            market, account, profile, confidence, trading_budget_remaining
        )
        
        # ============ CALCULATE ATR-BASED STOP LOSS WITH MAX CAP ============
        sl_price, sl_pct, is_low_cap = self.calculate_atr_stop_loss(market, profile)
        
        # Apply low-cap position reduction
        if is_low_cap:
            lowcap_reduction = profile.get('lowcap_position_reduction', 0.5)
            position_size *= lowcap_reduction
            position_pct *= lowcap_reduction
            decision.add_warning(f"⚠️ Low-Cap Coin erkannt (Vol: ${market.volume_24h/1000:.0f}K) → Position reduziert")
        
        decision.position_size_usdt = round(position_size, 2)
        decision.position_size_percent = round(position_pct, 1)
        
        if position_size < 5:  # Minimum order
            decision.should_trade = False
            decision.add_reason(f"❌ Position ${position_size:.2f} unter Minimum $5")
            return decision
        
        decision.add_reason(f"💰 Position: ${position_size:.2f} ({position_pct:.1f}% vom USDT)")
        
        # Stop Loss info with cap indicator
        sl_max_pct = profile.get('sl_max_pct', 10.0)
        sl_capped = sl_pct >= sl_max_pct * 0.99  # Check if we hit the cap
        sl_label = f"-{sl_pct:.2f}%"
        if sl_capped:
            sl_label += f" (MAX CAP {sl_max_pct:.0f}%)"
        elif is_low_cap:
            sl_label += " (Low-Cap enger)"
        else:
            sl_label += f" ({profile['sl_atr_multiplier_base']:.1f}x ATR)"
        
        decision.stop_loss_price = round(sl_price, 8)
        decision.stop_loss_pct = round(sl_pct, 2)
        decision.add_reason(f"🛑 Stop Loss: {sl_label}")
        
        # ============ CALCULATE TAKE PROFIT ============
        tp_price, tp_pct, rr_ratio = self.calculate_take_profit(market, profile, sl_pct)
        decision.take_profit_price = round(tp_price, 8)
        decision.take_profit_pct = round(tp_pct, 2)
        decision.risk_reward_ratio = round(rr_ratio, 1)
        decision.add_reason(f"🎯 Take Profit: +{tp_pct:.2f}% (R:R {rr_ratio:.1f}:1)")
        
        # ============ CALCULATE RISK SCORE ============
        risk_score = 50
        risk_score += (account.current_drawdown_pct * 2)  # Higher drawdown = higher risk
        risk_score += (100 - confidence) * 0.3  # Lower confidence = higher risk
        risk_score += (market.volatility_percentile * 0.2)  # Higher volatility = higher risk
        decision.risk_score = max(0, min(100, risk_score))
        
        return decision
    
    def get_profile_summary(
        self,
        trading_mode: TradingMode,
        usdt_free: float,
        trading_budget_remaining: float
    ) -> Dict:
        """Get profile summary for UI display"""
        profile = RISK_PROFILES_V2.get(trading_mode)
        if not profile:
            return {}
        
        # Calculate example position sizes
        min_pos = usdt_free * (profile['position_pct_min'] / 100)
        max_pos = usdt_free * (profile['position_pct_max'] / 100)
        
        # Apply trading budget cap
        min_pos = min(min_pos, trading_budget_remaining)
        max_pos = min(max_pos, trading_budget_remaining)
        
        return {
            'mode': trading_mode.value,
            'name': profile['name'],
            'emoji': profile['emoji'],
            'description': profile['description'],
            'position_pct_range': f"{profile['position_pct_min']:.0f}%-{profile['position_pct_max']:.0f}%",
            'position_usd_min': round(min_pos, 2),
            'position_usd_max': round(max_pos, 2),
            'max_positions': profile['max_positions'],
            'risk_per_trade': f"{profile['risk_pct_min']:.1f}%-{profile['risk_pct_max']:.1f}%",
            'sl_atr_multiplier': f"{profile['sl_atr_multiplier_min']:.1f}x-{profile['sl_atr_multiplier_max']:.1f}x ATR",
            'tp_rr_range': f"1:{profile['tp_rr_base']:.1f} - 1:{profile['tp_rr_max']:.1f}",
            'allowed_regimes': [r.value for r in profile['allowed_regimes']],
            'min_adx': profile['min_adx'],
        }


# Global instance
ai_engine_v2 = AITradingEngineV2()
