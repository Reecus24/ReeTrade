from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta

from auth import create_session, verify_admin_password, require_auth
from models import (
    LoginRequest, LoginResponse, StatusResponse, BacktestRequest, 
    BacktestResult, LiveConfirmRequest, Trade
)
from db_operations import Database
from worker import TradingWorker
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
worker: TradingWorker = None
worker_task: asyncio.Task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global worker, worker_task
    
    # Startup
    logger.info("Starting MEXC Trading Bot API")
    await db.initialize()
    
    # Start worker
    worker = TradingWorker(db)
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
    title="MEXC Trading Bot",
    description="Automated SPOT trading bot for MEXC",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# AUTH ENDPOINTS

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with admin password"""
    if not verify_admin_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    token = create_session()
    return LoginResponse(token=token, message="Login successful")

# BOT CONTROL ENDPOINTS

@app.post("/api/bot/start")
async def start_bot(_: str = Depends(require_auth)):
    """Start the trading bot"""
    await db.update_settings({'bot_running': True})
    await db.log("INFO", "Bot started by user")
    return {"message": "Bot started", "status": "running"}

@app.post("/api/bot/stop")
async def stop_bot(_: str = Depends(require_auth)):
    """Stop the trading bot"""
    await db.update_settings({'bot_running': False})
    await db.log("INFO", "Bot stopped by user")
    return {"message": "Bot stopped", "status": "stopped"}

@app.post("/api/bot/live/request")
async def request_live_mode(_: str = Depends(require_auth)):
    """Request to enable live trading"""
    await db.update_settings({'live_requested': True})
    await db.log("WARNING", "Live mode requested - awaiting confirmation")
    return {"message": "Live mode requested. Please confirm with password."}

@app.post("/api/bot/live/confirm")
async def confirm_live_mode(request: LiveConfirmRequest, _: str = Depends(require_auth)):
    """Confirm live trading mode with password"""
    if not verify_admin_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Check if API keys are configured
    api_key = os.environ.get('MEXC_API_KEY', '')
    api_secret = os.environ.get('MEXC_API_SECRET', '')
    
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=400,
            detail="MEXC API keys not configured. Please add MEXC_API_KEY and MEXC_API_SECRET to .env file."
        )
    
    await db.update_settings({
        'mode': 'live',
        'live_confirmed': True,
        'live_requested': False
    })
    await db.log("WARNING", "LIVE MODE ENABLED - Real trading active!")
    return {"message": "Live mode confirmed", "mode": "live"}

@app.post("/api/bot/live/disable")
async def disable_live_mode(_: str = Depends(require_auth)):
    """Disable live trading mode"""
    await db.update_settings({
        'mode': 'paper',
        'live_confirmed': False,
        'live_requested': False
    })
    await db.log("INFO", "Switched back to paper mode")
    return {"message": "Switched to paper mode", "mode": "paper"}

# STATUS ENDPOINTS

@app.get("/api/status", response_model=StatusResponse)
async def get_status(_: str = Depends(require_auth)):
    """Get bot status"""
    settings = await db.get_settings()
    account = await db.get_paper_account()
    
    return StatusResponse(
        settings=settings,
        paper_account=account,
        heartbeat=settings.last_heartbeat,
        is_alive=True
    )

@app.get("/api/logs")
async def get_logs(limit: int = 100, _: str = Depends(require_auth)):
    """Get recent logs"""
    logs = await db.get_logs(limit=limit)
    return {"logs": logs}

# MARKET DATA ENDPOINTS

@app.get("/api/market/top_pairs")
async def get_top_pairs(_: str = Depends(require_auth)):
    """Get top trading pairs"""
    settings = await db.get_settings()
    return {
        "pairs": settings.top_pairs,
        "last_refresh": settings.last_pairs_refresh
    }

@app.get("/api/market/candles")
async def get_candles(
    symbol: str,
    interval: str = "15m",
    limit: int = 100,
    _: str = Depends(require_auth)
):
    """Get candlestick data"""
    try:
        mexc = MexcClient()
        klines = await mexc.get_klines(symbol, interval, limit)
        return {"symbol": symbol, "klines": klines}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# BACKTEST ENDPOINT

@app.post("/api/backtest/run", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest, _: str = Depends(require_auth)):
    """Run backtest on historical data"""
    try:
        settings = await db.get_settings()
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
    return {"message": "MEXC Trading Bot API", "status": "healthy"}
