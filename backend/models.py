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
    
    # ========== TRADING MODE ==========
    # Simplified: Only RL-AI or Manual
    trading_mode: Literal["manual", "rl_ai", "ai_conservative", "ai_moderate", "ai_aggressive", "ki_explorer"] = "rl_ai"
    
    # ========== MARKET TYPE (SPOT vs FUTURES) ==========
    market_type: Literal["spot", "futures", "auto"] = "spot"  # auto = AI decides
    
    # ========== FUTURES SETTINGS ==========
    futures_enabled: bool = False
    futures_default_leverage: int = 5  # Default leverage (2-20)
    futures_max_leverage: int = 10  # Maximum allowed leverage
    futures_risk_per_trade: float = 0.02  # 2% risk per trade for futures
    futures_margin_mode: Literal["isolated", "cross"] = "isolated"
    futures_allow_shorts: bool = True  # Allow short positions
    
    # AI Override Tracking (for UI display)
    ai_last_override: Optional[dict] = None  # Last AI decision details
    ai_confidence: Optional[float] = None
    ai_risk_score: Optional[float] = None
    ai_reasoning: Optional[List[str]] = None
    ai_min_position: Optional[float] = None  # Min position size (NEW)
    ai_max_position: Optional[float] = None  # Max position size (NEW)
    ai_current_position: Optional[float] = None  # Current calculated position (NEW)
    
    # SEPARATE RUNNING STATES
    paper_running: bool = False
    live_running: bool = False
    live_requested: bool = False
    live_confirmed: bool = False
    
    # Legacy field for backwards compatibility
    mode: Literal["paper", "live"] = "paper"
    bot_running: bool = False
    
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
    cooldown_candles: int = 3
    min_notional_usdt: float = 10.0
    
    # ========== PAPER MODE SETTINGS ==========
    paper_start_balance_usdt: float = 500.0
    paper_daily_cap_usdt: float = 200.0  # Daily trading limit
    paper_max_order_usdt: float = 50.0  # Max order size
    paper_fee_bps: int = 10  # 0.1%
    paper_slippage_bps: int = 5  # 0.05%
    
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
    paper_heartbeat: Optional[datetime] = None
    live_heartbeat: Optional[datetime] = None
    
    # ========== COIN SELECTION ==========
    selected_spot_coins: List[str] = Field(default_factory=list)  # User selected SPOT coins
    selected_futures_coins: List[str] = Field(default_factory=list)  # User selected FUTURES coins
    spot_trade_all: bool = True  # Trade all available SPOT coins
    futures_trade_all: bool = True  # Trade all available FUTURES coins
    
    # ========== BOT STATUS TRACKING (Paper) ==========
    paper_last_scan: Optional[str] = None
    paper_last_decision: Optional[str] = None
    paper_last_regime: Optional[str] = None
    paper_last_symbol: Optional[str] = None
    paper_budget_used: Optional[float] = None
    paper_budget_available: Optional[float] = None
    paper_daily_used: Optional[float] = None
    paper_daily_remaining: Optional[float] = None
    paper_positions_count: Optional[int] = None
    
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
    trading_mode: Optional[Literal["manual", "ai_conservative", "ai_moderate", "ai_aggressive", "ki_explorer"]] = None
    
    # Market Type (SPOT vs FUTURES)
    market_type: Optional[Literal["spot", "futures", "auto"]] = None
    
    # Futures Settings
    futures_enabled: Optional[bool] = None
    futures_default_leverage: Optional[int] = None
    futures_max_leverage: Optional[int] = None
    futures_risk_per_trade: Optional[float] = None
    futures_margin_mode: Optional[Literal["isolated", "cross"]] = None
    futures_allow_shorts: Optional[bool] = None
    
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
    cooldown_candles: Optional[int] = None
    min_notional_usdt: Optional[float] = None
    
    # Paper Settings
    paper_start_balance_usdt: Optional[float] = None
    paper_daily_cap_usdt: Optional[float] = None
    paper_max_order_usdt: Optional[float] = None
    paper_fee_bps: Optional[int] = None
    paper_slippage_bps: Optional[int] = None
    
    # Live Settings
    reserve_usdt: Optional[float] = None
    trading_budget_usdt: Optional[float] = None
    live_daily_cap_usdt: Optional[float] = None
    live_max_order_usdt: Optional[float] = None
    live_min_notional_usdt: Optional[float] = None
    
    # Coin Selection
    selected_spot_coins: Optional[List[str]] = None
    selected_futures_coins: Optional[List[str]] = None
    spot_trade_all: Optional[bool] = None
    futures_trade_all: Optional[bool] = None
    
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
    
    # Market Type
    market_type: Literal["spot", "futures"] = "spot"
    
    # Futures-specific fields
    leverage: Optional[int] = None  # Only for futures
    margin_mode: Optional[Literal["isolated", "cross"]] = None
    liquidation_price: Optional[float] = None
    margin_used: Optional[float] = None  # USDT margin locked
    unrealized_pnl: Optional[float] = None
    roe_pct: Optional[float] = None  # Return on Equity %
    
    # Partial Profit Tracking
    original_qty: Optional[float] = None  # Original quantity before partial sell
    partial_profit_taken: bool = False  # Has partial profit been taken?
    partial_profit_time: Optional[datetime] = None  # When partial was taken
    sl_moved_to_entry: bool = False  # Has SL been moved to break-even?

class PaperAccount(BaseModel):
    user_id: str
    equity: float = 10000.0  # Start with $10k
    cash: float = 10000.0
    open_positions: List[Position] = Field(default_factory=list)

class Trade(BaseModel):
    user_id: str
    ts: datetime
    symbol: str
    side: Literal["BUY", "SELL"]
    qty: float
    entry: float
    exit: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None  # PnL percentage
    fees_paid: Optional[float] = None  # Total fees (entry + exit)
    slippage_cost: Optional[float] = None  # Slippage cost
    mode: Literal["paper", "live"] = "paper"
    reason: Optional[str] = None
    notional: Optional[float] = None  # Position notional value

class DailyMetrics(BaseModel):
    user_id: str
    date: str
    pnl: float
    drawdown: float
    trades_count: int

# ============ RESPONSE MODELS ============

class StatusResponse(BaseModel):
    settings: UserSettings
    paper_account: Optional[PaperAccount] = None
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
