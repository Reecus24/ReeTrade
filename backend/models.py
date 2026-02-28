from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

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
    
    # SEPARATE RUNNING STATES
    paper_running: bool = False
    live_running: bool = False
    live_requested: bool = False
    live_confirmed: bool = False
    
    # Legacy field for backwards compatibility (will be removed)
    mode: Literal["paper", "live"] = "paper"
    bot_running: bool = False
    
    # Strategy parameters
    ema_fast: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_min: int = 50
    rsi_overbought: int = 75
    
    # Risk parameters
    risk_per_trade: float = 0.01  # 1%
    max_positions: int = 3
    max_daily_loss: float = 0.03  # 3%
    take_profit_rr: float = 2.0  # Risk:Reward
    atr_stop: bool = False
    atr_mult: float = 1.5
    cooldown_candles: int = 3  # Wait N candles after trade
    
    # Fees
    fee_bps: int = 10  # 0.1%
    slippage_bps: int = 5  # 0.05%
    
    # Order Sizing
    min_notional_usdt: float = 10.0  # Minimum position size in USDT
    
    # Budget & Reserve System
    reserve_usdt: float = 0.0  # Safety reserve - bot won't touch this amount
    trading_budget_usdt: float = 500.0  # Max total exposure allowed (absolute cap)
    paper_start_balance_usdt: float = 500.0  # Paper mode starting balance
    max_order_notional_usdt: Optional[float] = 50.0  # Max single order size
    
    # Market data
    top_pairs: List[str] = Field(default_factory=list)
    last_pairs_refresh: Optional[datetime] = None
    paper_heartbeat: Optional[datetime] = None
    live_heartbeat: Optional[datetime] = None

class SettingsUpdate(BaseModel):
    # Strategy
    ema_fast: Optional[int] = None
    ema_slow: Optional[int] = None
    rsi_period: Optional[int] = None
    rsi_min: Optional[int] = None
    rsi_overbought: Optional[int] = None
    
    # Risk
    risk_per_trade: Optional[float] = None
    max_positions: Optional[int] = None
    max_daily_loss: Optional[float] = None
    take_profit_rr: Optional[float] = None
    atr_stop: Optional[bool] = None
    atr_mult: Optional[float] = None
    cooldown_candles: Optional[int] = None
    
    # Fees
    fee_bps: Optional[int] = None
    slippage_bps: Optional[int] = None
    
    # Order Sizing
    min_notional_usdt: Optional[float] = None
    
    # Budget & Reserve System
    reserve_usdt: Optional[float] = None
    trading_budget_usdt: Optional[float] = None
    paper_start_balance_usdt: Optional[float] = None
    max_order_notional_usdt: Optional[float] = None

# ============ KEYS MODELS ============

class MexcKeysInput(BaseModel):
    api_key: str
    api_secret: str

class MexcKeysStatus(BaseModel):
    connected: bool
    last_updated: Optional[datetime] = None

# ============ TRADING MODELS ============

class LogEntry(BaseModel):
    user_id: str
    ts: datetime
    level: Literal["INFO", "WARNING", "ERROR", "DEBUG"]
    msg: str
    context: Optional[dict] = None

class Position(BaseModel):
    symbol: str
    side: Literal["LONG", "SHORT"]
    entry_price: float
    qty: float
    stop_loss: float
    take_profit: float
    entry_time: datetime

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
