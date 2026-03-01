from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
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

# ============ BOT CONTROL ENDPOINTS (SEPARATED) ============

# ============ BOT CONTROL ENDPOINTS (LIVE only) ============

@app.post("/api/live/start")
async def start_live_bot(current_user: dict = Depends(get_current_user)):
    """Start the LIVE trading bot (requires confirmation + keys)"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    
    # Check if live is confirmed
    if not settings.live_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Live mode not confirmed. Please confirm live mode first."
        )
    
    # Check if API keys are configured
    has_keys = await db.has_mexc_keys(user_id)
    if not has_keys:
        raise HTTPException(
            status_code=400,
            detail="MEXC API keys not configured."
        )
    
    await db.update_settings(user_id, {'live_running': True})
    await db.log(user_id, "WARNING", "[LIVE] Bot started - REAL TRADING ACTIVE!")
    
    await db.audit_log(
        user_id=user_id,
        action="LIVE_BOT_START",
        details={'live_running': True}
    )
    
    return {"message": "Live bot started", "mode": "live", "running": True}

@app.post("/api/live/stop")
async def stop_live_bot(current_user: dict = Depends(get_current_user)):
    """Stop the LIVE trading bot"""
    user_id = current_user['user_id']
    await db.update_settings(user_id, {'live_running': False})
    await db.log(user_id, "INFO", "[LIVE] Bot stopped")
    
    await db.audit_log(
        user_id=user_id,
        action="LIVE_BOT_STOP",
        details={'live_running': False}
    )
    
    return {"message": "Live bot stopped", "mode": "live", "running": False}

@app.post("/api/live/request")
async def request_live_mode(current_user: dict = Depends(get_current_user)):
    """Request to enable live trading"""
    user_id = current_user['user_id']
    await db.update_settings(user_id, {'live_requested': True})
    await db.log(user_id, "WARNING", "Live mode requested - awaiting confirmation")
    return {"message": "Live mode requested. Please confirm."}

@app.post("/api/live/confirm")
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
        'live_confirmed': True,
        'live_requested': False
    })
    await db.log(user_id, "WARNING", "LIVE MODE CONFIRMED - Ready to start live trading!")
    
    await db.audit_log(
        user_id=user_id,
        action="LIVE_MODE_CONFIRM",
        details={'live_confirmed': True},
        ip_address=request.client.host if request.client else None
    )
    return {"message": "Live mode confirmed. You can now start the live bot.", "confirmed": True}

@app.post("/api/live/revoke")
async def revoke_live_mode(current_user: dict = Depends(get_current_user)):
    """Revoke live trading confirmation"""
    user_id = current_user['user_id']
    await db.update_settings(user_id, {
        'live_confirmed': False,
        'live_requested': False,
        'live_running': False
    })
    await db.log(user_id, "INFO", "Live mode revoked")
    return {"message": "Live mode revoked", "confirmed": False}

# ============ STATUS ENDPOINTS ============

@app.get("/api/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """Get bot status for current user (LIVE only)"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    account = await db.get_live_account(user_id)
    keys_status = await db.get_mexc_keys_status(user_id)
    
    return {
        'settings': {
            # Running state
            'live_running': settings.live_running,
            'live_confirmed': settings.live_confirmed,
            'live_requested': settings.live_requested,
            # Strategy params
            'ema_fast': settings.ema_fast,
            'ema_slow': settings.ema_slow,
            'rsi_period': settings.rsi_period,
            'rsi_min': settings.rsi_min,
            'rsi_overbought': settings.rsi_overbought,
            # Risk params
            'risk_per_trade': settings.risk_per_trade,
            'max_positions': settings.max_positions,
            'max_daily_loss': settings.max_daily_loss,
            'take_profit_rr': settings.take_profit_rr,
            # Budget
            'reserve_usdt': settings.reserve_usdt,
            'trading_budget_usdt': settings.trading_budget_usdt,
            'max_order_notional_usdt': settings.max_order_notional_usdt,
            'live_daily_cap_usdt': settings.live_daily_cap_usdt,
            'live_max_order_usdt': settings.live_max_order_usdt,
            'live_min_notional_usdt': settings.live_min_notional_usdt,
            # BOT STATUS TRACKING
            'live_last_scan': settings.live_last_scan,
            'live_last_decision': settings.live_last_decision,
            'live_last_regime': settings.live_last_regime,
            'live_last_symbol': settings.live_last_symbol,
            'live_budget_used': settings.live_budget_used,
            'live_budget_available': settings.live_budget_available,
            'live_daily_used': settings.live_daily_used,
            'live_daily_remaining': settings.live_daily_remaining,
            'live_positions_count': settings.live_positions_count,
            # Cooldown
            'cooldown_candles': settings.cooldown_candles,
        },
        'live_account': {
            'user_id': account.user_id,
            'equity': account.equity,
            'cash': account.cash,
            'open_positions': [pos.model_dump() for pos in account.open_positions] if account.open_positions else []
        },
        'live_heartbeat': settings.live_heartbeat.isoformat() if settings.live_heartbeat else None,
        'live_is_alive': settings.live_running and settings.live_confirmed,
        'mexc_keys_connected': keys_status['connected']
    }

@app.get("/api/logs")
async def get_logs(
    limit: int = 100, 
    mode: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get recent logs for current user, optionally filtered by mode"""
    user_id = current_user['user_id']
    logs = await db.get_logs(user_id, limit=limit)
    
    # Filter by mode if specified
    if mode:
        mode_prefix = f"[{mode.upper()}]"
        logs = [log for log in logs if mode_prefix in log.get('msg', '')]
    
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

# ============ ACCOUNT BALANCE ENDPOINT ============

@app.get("/api/account/balance")
async def get_account_balance(current_user: dict = Depends(get_current_user)):
    """Get LIVE account balance from MEXC with reserve & budget info"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    live_account = await db.get_live_account(user_id)
    
    # Calculate used budget from open positions
    used_budget = sum(pos.entry_price * pos.qty for pos in live_account.open_positions) if live_account.open_positions else 0
    
    # Get MEXC keys
    keys = await db.get_mexc_keys(user_id)
    if not keys:
        raise HTTPException(
            status_code=400,
            detail="MEXC API keys not configured"
        )
    
    try:
        # Create client with user's keys
        from crypto_utils import decrypt_value
        api_key = decrypt_value(keys['api_key'])
        api_secret = decrypt_value(keys['api_secret'])
        mexc = MexcClient(api_key=api_key, api_secret=api_secret)
        account_info = await mexc.get_account()
        
        # Extract balances
        balances = account_info.get('balances', [])
        
        # Calculate total equity in USDT
        usdt_balance = next(
            (b for b in balances if b.get('asset') == 'USDT'),
            {'free': '0', 'locked': '0'}
        )
        usdt_free = float(usdt_balance.get('free', 0))
        usdt_locked = float(usdt_balance.get('locked', 0))
        usdt_total = usdt_free + usdt_locked
        
        # RESERVE SYSTEM: Calculate available to bot
        available_to_bot = max(0, usdt_free - settings.reserve_usdt)
        
        # Apply trading budget cap
        budget_remaining = max(0, settings.trading_budget_usdt - used_budget)
        remaining_budget = min(available_to_bot, budget_remaining)
        
        # DAILY CAP
        today_exposure = await db.get_today_exposure(user_id, 'live')
        daily_cap = settings.live_daily_cap_usdt
        daily_remaining = max(0, daily_cap - today_exposure)
        
        # Get non-zero balances for display
        non_zero_balances = [
            {
                'asset': b['asset'],
                'free': float(b.get('free', 0)),
                'locked': float(b.get('locked', 0))
            }
            for b in balances
            if float(b.get('free', 0)) > 0 or float(b.get('locked', 0)) > 0
        ]
        
        return {
            'source': 'live',
            'source_label': 'MEXC Live',
            'equity': usdt_total,
            'cash': usdt_free,
            'locked': usdt_locked,
            'balances': non_zero_balances[:20],
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'error': None,
            # Reserve & Budget info
            'budget': {
                'usdt_free': round(usdt_free, 2),
                'reserve_usdt': settings.reserve_usdt,
                'available_to_bot': round(available_to_bot, 2),
                'trading_budget': settings.trading_budget_usdt,
                'used_budget': round(used_budget, 2),
                'remaining_budget': round(remaining_budget, 2),
                'max_order': settings.live_max_order_usdt
            },
            # Daily Cap
            'daily_cap': {
                'cap': daily_cap,
                'used': round(today_exposure, 2),
                'remaining': round(daily_remaining, 2)
            },
            'open_positions_count': len(live_account.open_positions) if live_account else 0
        }
        
    except Exception as e:
        logger.error(f"MEXC balance fetch failed for user {user_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch MEXC balance: {str(e)}"
        )

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

# ============ MANUAL SELL ENDPOINT ============

from pydantic import BaseModel

class ManualSellRequest(BaseModel):
    symbol: str
    confirm: bool = False

@app.post("/api/positions/sell")
async def manual_sell_position(
    request: ManualSellRequest,
    current_user: dict = Depends(get_current_user)
):
    """Manually sell a live position at current market price"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    account = await db.get_live_account(user_id)
    
    # Find the position
    position = None
    for pos in account.open_positions:
        if pos.symbol == request.symbol:
            position = pos
            break
    
    if not position:
        raise HTTPException(status_code=404, detail=f"Position {request.symbol} nicht gefunden")
    
    # Get user's MEXC client
    keys = await db.get_mexc_keys(user_id)
    if not keys:
        raise HTTPException(status_code=400, detail="MEXC API keys nicht konfiguriert")
    
    from crypto_utils import decrypt_value
    api_key = decrypt_value(keys['api_key'])
    api_secret = decrypt_value(keys['api_secret'])
    mexc = MexcClient(api_key=api_key, api_secret=api_secret)
    
    # If not confirmed, return position details for confirmation
    if not request.confirm:
        ticker = await mexc.get_ticker_24h(request.symbol)
        current_price = float(ticker['lastPrice'])
        
        pnl = (current_price - position.entry_price) * position.qty
        pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        
        return {
            'confirm_required': True,
            'position': {
                'symbol': position.symbol,
                'qty': position.qty,
                'entry_price': position.entry_price,
                'current_price': current_price,
                'pnl': round(pnl, 4),
                'pnl_pct': round(pnl_pct, 2),
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit
            },
            'warning': '⚠️ ACHTUNG: Dies wird die Position auf MEXC zum aktuellen Marktpreis verkaufen!'
        }
    
    # Execute real sell on MEXC
    ticker = await mexc.get_ticker_24h(request.symbol)
    current_price = float(ticker['lastPrice'])
    
    try:
        order_result = await mexc.place_order(
            symbol=request.symbol,
            side="SELL",
            order_type="MARKET",
            quantity=position.qty
        )
        order_id = order_result.get('orderId')
        
        executed_price = current_price
        if order_result.get('executedQty') and order_result.get('cummulativeQuoteQty'):
            actual_qty = float(order_result.get('executedQty'))
            if actual_qty > 0:
                executed_price = float(order_result.get('cummulativeQuoteQty')) / actual_qty
        
        if not order_id:
            raise HTTPException(status_code=500, detail="MEXC Order fehlgeschlagen - keine Order ID")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MEXC Sell Fehler: {str(e)}")
    
    # Calculate PnL
    pnl = (executed_price - position.entry_price) * position.qty
    pnl_pct = ((executed_price - position.entry_price) / position.entry_price) * 100
    
    # Remove position from account
    account.open_positions = [p for p in account.open_positions if p.symbol != request.symbol]
    account.cash += position.qty * executed_price
    
    await db.update_live_account(account)
    
    # Log the manual sell
    await db.log(
        user_id,
        "INFO",
        f"[LIVE] 🔴 MANUELLER VERKAUF: {request.symbol} @ {executed_price:.4f} | PnL: ${pnl:.2f} ({pnl_pct:+.1f}%)"
    )
    
    # Record the trade
    trade = Trade(
        user_id=user_id,
        ts=datetime.now(timezone.utc),
        symbol=request.symbol,
        side="SELL",
        qty=position.qty,
        entry=position.entry_price,
        exit=executed_price,
        pnl=pnl,
        pnl_pct=pnl_pct,
        mode='live',
        reason="Manueller Verkauf"
    )
    await db.add_trade(trade)
    
    return {
        'success': True,
        'message': f'{request.symbol} erfolgreich verkauft!',
        'order_id': order_id,
        'executed_price': executed_price,
        'qty': position.qty,
        'pnl': round(pnl, 4),
        'pnl_pct': round(pnl_pct, 2)
    }

# ============ METRICS ENDPOINTS ============

@app.get("/api/metrics/daily_pnl")
async def get_daily_pnl(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """Get daily PnL aggregation for chart (LIVE only)"""
    user_id = current_user['user_id']
    
    daily_data = await db.get_daily_pnl(user_id, mode='live', days=days)
    
    # Calculate summary stats
    total_pnl = sum(d['pnl'] for d in daily_data)
    total_trades = sum(d['trades_count'] for d in daily_data)
    winning_days = sum(1 for d in daily_data if d['pnl'] > 0)
    losing_days = sum(1 for d in daily_data if d['pnl'] < 0)
    
    return {
        'data': daily_data,
        'summary': {
            'total_pnl': round(total_pnl, 2),
            'total_trades': total_trades,
            'winning_days': winning_days,
            'losing_days': losing_days,
            'win_rate': round(winning_days / (winning_days + losing_days) * 100, 1) if (winning_days + losing_days) > 0 else 0
        },
        'days': days
    }

# ============ TRADES HISTORY ENDPOINTS ============

@app.get("/api/trades")
async def get_trades_history(
    symbol: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get paginated trade history (LIVE only)"""
    user_id = current_user['user_id']
    
    trades, total = await db.get_trades_paginated(
        user_id, 
        mode='live',  # Only live trades
        symbol=symbol,
        limit=min(limit, 500),
        offset=offset
    )
    
    return {
        'trades': trades,
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': offset + len(trades) < total
    }

@app.get("/api/trades/symbols")
async def get_traded_symbols(current_user: dict = Depends(get_current_user)):
    """Get list of all symbols the user has traded"""
    user_id = current_user['user_id']
    
    # Get distinct symbols from trades
    symbols = await db.trades.distinct('symbol', {'user_id': user_id})
    
    return {'symbols': sorted(symbols)}

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
