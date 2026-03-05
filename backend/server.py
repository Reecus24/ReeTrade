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
from mexc_futures_client import MexcFuturesClient
from strategy import TradingStrategy
from risk_manager import RiskManager
from ml_data_collector import get_ml_collector
from ki_learning_engine import get_ki_engine
from telegram_bot import TelegramBot, get_telegram_bot
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
telegram_bot: TelegramBot = None
telegram_polling_task: asyncio.Task = None
limiter = Limiter(key_func=get_remote_address)
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global worker, worker_task, telegram_bot, telegram_polling_task
    
    # Startup
    logger.info("Starting ReeTrade Terminal API")
    await db.initialize()
    
    # Start multi-user worker
    worker = MultiUserTradingWorker(db)
    worker_task = asyncio.create_task(worker.start())
    
    # Start Telegram bot if configured
    tg_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if tg_token:
        telegram_bot = get_telegram_bot(tg_token, db)
        await telegram_bot.register_commands()
        telegram_polling_task = asyncio.create_task(telegram_polling_loop())
        logger.info("Telegram bot started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down")
    if worker:
        await worker.stop()
    if worker_task:
        worker_task.cancel()
    if telegram_polling_task:
        telegram_polling_task.cancel()
    db.close()


async def telegram_polling_loop():
    """Polling loop für Telegram Befehle"""
    global telegram_bot
    
    if not telegram_bot:
        return
    
    offset = 0
    default_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    # Sende Startup-Nachricht
    if default_chat_id:
        await telegram_bot.send_message(
            int(default_chat_id),
            "🤖 <b>ReeTrade Bot gestartet!</b>\n\nTippe /help für alle Befehle."
        )
    
    while True:
        try:
            updates = await telegram_bot.get_updates(offset)
            
            for update in updates:
                offset = update['update_id'] + 1
                
                if 'message' in update and 'text' in update['message']:
                    chat_id = update['message']['chat']['id']
                    text = update['message']['text']
                    
                    # Finde user_id basierend auf chat_id
                    user = await db.users.find_one({"telegram_chat_id": str(chat_id)})
                    user_id = str(user['_id']) if user else None
                    
                    # Wenn kein User gefunden, verwende Default
                    if not user_id and str(chat_id) == default_chat_id:
                        # Finde ersten User mit Live-Mode
                        first_user = await db.users.find_one({"live_mode_confirmed": True})
                        user_id = str(first_user['_id']) if first_user else None
                    
                    if text.startswith('/'):
                        response = await telegram_bot.handle_command(chat_id, text.split()[0], user_id)
                        await telegram_bot.send_message(chat_id, response)
            
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            await asyncio.sleep(5)

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
    """Get bot status for current user (LIVE only) with AI info"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    account = await db.get_live_account(user_id)
    
    # Quick check - just verify keys exist (real verification via /api/keys/mexc/status)
    keys_status = await db.get_mexc_keys_status(user_id)
    
    return {
        'settings': {
            # Trading Mode (NEW)
            'trading_mode': settings.trading_mode,
            # AI Status (NEW)
            'ai_confidence': settings.ai_confidence,
            'ai_risk_score': settings.ai_risk_score,
            'ai_reasoning': settings.ai_reasoning,
            'ai_last_override': settings.ai_last_override,
            'ai_min_position': settings.ai_min_position,
            'ai_max_position': settings.ai_max_position,
            'ai_current_position': settings.ai_current_position,
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
            'open_positions': await enrich_positions_with_prices(account.open_positions, user_id) if account.open_positions else []
        },
        'live_heartbeat': settings.live_heartbeat.isoformat() if settings.live_heartbeat else None,
        'live_is_alive': settings.live_running and settings.live_confirmed,
        'mexc_keys_connected': keys_status['connected']
    }

async def enrich_positions_with_prices(positions: list, user_id: str) -> list:
    """Add current prices AND real MEXC balances to positions for live PnL display"""
    if not positions:
        return []
    
    # Try to get MEXC client for user
    keys = await db.get_mexc_keys(user_id)
    mexc = None
    mexc_balances = {}
    
    if keys:
        try:
            mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
            # Get all balances once
            account_info = await mexc.get_account()
            for bal in account_info.get('balances', []):
                asset = bal.get('asset', '')
                try:
                    total = float(bal.get('free', 0) or 0) + float(bal.get('locked', 0) or 0)
                    if total > 0:
                        mexc_balances[asset] = total
                except:
                    pass
        except Exception:
            pass
    
    enriched = []
    for pos in positions:
        pos_dict = pos.model_dump() if hasattr(pos, 'model_dump') else dict(pos)
        
        # Get the asset name (e.g., AIXBT from AIXBTUSDT)
        asset = pos.symbol.replace('USDT', '')
        
        # Use REAL MEXC balance instead of stored qty
        if asset in mexc_balances:
            real_qty = mexc_balances[asset]
            if real_qty != pos_dict.get('qty'):
                pos_dict['qty'] = real_qty
                pos_dict['qty_synced'] = True  # Flag that we synced from MEXC
        
        # Try to get current price
        if mexc:
            try:
                ticker = await mexc.get_ticker_24h(pos.symbol)
                pos_dict['current_price'] = float(ticker.get('lastPrice', 0))
            except Exception:
                pos_dict['current_price'] = 0
        else:
            pos_dict['current_price'] = 0
        
        enriched.append(pos_dict)
    
    return enriched

# ============ AI PROFILE ENDPOINTS ============

@app.get("/api/ai/profiles")
async def get_ai_profiles(current_user: dict = Depends(get_current_user)):
    """Get available AI trading profiles V2 with dynamic position sizing based on available USDT"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    live_account = await db.get_live_account(user_id)
    
    from ai_engine_v2 import ai_engine_v2, TradingMode, RISK_PROFILES_V2
    
    # Get USDT free balance from MEXC (for position sizing display)
    usdt_free = 0
    keys = await db.get_mexc_keys(user_id)
    if keys:
        try:
            mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
            account_info = await mexc.get_account()
            usdt_balance = next(
                (b for b in account_info.get('balances', []) if b.get('asset') == 'USDT'),
                {'free': '0'}
            )
            usdt_free = float(usdt_balance.get('free', 0))
        except Exception:
            usdt_free = settings.trading_budget_usdt or 500
    else:
        usdt_free = settings.trading_budget_usdt or 500
    
    # Calculate open positions value
    open_value = sum(
        pos.entry_price * pos.qty for pos in live_account.open_positions
    ) if live_account and live_account.open_positions else 0
    
    trading_budget = settings.trading_budget_usdt or 500
    trading_budget_remaining = max(0, trading_budget - open_value)
    
    profiles = []
    
    # Manual Mode
    profiles.append({
        'mode': 'manual',
        'name': 'Manual',
        'emoji': '⚙️',
        'description': 'Volle manuelle Kontrolle',
        'position_pct_range': 'Manuell',
        'position_usd_min': settings.live_min_notional_usdt or 5,
        'position_usd_max': settings.live_max_order_usdt or 50,
        'max_positions': settings.max_positions or 3,
        'usdt_free': round(usdt_free, 2),
        'trading_budget_remaining': round(trading_budget_remaining, 2)
    })
    
    # AI Profiles with NEW position sizing logic
    for mode in [TradingMode.AI_CONSERVATIVE, TradingMode.AI_MODERATE, TradingMode.AI_AGGRESSIVE, TradingMode.KI_EXPLORER]:
        profile = RISK_PROFILES_V2.get(mode, {})
        
        # Calculate position sizes based on AVAILABLE USDT (not trading budget!)
        position_pct_min = profile.get('position_pct_min', 5)
        position_pct_max = profile.get('position_pct_max', 20)
        
        # Calculate actual USD values based on available USDT
        position_usd_min = usdt_free * (position_pct_min / 100)
        position_usd_max = usdt_free * (position_pct_max / 100)
        
        # Apply trading budget cap
        position_usd_min = min(position_usd_min, trading_budget_remaining)
        position_usd_max = min(position_usd_max, trading_budget_remaining)
        
        profile_data = {
            'mode': mode.value,
            'name': profile.get('name', mode.value),
            'emoji': profile.get('emoji', '🤖'),
            'description': profile.get('description', ''),
            # NEW: Position sizing as % of available USDT
            'position_pct_range': f"{position_pct_min:.0f}%-{position_pct_max:.0f}%",
            'position_usd_min': round(position_usd_min, 2),
            'position_usd_max': round(position_usd_max, 2),
            'max_positions': profile.get('max_positions', 3),
            'sl_atr_multiplier': f"{profile.get('sl_atr_multiplier_min', 1.5):.1f}x-{profile.get('sl_atr_multiplier_max', 2.5):.1f}x ATR",
            'tp_rr_range': f"1:{profile.get('tp_rr_base', 2):.1f} - 1:{profile.get('tp_rr_max', 3):.1f}",
            'risk_per_trade': f"{profile.get('risk_pct_min', 1):.1f}%-{profile.get('risk_pct_max', 5):.1f}%",
            'allowed_regimes': [r.value for r in profile.get('allowed_regimes', [])],
            'min_adx': profile.get('min_adx', 15),
            'usdt_free': round(usdt_free, 2),
            'trading_budget_remaining': round(trading_budget_remaining, 2)
        }
        
        # Add explorer-specific info
        if mode == TradingMode.KI_EXPLORER:
            profile_data['is_explorer'] = True
            profile_data['description'] = '🔬 Experimentiert mit verschiedenen Parametern für optimales KI-Lernen. Nur mit kleinen Beträgen nutzen!'
        
        profiles.append(profile_data)
    
    return {
        'profiles': profiles,
        'usdt_free': round(usdt_free, 2),
        'trading_budget': trading_budget,
        'trading_budget_remaining': round(trading_budget_remaining, 2),
        'open_positions_value': round(open_value, 2)
    }

@app.get("/api/ai/preview/{mode}")
async def preview_ai_mode(mode: str, current_user: dict = Depends(get_current_user)):
    """Preview AI V2 settings for a mode based on available USDT - NEW POSITION SIZING"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    live_account = await db.get_live_account(user_id)
    
    from ai_engine_v2 import TradingMode, RISK_PROFILES_V2, ai_engine_v2
    
    try:
        trading_mode = TradingMode(mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid trading mode")
    
    # Get USDT free balance from MEXC
    usdt_free = 0
    keys = await db.get_mexc_keys(user_id)
    if keys:
        try:
            mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
            account_info = await mexc.get_account()
            usdt_balance = next(
                (b for b in account_info.get('balances', []) if b.get('asset') == 'USDT'),
                {'free': '0'}
            )
            usdt_free = float(usdt_balance.get('free', 0))
        except Exception:
            usdt_free = settings.trading_budget_usdt or 500
    else:
        usdt_free = settings.trading_budget_usdt or 500
    
    # Calculate open positions value
    open_value = sum(
        pos.entry_price * pos.qty for pos in live_account.open_positions
    ) if live_account and live_account.open_positions else 0
    
    trading_budget = settings.trading_budget_usdt or 500
    trading_budget_remaining = max(0, trading_budget - open_value)
    
    if trading_mode == TradingMode.MANUAL:
        return {
            'mode': 'manual',
            'name': 'Manual',
            'emoji': '⚙️',
            'position_pct_range': 'Manuell',
            'position_usd_min': settings.live_min_notional_usdt or 5,
            'position_usd_max': settings.live_max_order_usdt or 50,
            'max_positions': settings.max_positions or 3,
            'sl_atr_multiplier': 'Fixed %',
            'tp_rr_range': 'Fixed',
            'risk_per_trade': f"{settings.risk_per_trade * 100:.1f}%",
            'allowed_regimes': ['bullish'],
            'min_adx': 15,
            'reasoning': ['Manual Mode - keine AI-Anpassungen'],
            'usdt_free': round(usdt_free, 2),
            'trading_budget': trading_budget,
            'trading_budget_remaining': round(trading_budget_remaining, 2)
        }
    
    # Get AI V2 profile
    profile = RISK_PROFILES_V2.get(trading_mode, {})
    
    # Calculate position sizes based on AVAILABLE USDT (not trading budget!)
    position_pct_min = profile.get('position_pct_min', 5)
    position_pct_max = profile.get('position_pct_max', 20)
    
    # Calculate actual USD values based on available USDT
    position_usd_min = usdt_free * (position_pct_min / 100)
    position_usd_max = usdt_free * (position_pct_max / 100)
    
    # Apply trading budget cap
    position_usd_min = min(position_usd_min, trading_budget_remaining)
    position_usd_max = min(position_usd_max, trading_budget_remaining)
    
    return {
        'mode': trading_mode.value,
        'name': profile.get('name', mode),
        'emoji': profile.get('emoji', '🤖'),
        'description': profile.get('description', ''),
        # NEW: Position sizing as % of available USDT
        'position_pct_range': f"{position_pct_min:.0f}%-{position_pct_max:.0f}%",
        'position_usd_min': round(position_usd_min, 2),
        'position_usd_max': round(position_usd_max, 2),
        # ATR-based SL/TP
        'sl_atr_multiplier': f"{profile.get('sl_atr_multiplier_min', 1.5):.1f}x-{profile.get('sl_atr_multiplier_max', 2.5):.1f}x ATR",
        'tp_rr_range': f"1:{profile.get('tp_rr_base', 2):.1f} - 1:{profile.get('tp_rr_max', 3):.1f}",
        'max_positions': profile.get('max_positions', 3),
        'risk_per_trade': f"{profile.get('risk_pct_min', 1):.1f}%-{profile.get('risk_pct_max', 5):.1f}%",
        'allowed_regimes': [r.value for r in profile.get('allowed_regimes', [])],
        'min_adx': profile.get('min_adx', 15),
        # Reasoning with NEW format
        'reasoning': [
            f"{profile.get('emoji', '🤖')} Profil: {profile.get('name', mode)}",
            f"💰 Position Size: {position_pct_min:.0f}%-{position_pct_max:.0f}% vom verfügbaren USDT",
            f"📊 Berechnete Order: ${position_usd_min:.2f} - ${position_usd_max:.2f}",
            f"🛑 Stop Loss: {profile.get('sl_atr_multiplier_min', 1.5):.1f}x-{profile.get('sl_atr_multiplier_max', 2.5):.1f}x ATR (dynamisch)",
            f"🎯 Take Profit: R:R {profile.get('tp_rr_base', 2):.1f}:1 - {profile.get('tp_rr_max', 3):.1f}:1",
            f"⚡ Confidence-Skalierung: Hoch >{profile.get('high_confidence_threshold', 85)}% → obere Range",
            f"📈 Erlaubte Regimes: {', '.join([r.value.upper() for r in profile.get('allowed_regimes', [])])}"
        ],
        'usdt_free': round(usdt_free, 2),
        'trading_budget': trading_budget,
        'trading_budget_remaining': round(trading_budget_remaining, 2)
    }

@app.get("/api/ai/status")
async def get_ai_status(current_user: dict = Depends(get_current_user)):
    """Get current AI decision status"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    
    return {
        'trading_mode': settings.trading_mode,
        'confidence': settings.ai_confidence,
        'risk_score': settings.ai_risk_score,
        'reasoning': settings.ai_reasoning,
        'last_override': settings.ai_last_override
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

# ============ ML TRAINING DATA ENDPOINTS ============

@app.get("/api/ml/stats")
async def get_ml_stats(current_user: dict = Depends(get_current_user)):
    """Get ML training data statistics"""
    user_id = current_user['user_id']
    ml_collector = get_ml_collector(db)
    stats = await ml_collector.get_training_stats(user_id)
    return stats

@app.get("/api/ml/training-data")
async def get_ml_training_data(current_user: dict = Depends(get_current_user)):
    """Get all completed trades for ML training export"""
    user_id = current_user['user_id']
    ml_collector = get_ml_collector(db)
    data = await ml_collector.get_training_data(user_id, min_trades=10)
    return {
        "count": len(data),
        "data": data,
        "ready_for_training": len(data) >= 100
    }


# ============ FUTURES ENDPOINTS ============

@app.get("/api/futures/status")
async def get_futures_status(current_user: dict = Depends(get_current_user)):
    """Get Futures account status and balance"""
    user_id = current_user['user_id']
    settings = await db.get_settings(user_id)
    
    # Try to get separate futures keys first, fallback to spot keys
    keys = await db.get_mexc_keys(user_id, key_type='futures')
    if not keys:
        return {
            "futures_enabled": settings.futures_enabled,
            "error": "MEXC Futures API keys nicht konfiguriert. Bitte separate Futures-Keys im Settings Tab eingeben.",
            "account": None,
            "positions": []
        }
    
    try:
        futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        
        # First test connectivity (public endpoint)
        connectivity = await futures_client.test_connectivity()
        if not connectivity.get("reachable"):
            logger.warning(f"[FUTURES] Connectivity test failed: {connectivity.get('error')}")
            return {
                "futures_enabled": settings.futures_enabled,
                "error": f"MEXC Futures API nicht erreichbar: {connectivity.get('error')}",
                "account": None,
                "positions": [],
                "settings": {
                    "default_leverage": settings.futures_default_leverage,
                    "max_leverage": settings.futures_max_leverage,
                    "risk_per_trade": settings.futures_risk_per_trade,
                    "margin_mode": settings.futures_margin_mode,
                    "allow_shorts": settings.futures_allow_shorts
                }
            }
        
        # Get futures account assets
        assets = await futures_client.get_account_asset("USDT")
        
        # Check for API errors in the response
        if isinstance(assets, dict) and assets.get('error'):
            error_msg = assets.get('error')
            logger.warning(f"[FUTURES] Account asset error: {error_msg}")
            return {
                "futures_enabled": settings.futures_enabled,
                "error": f"Futures API Fehler: {error_msg}",
                "account": None,
                "positions": [],
                "connectivity": connectivity,
                "settings": {
                    "default_leverage": settings.futures_default_leverage,
                    "max_leverage": settings.futures_max_leverage,
                    "risk_per_trade": settings.futures_risk_per_trade,
                    "margin_mode": settings.futures_margin_mode,
                    "allow_shorts": settings.futures_allow_shorts
                }
            }
        
        # Get open futures positions
        positions = []
        try:
            positions = await futures_client.get_open_positions()
        except Exception as pos_err:
            logger.warning(f"Futures positions fetch error: {pos_err}")
        
        return {
            "futures_enabled": settings.futures_enabled,
            "account": {
                "available_balance": float(assets.get("availableBalance", 0)),
                "frozen_balance": float(assets.get("frozenBalance", 0)),
                "equity": float(assets.get("equity", 0)),
                "unrealized_pnl": float(assets.get("unrealisedPnl", 0))
            },
            "open_positions": len(positions),
            "positions": [
                {
                    "symbol": p.get("symbol"),
                    "position_type": "LONG" if p.get("positionType") == 1 else "SHORT",
                    "quantity": float(p.get("holdVol", 0)),
                    "entry_price": float(p.get("openAvgPrice", 0)),
                    "leverage": int(p.get("leverage", 1)),
                    "unrealized_pnl": float(p.get("unrealisedPnl", 0)),
                    "liquidation_price": float(p.get("liquidatePrice", 0)),
                    "margin": float(p.get("im", 0))
                }
                for p in positions
            ],
            "connectivity": connectivity,
            "settings": {
                "default_leverage": settings.futures_default_leverage,
                "max_leverage": settings.futures_max_leverage,
                "risk_per_trade": settings.futures_risk_per_trade,
                "margin_mode": settings.futures_margin_mode,
                "allow_shorts": settings.futures_allow_shorts
            }
        }
    except Exception as e:
        logger.error(f"Futures status error: {e}")
        return {
            "futures_enabled": settings.futures_enabled,
            "error": f"Futures API Fehler: {str(e)}. Stelle sicher, dass dein API-Key Futures-Berechtigung hat.",
            "account": None,
            "positions": [],
            "settings": {
                "default_leverage": settings.futures_default_leverage,
                "max_leverage": settings.futures_max_leverage,
                "risk_per_trade": settings.futures_risk_per_trade,
                "margin_mode": settings.futures_margin_mode,
                "allow_shorts": settings.futures_allow_shorts
            }
        }


@app.get("/api/futures/test")
async def test_futures_connectivity(current_user: dict = Depends(get_current_user)):
    """Test MEXC Futures API connectivity and authentication"""
    user_id = current_user['user_id']
    
    keys = await db.get_mexc_keys(user_id, key_type='futures')
    if not keys:
        return {"error": "MEXC Futures API keys nicht konfiguriert. Bitte separate Futures-Keys eingeben.", "tests": {}}
    
    futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
    
    tests = {}
    
    # Test 1: Public connectivity (ping)
    try:
        connectivity = await futures_client.test_connectivity()
        tests["ping"] = {"success": connectivity.get("reachable", False), "data": connectivity}
    except Exception as e:
        tests["ping"] = {"success": False, "error": str(e)}
    
    # Test 2: Get contracts (public)
    try:
        contracts = await futures_client.get_all_contracts()
        tests["contracts"] = {"success": len(contracts) > 0, "count": len(contracts)}
    except Exception as e:
        tests["contracts"] = {"success": False, "error": str(e)}
    
    # Test 3: Authenticated - Get account asset
    try:
        assets = await futures_client.get_account_asset("USDT")
        if isinstance(assets, dict) and assets.get('error'):
            tests["auth"] = {"success": False, "error": assets.get('error')}
        else:
            tests["auth"] = {"success": True, "available": assets.get("availableBalance", 0)}
    except Exception as e:
        tests["auth"] = {"success": False, "error": str(e)}
    
    return {"tests": tests, "all_passed": all(t.get("success") for t in tests.values())}


@app.post("/api/futures/enable")
async def enable_futures(current_user: dict = Depends(get_current_user)):
    """Enable futures trading"""
    user_id = current_user['user_id']
    
    # Verify API keys work with futures
    keys = await db.get_mexc_keys(user_id, key_type='futures')
    if not keys:
        raise HTTPException(status_code=400, detail="MEXC Futures API keys nicht konfiguriert. Bitte separate Futures-Keys eingeben.")
    
    try:
        futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        await futures_client.get_account_asset("USDT")
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Futures API nicht verfügbar: {str(e)}"
        )
    
    await db.update_settings(user_id, {'futures_enabled': True})
    await db.log(user_id, "WARNING", "[FUTURES] ⚡ Futures Trading aktiviert!")
    
    return {"message": "Futures Trading aktiviert", "futures_enabled": True}


@app.post("/api/futures/disable")
async def disable_futures(current_user: dict = Depends(get_current_user)):
    """Disable futures trading"""
    user_id = current_user['user_id']
    
    await db.update_settings(user_id, {'futures_enabled': False})
    await db.log(user_id, "INFO", "[FUTURES] Futures Trading deaktiviert")
    
    return {"message": "Futures Trading deaktiviert", "futures_enabled": False}


@app.get("/api/futures/pairs")
async def get_futures_pairs(current_user: dict = Depends(get_current_user)):
    """Get available futures trading pairs"""
    user_id = current_user['user_id']
    
    keys = await db.get_mexc_keys(user_id, key_type='futures')
    if not keys:
        raise HTTPException(status_code=400, detail="MEXC Futures API keys nicht konfiguriert")
    
    try:
        futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        pairs = await futures_client.get_available_futures_pairs("USDT")
        
        return {
            "pairs": pairs,
            "count": len(pairs)
        }
    except Exception as e:
        logger.error(f"Futures pairs error: {e}")
        raise HTTPException(status_code=502, detail=f"Fehler beim Laden der Futures-Paare: {str(e)}")


@app.post("/api/futures/close-position")
async def close_futures_position(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """Manually close a futures position"""
    user_id = current_user['user_id']
    
    keys = await db.get_mexc_keys(user_id, key_type='futures')
    if not keys:
        raise HTTPException(status_code=400, detail="MEXC Futures API keys nicht konfiguriert")
    
    try:
        futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        
        # Find the position
        positions = await futures_client.get_open_positions(symbol)
        if not positions:
            raise HTTPException(status_code=404, detail=f"Keine offene Position für {symbol}")
        
        pos = positions[0]
        pos_type = pos.get("positionType")
        quantity = float(pos.get("holdVol", 0))
        
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="Position hat keine Menge")
        
        # Close the position
        if pos_type == 1:  # Long
            result = await futures_client.close_long(symbol, quantity)
        else:  # Short
            result = await futures_client.close_short(symbol, quantity)
        
        await db.log(user_id, "WARNING", f"[FUTURES] 🔴 Position geschlossen: {symbol}")
        
        return {
            "success": True,
            "message": f"Position {symbol} geschlossen",
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Close futures position error: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Schließen: {str(e)}")


@app.post("/api/futures/close-all")
async def close_all_futures_positions(current_user: dict = Depends(get_current_user)):
    """Close all open futures positions"""
    user_id = current_user['user_id']
    
    keys = await db.get_mexc_keys(user_id, key_type='futures')
    if not keys:
        raise HTTPException(status_code=400, detail="MEXC Futures API keys nicht konfiguriert")
    
    try:
        futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        results = await futures_client.close_all_positions()
        
        closed_count = sum(1 for r in results if r.get("success"))
        await db.log(user_id, "WARNING", f"[FUTURES] 🔴 Alle Positionen geschlossen ({closed_count})")
        
        return {
            "success": True,
            "message": f"{closed_count} Positionen geschlossen",
            "results": results
        }
    except Exception as e:
        logger.error(f"Close all futures positions error: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Schließen: {str(e)}")


@app.put("/api/futures/settings")
async def update_futures_settings(
    default_leverage: Optional[int] = None,
    max_leverage: Optional[int] = None,
    risk_per_trade: Optional[float] = None,
    allow_shorts: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Update futures-specific settings"""
    user_id = current_user['user_id']
    
    updates = {}
    if default_leverage is not None:
        if default_leverage < 2 or default_leverage > 20:
            raise HTTPException(status_code=400, detail="Leverage muss zwischen 2 und 20 sein")
        updates['futures_default_leverage'] = default_leverage
    
    if max_leverage is not None:
        if max_leverage < 2 or max_leverage > 20:
            raise HTTPException(status_code=400, detail="Max Leverage muss zwischen 2 und 20 sein")
        updates['futures_max_leverage'] = max_leverage
    
    if risk_per_trade is not None:
        if risk_per_trade < 0.005 or risk_per_trade > 0.05:
            raise HTTPException(status_code=400, detail="Risiko pro Trade muss zwischen 0.5% und 5% sein")
        updates['futures_risk_per_trade'] = risk_per_trade
    
    if allow_shorts is not None:
        updates['futures_allow_shorts'] = allow_shorts
    
    if updates:
        await db.update_settings(user_id, updates)
        await db.log(user_id, "INFO", f"[FUTURES] Einstellungen aktualisiert: {updates}")
    
    return {"message": "Futures-Einstellungen aktualisiert", "updates": updates}


# ============ KI LEARNING ENDPOINTS ============

@app.get("/api/ki/stats")
async def get_ki_stats(current_user: dict = Depends(get_current_user)):
    """Get KI learning statistics"""
    user_id = current_user['user_id']
    ki_engine = get_ki_engine(db)
    return await ki_engine.get_ki_stats(user_id)


@app.get("/api/ki/log")
async def get_ki_log(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Get KI learning log"""
    user_id = current_user['user_id']
    ki_engine = get_ki_engine(db)
    log = await ki_engine.get_ki_log(user_id, limit)
    return {"log": log}


# ============ COIN SELECTION ENDPOINTS ============

@app.get("/api/coins/available")
async def get_available_coins(current_user: dict = Depends(get_current_user)):
    """Get all available SPOT and FUTURES coins from MEXC"""
    user_id = current_user['user_id']
    
    keys = await db.get_mexc_keys(user_id)
    if not keys:
        return {"spot_coins": [], "futures_coins": [], "error": "API Keys nicht konfiguriert"}
    
    spot_coins = []
    futures_coins = []
    
    try:
        # Get SPOT coins using ticker endpoint (more reliable)
        mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        tickers = await mexc.get_ticker_24h()
        
        # Filter USDT pairs with volume
        for ticker in tickers:
            if isinstance(ticker, dict):
                symbol = ticker.get('symbol', '')
                volume = float(ticker.get('quoteVolume', 0))
                if symbol.endswith('USDT') and volume > 10000:  # Min $10k volume
                    spot_coins.append(symbol)
        
        # Sort alphabetically and limit
        spot_coins = sorted(list(set(spot_coins)))[:500]
        logger.info(f"Found {len(spot_coins)} SPOT coins")
    except Exception as e:
        logger.error(f"SPOT coins fetch error: {e}")
    
    try:
        # Get FUTURES coins
        futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        contracts = await futures_client.get_all_contracts()
        
        for contract in contracts:
            symbol = contract.get('symbol', '')
            if symbol.endswith('_USDT'):
                futures_coins.append(symbol)
        
        # Sort and limit
        futures_coins = sorted(list(set(futures_coins)))[:300]
        logger.info(f"Found {len(futures_coins)} FUTURES coins")
    except Exception as e:
        logger.error(f"Futures coins fetch error: {e}")
        # If futures fails, return empty but don't crash
        futures_coins = []
    
    return {
        "spot_coins": spot_coins,
        "futures_coins": futures_coins,
        "spot_count": len(spot_coins),
        "futures_count": len(futures_coins)
    }


# ============ MEXC KEYS ENDPOINTS ============

@app.post("/api/keys/mexc")
async def set_mexc_keys(keys: MexcKeysInput, current_user: dict = Depends(get_current_user)):
    """Set MEXC SPOT API keys (encrypted storage)"""
    user_id = current_user['user_id']
    
    if not keys.api_key or not keys.api_secret:
        raise HTTPException(status_code=400, detail="Both API key and secret required")
    
    await db.set_mexc_keys(user_id, keys.api_key, keys.api_secret, key_type='spot')    
    # Audit log
    await db.audit_log(
        user_id=user_id,
        action="KEYS_UPDATE",
        details={'keys_configured': True, 'type': 'spot'}
    )
    await db.log(user_id, "INFO", "MEXC SPOT API keys updated")
    
    return {"message": "MEXC SPOT keys saved securely", "connected": True}


@app.post("/api/keys/mexc/futures")
async def set_mexc_futures_keys(keys: MexcKeysInput, current_user: dict = Depends(get_current_user)):
    """Set MEXC FUTURES API keys (separate from SPOT)"""
    user_id = current_user['user_id']
    
    if not keys.api_key or not keys.api_secret:
        raise HTTPException(status_code=400, detail="Both API key and secret required")
    
    await db.set_mexc_keys(user_id, keys.api_key, keys.api_secret, key_type='futures')    
    # Audit log
    await db.audit_log(
        user_id=user_id,
        action="KEYS_UPDATE",
        details={'keys_configured': True, 'type': 'futures'}
    )
    await db.log(user_id, "INFO", "MEXC FUTURES API keys updated")
    
    return {"message": "MEXC FUTURES keys saved securely", "futures_connected": True}

@app.get("/api/keys/mexc/status")
async def get_mexc_keys_status(current_user: dict = Depends(get_current_user)):
    """Get MEXC keys connection status for both SPOT and FUTURES"""
    user_id = current_user['user_id']
    
    # Get status from DB (includes both spot and futures)
    basic_status = await db.get_mexc_keys_status(user_id)
    
    result = {
        'connected': basic_status.get('spot_connected', False),
        'spot_connected': basic_status.get('spot_connected', False),
        'futures_connected': basic_status.get('futures_connected', False),
        'last_updated': basic_status.get('last_updated'),
        'error': None
    }
    
    # Verify SPOT keys with real API call
    if result['spot_connected']:
        try:
            keys = await db.get_mexc_keys(user_id, key_type='spot')
            if keys:
                mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
                await mexc.get_account()
        except Exception as e:
            result['spot_connected'] = False
            result['connected'] = False
            result['error'] = f'SPOT: {str(e)[:50]}'
    
    # Verify FUTURES keys with real API call  
    if result['futures_connected']:
        try:
            keys = await db.get_mexc_keys(user_id, key_type='futures')
            if keys:
                futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
                await futures_client.get_account_asset('USDT')
        except Exception as e:
            result['futures_connected'] = False
            if result['error']:
                result['error'] += f' | FUTURES: {str(e)[:30]}'
            else:
                result['error'] = f'FUTURES: {str(e)[:50]}'
    
    return result

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
    
    # Calculate used budget from open positions (entry value)
    entry_value = sum(pos.entry_price * pos.qty for pos in live_account.open_positions) if live_account.open_positions else 0
    
    # Get MEXC keys
    keys = await db.get_mexc_keys(user_id)
    if not keys:
        raise HTTPException(
            status_code=400,
            detail="MEXC API keys nicht konfiguriert oder ungültig. Bitte Keys in Settings neu eingeben."
        )
    
    try:
        # Keys are already decrypted by get_mexc_keys()
        mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
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
        
        # Calculate current value of positions (with live prices)
        # First: Check actual token balances on MEXC (more accurate than local DB)
        invested_value = 0
        total_pnl = 0
        actual_positions_count = 0
        
        # Get all non-USDT token balances from MEXC
        token_balances = []
        for b in balances:
            asset = b.get('asset', '')
            if asset == 'USDT':
                continue
            try:
                free = float(b.get('free', 0) or 0)
                locked = float(b.get('locked', 0) or 0)
                total = free + locked
                if total > 0.000001:  # Minimum threshold
                    token_balances.append({
                        'asset': asset,
                        'qty': total
                    })
            except (ValueError, TypeError):
                continue
        
        for token_bal in token_balances:
            asset = token_bal['asset']
            token_qty = token_bal['qty']
                
            symbol = f"{asset}USDT"
            try:
                ticker = await mexc.get_ticker_24h(symbol)
                current_price = float(ticker.get('lastPrice', 0))
                if current_price > 0:
                    current_value = current_price * token_qty
                    invested_value += current_value
                    actual_positions_count += 1
                    
                    # Try to find entry price from local DB for PnL calculation
                    local_pos = next(
                        (p for p in (live_account.open_positions if live_account else []) if p.symbol == symbol),
                        None
                    )
                    if local_pos:
                        total_pnl += (current_price - local_pos.entry_price) * min(token_qty, local_pos.qty)
            except Exception:
                # Token might not have USDT pair, skip
                pass
        
        # Also check local DB positions (in case MEXC balance is delayed)
        if live_account and live_account.open_positions:
            for pos in live_account.open_positions:
                # Check if we already counted this from MEXC balances
                asset = pos.symbol.replace('USDT', '')
                already_counted = any(tb['asset'] == asset for tb in token_balances)
                
                if not already_counted:
                    try:
                        ticker = await mexc.get_ticker_24h(pos.symbol)
                        current_price = float(ticker.get('lastPrice', pos.entry_price))
                        current_value = current_price * pos.qty
                        invested_value += current_value
                        total_pnl += (current_price - pos.entry_price) * pos.qty
                        actual_positions_count += 1
                    except Exception:
                        invested_value += pos.entry_price * pos.qty
                        actual_positions_count += 1
        
        total_pnl_pct = (total_pnl / invested_value * 100) if invested_value > 0 else 0
        
        # RESERVE SYSTEM: Calculate available to bot
        available_to_bot = max(0, usdt_free - settings.reserve_usdt)
        
        # Apply trading budget cap
        budget_remaining = max(0, settings.trading_budget_usdt - entry_value)
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
            # Portfolio Summary
            'invested_value': round(invested_value, 2),
            'total_pnl': round(total_pnl, 4),
            'total_pnl_pct': round(total_pnl_pct, 2),
            # Budget info (simplified - no reserve)
            'budget': {
                'usdt_free': round(usdt_free, 2),
                'used_budget': round(invested_value, 2),
            },
            # Daily Cap
            'daily_cap': {
                'cap': daily_cap,
                'used': round(today_exposure, 2),
                'remaining': round(daily_remaining, 2)
            },
            'open_positions_count': actual_positions_count,
            # AI max positions based on profile
            'ai_max_positions': get_ai_max_positions(settings),
            # AI Position Range based on available USDT
            'ai_position_range': calculate_ai_position_range(settings, usdt_free, invested_value),
            # Futures data
            'futures': await get_futures_balance_data(keys, settings)
        }
        
    except Exception as e:
        logger.error(f"MEXC balance fetch failed for user {user_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch MEXC balance: {str(e)}"
        )

def get_ai_max_positions(settings) -> int:
    """Get max positions based on AI profile"""
    from ai_engine_v2 import TradingMode, RISK_PROFILES_V2
    
    trading_mode = TradingMode(settings.trading_mode) if settings.trading_mode else TradingMode.MANUAL
    
    if trading_mode == TradingMode.MANUAL:
        return settings.max_positions or 3
    
    profile = RISK_PROFILES_V2.get(trading_mode, {})
    return profile.get('max_positions', settings.max_positions or 3)


async def get_futures_balance_data(keys: dict, settings) -> dict:
    """Get futures account balance data"""
    if not settings.futures_enabled or not keys:
        return None
    
    try:
        futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        assets = await futures_client.get_account_asset("USDT")
        positions = await futures_client.get_open_positions()
        
        return {
            'available_balance': float(assets.get("availableBalance", 0)),
            'frozen_balance': float(assets.get("frozenBalance", 0)),
            'equity': float(assets.get("equity", 0)),
            'unrealized_pnl': float(assets.get("unrealisedPnl", 0)),
            'open_positions': len(positions)
        }
    except Exception as e:
        logger.warning(f"Futures balance fetch error: {e}")
        return {
            'available_balance': 0,
            'frozen_balance': 0,
            'equity': 0,
            'unrealized_pnl': 0,
            'open_positions': 0,
            'error': str(e)
        }

def calculate_ai_position_range(settings, usdt_free: float, open_value: float) -> dict:
    """Calculate AI position range based on available USDT and profile"""
    from ai_engine_v2 import TradingMode, RISK_PROFILES_V2
    
    trading_mode = TradingMode(settings.trading_mode) if settings.trading_mode else TradingMode.MANUAL
    
    if trading_mode == TradingMode.MANUAL:
        return {
            'min': settings.live_min_notional_usdt or 5,
            'max': settings.live_max_order_usdt or 50,
            'pct_range': 'Manual'
        }
    
    profile = RISK_PROFILES_V2.get(trading_mode, {})
    position_pct_min = profile.get('position_pct_min', 5)
    position_pct_max = profile.get('position_pct_max', 20)
    
    # Calculate based on AVAILABLE USDT (not trading budget!)
    position_usd_min = usdt_free * (position_pct_min / 100)
    position_usd_max = usdt_free * (position_pct_max / 100)
    
    # Apply trading budget cap
    trading_budget = settings.trading_budget_usdt or 500
    trading_budget_remaining = max(0, trading_budget - open_value)
    position_usd_min = min(position_usd_min, trading_budget_remaining)
    position_usd_max = min(position_usd_max, trading_budget_remaining)
    
    return {
        'min': round(position_usd_min, 2),
        'max': round(position_usd_max, 2),
        'pct_range': f"{position_pct_min:.0f}%-{position_pct_max:.0f}%"
    }

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

@app.post("/api/market/refresh_pairs")
async def refresh_top_pairs(current_user: dict = Depends(get_current_user)):
    """Manually trigger refresh of top trading pairs with intelligent filtering"""
    user_id = current_user['user_id']
    
    # Use the worker's refresh logic
    if worker:
        await worker.refresh_top_pairs(user_id)
        settings = await db.get_settings(user_id)
        return {
            "message": "Coins erfolgreich aktualisiert",
            "pairs_count": len(settings.top_pairs),
            "pairs": settings.top_pairs[:10],  # Show first 10
            "last_refresh": settings.last_pairs_refresh
        }
    else:
        raise HTTPException(status_code=500, detail="Worker not available")

# ============ MANUAL SELL ENDPOINT ============

from pydantic import BaseModel

class ManualSellRequest(BaseModel):
    symbol: str
    position_id: Optional[str] = None  # Optional for backward compatibility
    confirm: bool = False

@app.post("/api/positions/sell")
async def manual_sell_position(
    request: ManualSellRequest,
    current_user: dict = Depends(get_current_user)
):
    """Manually sell a live position at current market price"""
    user_id = current_user['user_id']
    account = await db.get_live_account(user_id)
    
    # Find the position - by ID if provided, otherwise first matching symbol
    position = None
    position_index = -1
    for idx, pos in enumerate(account.open_positions):
        if request.position_id:
            # Match by position ID (new way)
            if getattr(pos, 'id', None) == request.position_id:
                position = pos
                position_index = idx
                break
        elif pos.symbol == request.symbol:
            # Match by symbol only (old way - takes first match)
            position = pos
            position_index = idx
            break
    
    if not position:
        raise HTTPException(status_code=404, detail=f"Position {request.symbol} nicht gefunden")
    
    # Get user's MEXC client (keys are already decrypted by get_mexc_keys)
    keys = await db.get_mexc_keys(user_id)
    if not keys:
        raise HTTPException(status_code=400, detail="MEXC API keys nicht konfiguriert")
    
    mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
    
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
    
    # Remove ONLY this specific position from account (by index, not by symbol)
    if position_index >= 0:
        account.open_positions.pop(position_index)
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

@app.post("/api/positions/sync")
async def sync_positions_with_mexc(current_user: dict = Depends(get_current_user)):
    """Manually trigger sync with MEXC to detect externally sold positions"""
    user_id = current_user['user_id']
    
    if worker:
        await worker.sync_mexc_trades(user_id)
        
        # Return updated positions
        account = await db.get_live_account(user_id)
        return {
            'success': True,
            'message': 'Sync mit MEXC abgeschlossen',
            'open_positions': len(account.open_positions) if account else 0
        }
    else:
        raise HTTPException(status_code=500, detail="Worker not available")

# ============ METRICS ENDPOINTS ============

@app.get("/api/metrics/daily_pnl")
async def get_daily_pnl(
    days: int = 30,
    market_type: Optional[str] = None,  # "spot" or "futures"
    current_user: dict = Depends(get_current_user)
):
    """Get daily PnL aggregation for chart (LIVE only), optionally filtered by market type"""
    user_id = current_user['user_id']
    
    daily_data = await db.get_daily_pnl(user_id, mode='live', days=days, market_type=market_type)
    
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
    market_type: Optional[str] = None,  # "spot" or "futures"
    limit: int = 200,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get paginated trade history (LIVE only), optionally filtered by market type"""
    user_id = current_user['user_id']
    
    trades, total = await db.get_trades_paginated(
        user_id, 
        mode='live',  # Only live trades
        symbol=symbol,
        market_type=market_type,
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


# ============ TELEGRAM ENDPOINTS ============

@app.post("/api/telegram/test")
async def test_telegram(current_user: dict = Depends(get_current_user)):
    """Sende Test-Nachricht an Telegram"""
    global telegram_bot
    
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not telegram_bot or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram nicht konfiguriert")
    
    success = await telegram_bot.send_message(
        int(chat_id),
        "🧪 <b>Test erfolgreich!</b>\n\nReeTrade Terminal ist mit Telegram verbunden."
    )
    
    if success:
        return {"message": "Test-Nachricht gesendet!"}
    else:
        raise HTTPException(status_code=500, detail="Senden fehlgeschlagen")


@app.get("/api/telegram/status")
async def telegram_status(current_user: dict = Depends(get_current_user)):
    """Telegram-Status abrufen"""
    global telegram_bot
    
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    return {
        "configured": bool(token and chat_id),
        "bot_active": telegram_bot is not None,
        "chat_id": chat_id[:5] + "..." if chat_id else None
    }


@app.post("/api/telegram/notify/trade")
async def send_trade_notification(
    trade_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Manuell eine Trade-Benachrichtigung senden"""
    global telegram_bot
    
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not telegram_bot or not chat_id:
        return {"sent": False, "reason": "Telegram nicht konfiguriert"}
    
    if trade_data.get('type') == 'open':
        await telegram_bot.notify_trade_opened(int(chat_id), trade_data)
    else:
        await telegram_bot.notify_trade_closed(int(chat_id), trade_data)
    
    return {"sent": True}

