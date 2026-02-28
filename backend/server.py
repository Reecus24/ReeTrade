from fastapi import FastAPI, HTTPException, Depends, Request, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from auth import create_token, hash_password, verify_password, get_current_user
from models import (
    UserRegister, UserLogin, LoginResponse, SettingsUpdate,
    MexcKeysInput, MexcKeysStatus, StatusResponse, BacktestRequest, 
    BacktestResult, LiveConfirmRequest, Trade
)
from db_operations import Database
from worker import MultiUserTradingWorker
from mexc_client import MexcClient
from strategy import TradingStrategy
from risk_manager import RiskManager
from models import PaperAccount, Position

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
db = Database()
worker: MultiUserTradingWorker = None
worker_task: asyncio.Task = None
limiter = Limiter(key_func=get_remote_address)
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global worker, worker_task
    
    # Startup
    logger.info("Starting ReeTrade Terminal API")
    await db.initialize()
    
    # Start multi-user worker
    worker = MultiUserTradingWorker(db)
    worker_task = asyncio.create_task(worker.start())
    
    yield
    
    # Shutdown
    logger.info("Shutting down")
    if worker:
        await worker.stop()
    if worker_task:
        worker_task.cancel()
    db.close()

app = FastAPI(
    title="ReeTrade Terminal API",
    description="Multi-user automated SPOT trading bot for MEXC",
    version="2.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ AUTH ENDPOINTS ============

@app.post("/api/auth/register", response_model=LoginResponse)
async def register(data: UserRegister):
    """Register new user"""
    # Check if email exists
    existing = await db.get_user_by_email(data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    password_hash = hash_password(data.password)
    
    # Create user
    user_id = await db.create_user(data.email, password_hash)
    
    # Create token
    token = create_token(user_id, data.email)
    
    return LoginResponse(
        token=token,
        message="Registration successful",
        user={'email': data.email, 'user_id': user_id}
    )

@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, data: UserLogin):
    """Login with email and password"""
    # Get user
    user = await db.get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not verify_password(data.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create token
    token = create_token(user['_id'], user['email'])
    
    # Audit log
    await db.audit_log(
        user_id=user['_id'],
        action="LOGIN",
        details={'email': user['email']},
        ip_address=request.client.host if request.client else None
    )
    
    return LoginResponse(
        token=token,
        message="Login successful",
        user={'email': user['email'], 'user_id': user['_id']}
    )

# ============ BOT CONTROL ENDPOINTS ============

@app.post("/api/bot/start")
async def start_bot(current_user: dict = Depends(get_current_user)):
    """Start the trading bot for current user"""
    user_id = current_user['user_id']
    await db.update_settings(user_id, {'bot_running': True})
    await db.log(user_id, "INFO", "Bot started by user")
    return {"message": "Bot started", "status": "running"}

@app.post("/api/bot/stop")
async def stop_bot(current_user: dict = Depends(get_current_user)):
    """Stop the trading bot for current user"""
    user_id = current_user['user_id']
    await db.update_settings(user_id, {'bot_running': False})
    await db.log(user_id, "INFO", "Bot stopped by user")
    return {"message": "Bot stopped", "status": "stopped"}

@app.post("/api/bot/live/request")
async def request_live_mode(current_user: dict = Depends(get_current_user)):
    """Request to enable live trading"""
    user_id = current_user['user_id']
    await db.update_settings(user_id, {'live_requested': True})
    await db.log(user_id, "WARNING", "Live mode requested - awaiting confirmation")
    return {"message": "Live mode requested. Please confirm."}

@app.post("/api/bot/live/confirm")
@limiter.limit("3/minute")
async def confirm_live_mode(request: Request, body: LiveConfirmRequest, current_user: dict = Depends(get_current_user)):
    """Confirm live trading mode with password verification"""
    user_id = current_user['user_id']
    
    # Verify password
    user = await db.get_user_by_id(user_id)
    if not user or not verify_password(body.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Check if API keys are configured
    has_keys = await db.has_mexc_keys(user_id)
    if not has_keys:
        raise HTTPException(
            status_code=400,
            detail="MEXC API keys not configured. Please add your API keys in Settings first."
        )
    
    await db.update_settings(user_id, {
        'mode': 'live',
        'live_confirmed': True,
        'live_requested': False
    })
    await db.log(user_id, "WARNING", "LIVE MODE ENABLED - Real trading active!")    
    # Audit log
    await db.audit_log(
        user_id=user_id,
        action="LIVE_MODE_ENABLE",
        details={'mode': 'live', 'live_confirmed': True},
        ip_address=request.client.host if request.client else None
    )
    return {"message": "Live mode confirmed", "mode": "live"}

@app.post("/api/bot/live/disable")
async def disable_live_mode(current_user: dict = Depends(get_current_user)):
    """Disable live trading mode"""
    user_id = current_user['user_id']
    await db.update_settings(user_id, {
        'mode': 'paper',
        'live_confirmed': False,
        'live_requested': False
    })
    await db.log(user_id, "INFO", "Switched back to paper mode")
    return {"message": "Switched to paper mode", "mode": "paper"}

# ============ STATUS ENDPOINTS ============

@app.get("/api/status", response_model=StatusResponse)
async def get_status(current_user: dict = Depends(get_current_user)):
    """Get bot status for current user"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    account = await db.get_paper_account(user_id)
    keys_status = await db.get_mexc_keys_status(user_id)
    
    return StatusResponse(
        settings=settings,
        paper_account=account,
        heartbeat=settings.last_heartbeat,
        is_alive=True,
        mexc_keys_connected=keys_status['connected']
    )

@app.get("/api/logs")
async def get_logs(limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Get recent logs for current user"""
    user_id = current_user['user_id']
    logs = await db.get_logs(user_id, limit=limit)
    return {"logs": logs}

# ============ SETTINGS ENDPOINTS ============

@app.get("/api/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Get user settings"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    return settings

@app.put("/api/settings")
async def update_settings(updates: SettingsUpdate, current_user: dict = Depends(get_current_user)):
    """Update user settings"""
    user_id = current_user['user_id']
    
    # Convert to dict and remove None values
    updates_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    if not updates_dict:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    await db.update_settings(user_id, updates_dict)    
    # Audit log
    await db.audit_log(
        user_id=user_id,
        action="SETTINGS_UPDATE",
        details=updates_dict
    )
    await db.log(user_id, "INFO", "Settings updated", updates_dict)
    
    # Get updated settings
    settings = await db.get_settings(user_id)
    return {"message": "Settings updated", "settings": settings}

# ============ MEXC KEYS ENDPOINTS ============

@app.post("/api/keys/mexc")
async def set_mexc_keys(keys: MexcKeysInput, current_user: dict = Depends(get_current_user)):
    """Set MEXC API keys (encrypted storage)"""
    user_id = current_user['user_id']
    
    if not keys.api_key or not keys.api_secret:
        raise HTTPException(status_code=400, detail="Both API key and secret required")
    
    await db.set_mexc_keys(user_id, keys.api_key, keys.api_secret)    
    # Audit log
    await db.audit_log(
        user_id=user_id,
        action="KEYS_UPDATE",
        details={'keys_configured': True}
    )
    await db.log(user_id, "INFO", "MEXC API keys updated")
    
    return {"message": "MEXC keys saved securely", "connected": True}

@app.get("/api/keys/mexc/status", response_model=MexcKeysStatus)
async def get_mexc_keys_status(current_user: dict = Depends(get_current_user)):
    """Get MEXC keys connection status (no keys returned)"""
    user_id = current_user['user_id']
    status = await db.get_mexc_keys_status(user_id)
    return MexcKeysStatus(**status)

@app.delete("/api/keys/mexc")
async def delete_mexc_keys(current_user: dict = Depends(get_current_user)):
    """Delete MEXC API keys"""
    user_id = current_user['user_id']
    
    # Also disable live mode if active
    settings = await db.get_settings(user_id)
    if settings.mode == 'live':
        await db.update_settings(user_id, {
            'mode': 'paper',
            'live_confirmed': False,
            'live_requested': False
        })
    
    # Delete keys
    await db.user_keys.delete_one({'user_id': user_id})
    await db.log(user_id, "INFO", "MEXC API keys deleted")
    
    return {"message": "MEXC keys deleted"}

# ============ MARKET DATA ENDPOINTS ============

@app.get("/api/market/top_pairs")
async def get_top_pairs(current_user: dict = Depends(get_current_user)):
    """Get top trading pairs"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    return {
        "pairs": settings.top_pairs,
        "last_refresh": settings.last_pairs_refresh
    }

@app.get("/api/market/candles")
async def get_candles(
    symbol: str,
    interval: str = "15m",
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get candlestick data"""
    try:
        mexc = MexcClient()
        klines = await mexc.get_klines(symbol, interval, limit)
        return {"symbol": symbol, "klines": klines}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ BACKTEST ENDPOINT ============

@app.post("/api/backtest/run", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest, current_user: dict = Depends(get_current_user)):
    """Run backtest on historical data"""
    try:
        user_id = current_user['user_id']
        settings = await db.get_settings(user_id)
        mexc = MexcClient()
        strategy = TradingStrategy(
            ema_fast=settings.ema_fast,
            ema_slow=settings.ema_slow,
            rsi_period=settings.rsi_period,
            rsi_min=settings.rsi_min,
            rsi_overbought=settings.rsi_overbought
        )
        
        # Use top pairs or default
        test_symbols = settings.top_pairs[:5] if settings.top_pairs else ["BTCUSDT", "ETHUSDT"]
        
        trades = []
        for symbol in test_symbols:
            # Get 15m klines (last 500 = ~5 days)
            klines = await mexc.get_klines(symbol, "15m", 500)
            
            if len(klines) < settings.ema_slow:
                continue
            
            # Simple backtest: check signal at each candle
            for i in range(settings.ema_slow, len(klines), 4):  # Every hour
                signal, context = strategy.generate_signal(klines[:i])
                
                if signal == "LONG":
                    entry_price = float(klines[i][4])
                    # Simulate exit after 4 candles (1 hour)
                    if i + 4 < len(klines):
                        exit_price = float(klines[i+4][4])
                        pnl = (exit_price - entry_price) / entry_price * 100
                        
                        trades.append(Trade(
                            user_id=user_id,
                            ts=datetime.fromtimestamp(klines[i][0]/1000, tz=timezone.utc),
                            symbol=symbol,
                            side="BUY",
                            qty=1.0,
                            entry=entry_price,
                            exit=exit_price,
                            pnl=pnl,
                            mode="paper",
                            reason="Backtest"
                        ))
        
        # Calculate stats
        winning = [t for t in trades if t.pnl and t.pnl > 0]
        losing = [t for t in trades if t.pnl and t.pnl < 0]
        total_pnl = sum(t.pnl for t in trades if t.pnl)
        
        return BacktestResult(
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=total_pnl,
            win_rate=len(winning)/len(trades)*100 if trades else 0,
            max_drawdown=0,  # Simplified
            trades=trades
        )
        
    except Exception as e:
        logger.exception("Backtest error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api")
async def root():
    """Health check"""
    return {"message": "ReeTrade Terminal API", "status": "healthy"}
