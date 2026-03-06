from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal
from datetime import datetime
import uuid

# ============ AUTH MODELS ============

class UserRegister(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    token: str
    message: str
    user: dict

class User(BaseModel):
    email: EmailStr
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

# ============ SETTINGS MODELS ============

class UserSettings(BaseModel):
    user_id: str
    
    # ========== TRADING MODE (SIMPLIFIED: Only RL-AI) ==========
    trading_mode: Literal["manual", "rl_ai"] = "rl_ai"
    
    # AI Override Tracking (for UI display)
    ai_last_override: Optional[dict] = None
    ai_confidence: Optional[float] = None
    ai_risk_score: Optional[float] = None
    ai_reasoning: Optional[List[str]] = None
    ai_min_position: Optional[float] = None
    ai_max_position: Optional[float] = None
    ai_current_position: Optional[float] = None
    
    # LIVE MODE ONLY
    live_running: bool = False
    live_requested: bool = False
    live_confirmed: bool = False
    
    # ========== SHARED STRATEGY PARAMETERS ==========
    ema_fast: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_min: int = 50
    rsi_overbought: int = 75
    
    # ========== SHARED RISK PARAMETERS ==========
    risk_per_trade: float = 0.01  # 1%
    max_positions: int = 3
    max_daily_loss: float = 0.03  # 3%
    take_profit_rr: float = 2.0  # Risk:Reward
    atr_stop: bool = False
    atr_mult: float = 1.5
    min_notional_usdt: float = 10.0
    
    # ========== LIVE MODE SETTINGS ==========
    reserve_usdt: float = 0.0  # Safety reserve
    trading_budget_usdt: float = 500.0  # Max total exposure
    live_daily_cap_usdt: float = 200.0  # Daily trading limit
    live_max_order_usdt: float = 50.0  # Max order size
    live_min_notional_usdt: float = 10.0  # Min order size for live
    
    # Legacy (for backwards compat)
    fee_bps: int = 10
    slippage_bps: int = 5
    max_order_notional_usdt: Optional[float] = 50.0
    
    # Market data
    top_pairs: List[str] = Field(default_factory=list)
    all_pairs: List[str] = Field(default_factory=list)  # All coins for batch rotation
    last_pairs_refresh: Optional[datetime] = None
    live_heartbeat: Optional[datetime] = None
    
    # ========== COIN SELECTION ==========
    selected_spot_coins: List[str] = Field(default_factory=list)  # User selected SPOT coins
    spot_trade_all: bool = True  # Trade all available SPOT coins
    
    # ========== BOT STATUS TRACKING (Live) ==========
    live_last_scan: Optional[str] = None
    live_last_decision: Optional[str] = None
    live_last_regime: Optional[str] = None
    live_last_symbol: Optional[str] = None
    live_budget_used: Optional[float] = None
    live_budget_available: Optional[float] = None
    live_daily_used: Optional[float] = None
    live_daily_remaining: Optional[float] = None
    live_positions_count: Optional[int] = None

class SettingsUpdate(BaseModel):
    # Trading Mode
    trading_mode: Optional[Literal["manual", "rl_ai"]] = None
    
    # Strategy (shared)
    ema_fast: Optional[int] = None
    ema_slow: Optional[int] = None
    rsi_period: Optional[int] = None
    rsi_min: Optional[int] = None
    rsi_overbought: Optional[int] = None
    
    # Risk (shared)
    risk_per_trade: Optional[float] = None
    max_positions: Optional[int] = None
    max_daily_loss: Optional[float] = None
    take_profit_rr: Optional[float] = None
    atr_stop: Optional[bool] = None
    atr_mult: Optional[float] = None
    min_notional_usdt: Optional[float] = None
    
    # Live Settings
    reserve_usdt: Optional[float] = None
    trading_budget_usdt: Optional[float] = None
    live_daily_cap_usdt: Optional[float] = None
    live_max_order_usdt: Optional[float] = None
    live_min_notional_usdt: Optional[float] = None
    max_notional_usdt: Optional[float] = None  # Alias for max order
    
    # Coin Selection
    selected_spot_coins: Optional[List[str]] = None
    spot_trade_all: Optional[bool] = None
    
    # Legacy
    fee_bps: Optional[int] = None
    slippage_bps: Optional[int] = None
    max_order_notional_usdt: Optional[float] = None

# ============ KEYS MODELS ============

class MexcKeysInput(BaseModel):
    api_key: str
    api_secret: str

class MexcKeysStatus(BaseModel):
    connected: bool
    last_updated: Optional[datetime] = None
    error: Optional[str] = None

# ============ TRADING MODELS ============

class LogEntry(BaseModel):
    user_id: str
    ts: datetime
    level: Literal["INFO", "WARNING", "ERROR", "DEBUG"]
    msg: str
    context: Optional[dict] = None

class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])  # Unique ID
    symbol: str
    side: Literal["LONG", "SHORT"]
    entry_price: float
    qty: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    
    # Partial Profit Tracking
    original_qty: Optional[float] = None  # Original quantity before partial sell
    partial_profit_taken: bool = False  # Has partial profit been taken?
    partial_profit_time: Optional[datetime] = None  # When partial was taken
    sl_moved_to_entry: bool = False  # Has SL been moved to break-even?
    
    # ============ ORDERBOOK & MFE/MAE TRACKING ============
    # Orderbook at entry
    spread_at_entry: Optional[float] = None
    orderbook_imbalance_at_entry: Optional[float] = None
    
    # MFE/MAE Tracking (updated during position lifetime)
    max_price_seen: Optional[float] = None  # Highest price during trade
    min_price_seen: Optional[float] = None  # Lowest price during trade
    
    # AI Context at entry
    epsilon_at_entry: Optional[float] = None
    q_value_at_entry: Optional[float] = None

class LiveAccount(BaseModel):
    user_id: str
    equity: float = 0.0
    cash: float = 0.0
    open_positions: List[Position] = Field(default_factory=list)

# Alias for backwards compatibility
PaperAccount = LiveAccount

class Trade(BaseModel):
    user_id: str
    ts: datetime
    symbol: str
    side: Literal["BUY", "SELL"]
    qty: float
    entry: float
    exit: Optional[float] = None
    pnl: Optional[float] = None  # NET PnL after costs
    pnl_pct: Optional[float] = None  # NET PnL percentage
    fees_paid: Optional[float] = None  # Total fees (entry + exit)
    slippage_cost: Optional[float] = None  # Slippage cost
    mode: Literal["live"] = "live"  # Only live mode
    reason: Optional[str] = None  # Exit reason: ai_exit, time_limit, emergency_sl, manual
    notional: Optional[float] = None  # Position notional value
    
    # Extended fields
    duration_seconds: Optional[float] = None  # Hold duration
    gross_pnl: Optional[float] = None  # PnL before costs
    gross_pnl_pct: Optional[float] = None  # Gross PnL percentage
    
    # ============ ORDERBOOK & MARKET CONTEXT ============
    spread_at_entry: Optional[float] = None  # Bid-Ask Spread %
    orderbook_imbalance: Optional[float] = None  # bid_vol / ask_vol
    bid_volume_sum: Optional[float] = None  # Sum of top 5 bids
    ask_volume_sum: Optional[float] = None  # Sum of top 5 asks
    mid_price_at_entry: Optional[float] = None
    volatility_at_entry: Optional[float] = None  # 1m realized volatility
    
    # Microtrend at entry
    return_30s_at_entry: Optional[float] = None
    return_60s_at_entry: Optional[float] = None
    return_180s_at_entry: Optional[float] = None
    
    # ============ MFE/MAE TRACKING ============
    max_price_during_trade: Optional[float] = None
    min_price_during_trade: Optional[float] = None
    mfe: Optional[float] = None  # Max Favorable Excursion %
    mae: Optional[float] = None  # Max Adverse Excursion %
    
    # AI context
    epsilon_at_trade: Optional[float] = None
    exit_reason_category: Optional[str] = None  # ai_exit, time_limit, emergency_sl, stop_loss, take_profit, manual
    q_value_at_entry: Optional[float] = None  # Q-Value when trade was opened
    model_version: Optional[str] = None

class DailyMetrics(BaseModel):
    user_id: str
    date: str
    pnl: float
    drawdown: float
    trades_count: int

# ============ RESPONSE MODELS ============

class StatusResponse(BaseModel):
    settings: UserSettings
    live_account: Optional[LiveAccount] = None
    heartbeat: Optional[datetime] = None
    is_alive: bool = True
    mexc_keys_connected: bool = False

class BacktestRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
class BacktestResult(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    max_drawdown: float
    trades: List[Trade]

class LiveConfirmRequest(BaseModel):
    password: str

class AuditLogEntry(BaseModel):
    user_id: str
    ts: datetime
    action: str  # LOGIN, SETTINGS_UPDATE, KEYS_UPDATE, LIVE_MODE_ENABLE, TRADE_EXECUTED
    details: Optional[dict] = None
    ip_address: Optional[str] = None

class SymbolTradingPause(BaseModel):
    user_id: str
    symbol: str
    pause_until: datetime
    reason: str
    consecutive_losses: int
