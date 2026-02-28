from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    token: str
    message: str

class BotSettings(BaseModel):
    mode: Literal["paper", "live"] = "paper"
    bot_running: bool = False
    live_requested: bool = False
    live_confirmed: bool = False
    
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
    
    # Fees
    fee_bps: int = 10  # 0.1%
    slippage_bps: int = 5  # 0.05%
    
    # Market data
    top_pairs: List[str] = Field(default_factory=list)
    last_pairs_refresh: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None

class LogEntry(BaseModel):
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
    equity: float = 10000.0  # Start with $10k
    cash: float = 10000.0
    open_positions: List[Position] = Field(default_factory=list)

class Trade(BaseModel):
    ts: datetime
    symbol: str
    side: Literal["BUY", "SELL"]
    qty: float
    entry: float
    exit: Optional[float] = None
    pnl: Optional[float] = None
    mode: Literal["paper", "live"] = "paper"
    reason: Optional[str] = None

class DailyMetrics(BaseModel):
    date: str
    pnl: float
    drawdown: float
    trades_count: int

class StatusResponse(BaseModel):
    settings: BotSettings
    paper_account: Optional[PaperAccount] = None
    heartbeat: Optional[datetime] = None
    is_alive: bool = True

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
