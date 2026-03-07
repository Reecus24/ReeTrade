from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional, Dict
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
from ml_data_collector import get_ml_collector
from ki_learning_engine import get_ki_engine
from models import PaperAccount, Position
from telegram_bot import TelegramBot, get_telegram_bot

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
    if telegram_bot:
        await telegram_bot.close()
    db.close()


async def telegram_polling_loop():
    """Polling loop für Telegram Befehle"""
    global telegram_bot
    
    if not telegram_bot:
        return
    
    offset = 0
    logger.info("[TELEGRAM] Polling started")
    
    while True:
        try:
            updates = await telegram_bot.get_updates(offset)
            
            for update in updates:
                offset = update['update_id'] + 1
                
                if 'message' in update and 'text' in update['message']:
                    chat_id = update['message']['chat']['id']
                    text = update['message']['text'].strip()
                    
                    # Finde user_id basierend auf chat_id
                    user = await db.users.find_one({"telegram_chat_id": str(chat_id)})
                    user_id = str(user['_id']) if user else None
                    
                    if text.startswith('/'):
                        response = await telegram_bot.handle_command(chat_id, text, user_id)
                        await telegram_bot.send_message(chat_id, response)
            
            await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            logger.info("[TELEGRAM] Polling stopped")
            break
        except Exception as e:
            logger.error(f"[TELEGRAM] Polling error: {e}")
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
            'live_max_order_usdt': settings.live_max_order_usdt,
            'live_min_notional_usdt': settings.live_min_notional_usdt,
            # BOT STATUS TRACKING
            'live_last_scan': settings.live_last_scan,
            'live_last_decision': settings.live_last_decision,
            'live_last_regime': settings.live_last_regime,
            'live_last_symbol': settings.live_last_symbol,
            'live_budget_used': settings.live_budget_used,
            'live_budget_available': settings.live_budget_available,
            'live_positions_count': settings.live_positions_count,
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
    """Add current prices, real MEXC balances, AND dust status to positions for live PnL display"""
    from order_sizer import order_sizer
    
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
            
            # Update order_sizer filters for dust detection
            try:
                exchange_info = await mexc.get_exchange_info()
                order_sizer.update_symbol_filters(exchange_info)
            except Exception as e:
                logger.warning(f"Could not update exchange filters: {e}")
                
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
        current_price = 0
        if mexc:
            try:
                ticker = await mexc.get_ticker_24h(pos.symbol)
                current_price = float(ticker.get('lastPrice', 0))
                pos_dict['current_price'] = current_price
            except Exception:
                pos_dict['current_price'] = 0
        else:
            pos_dict['current_price'] = 0
        
        # DUST DETECTION: Check if position is too small to sell
        qty = pos_dict.get('qty', 0)
        if current_price > 0 and qty > 0:
            dust_status = order_sizer.get_dust_status(pos.symbol, qty, current_price)
            pos_dict['is_dust'] = dust_status['is_dust']
            pos_dict['can_sell'] = dust_status['can_sell']
            pos_dict['dust_reason'] = dust_status.get('reason')
            pos_dict['estimated_notional'] = dust_status.get('estimated_notional', 0)
        else:
            pos_dict['is_dust'] = False
            pos_dict['can_sell'] = True
            pos_dict['dust_reason'] = None
        
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
    
    # Map frontend field names to backend field names
    if 'max_notional_usdt' in updates_dict:
        updates_dict['live_max_order_usdt'] = updates_dict.pop('max_notional_usdt')
    if 'min_notional_usdt' in updates_dict:
        updates_dict['live_min_notional_usdt'] = updates_dict['min_notional_usdt']
    
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
    """Get all available SPOT coins from MEXC"""
    user_id = current_user['user_id']
    
    keys = await db.get_mexc_keys(user_id)
    if not keys:
        return {"spot_coins": [], "error": "API Keys nicht konfiguriert"}
    
    spot_coins = []
    
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
    
    return {
        "spot_coins": spot_coins,
        "spot_count": len(spot_coins)
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


@app.get("/api/keys/mexc/status")
async def get_mexc_keys_status(current_user: dict = Depends(get_current_user)):
    """Get MEXC keys connection status"""
    user_id = current_user['user_id']
    
    # Get status from DB
    basic_status = await db.get_mexc_keys_status(user_id)
    
    result = {
        'connected': basic_status.get('spot_connected', False),
        'last_updated': basic_status.get('last_updated'),
        'error': None
    }
    
    # Verify SPOT keys with real API call
    if result['connected']:
        try:
            keys = await db.get_mexc_keys(user_id, key_type='spot')
            if keys:
                mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
                await mexc.get_account()
        except Exception as e:
            result['connected'] = False
            result['error'] = f'{str(e)[:50]}'
    
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
        
        # ============ TOTAL MEXC VALUE (alle Assets) ============
        # Berechne den Gesamtwert ALLER Assets auf MEXC (nicht nur Bot-Positionen)
        total_mexc_value = usdt_total  # Start mit USDT
        
        for b in balances:
            asset = b.get('asset', '')
            if asset == 'USDT':
                continue
            try:
                free = float(b.get('free', 0) or 0)
                locked = float(b.get('locked', 0) or 0)
                total_qty = free + locked
                if total_qty > 0.000001:
                    symbol = f"{asset}USDT"
                    ticker = await mexc.get_ticker_24h(symbol)
                    current_price = float(ticker.get('lastPrice', 0))
                    if current_price > 0:
                        total_mexc_value += current_price * total_qty
            except Exception:
                pass  # Skip assets without USDT pair
        
        # ============ BOT-TRACKED POSITIONS (für PnL) ============
        # ONLY count positions tracked by the bot (from local DB)
        invested_value = 0
        total_pnl = 0
        actual_positions_count = 0
        
        # Get tracked positions from local DB and calculate their current value
        if live_account and live_account.open_positions:
            for pos in live_account.open_positions:
                try:
                    ticker = await mexc.get_ticker_24h(pos.symbol)
                    current_price = float(ticker.get('lastPrice', pos.entry_price))
                    current_value = current_price * pos.qty
                    invested_value += current_value
                    total_pnl += (current_price - pos.entry_price) * pos.qty
                    actual_positions_count += 1
                except Exception:
                    # Fallback to entry price if ticker fails
                    invested_value += pos.entry_price * pos.qty
                    actual_positions_count += 1
        
        total_pnl_pct = (total_pnl / invested_value * 100) if invested_value > 0 else 0
        
        # RESERVE SYSTEM: Calculate available to bot
        available_to_bot = max(0, usdt_free - settings.reserve_usdt)
        
        # Apply trading budget cap
        budget_remaining = max(0, settings.trading_budget_usdt - entry_value)
        remaining_budget = min(available_to_bot, budget_remaining)
        
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
        
        # Serialize open_positions from local DB (source of truth for frontend)
        # Include LIVE current prices from MEXC
        open_positions_serialized = []
        if live_account and live_account.open_positions:
            for pos in live_account.open_positions:
                # Hole aktuellen Preis von MEXC
                current_price = None
                try:
                    ticker = await mexc.get_ticker_24h(pos.symbol)
                    if ticker:
                        current_price = float(ticker.get('lastPrice', 0))
                except:
                    current_price = None
                
                open_positions_serialized.append({
                    'id': str(pos.id) if hasattr(pos, 'id') else None,
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'qty': pos.qty,
                    'entry_price': pos.entry_price,
                    'current_price': current_price,
                    'stop_loss': getattr(pos, 'stop_loss', None),
                    'take_profit': getattr(pos, 'take_profit', None),
                    'entry_time': pos.entry_time.isoformat() if hasattr(pos, 'entry_time') and pos.entry_time else None
                })
        
        # Use local DB positions count as source of truth (matches PositionsPanel)
        local_positions_count = len(open_positions_serialized)
        
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
            'invested_value': round(invested_value, 2),  # Nur Bot-Positionen
            'total_value': round(total_mexc_value, 2),   # GESAMTES MEXC Konto
            'total_pnl': round(total_pnl, 4),
            'total_pnl_pct': round(total_pnl_pct, 2),
            # Budget info (simplified - no reserve)
            'budget': {
                'usdt_free': round(usdt_free, 2),
                'used_budget': round(invested_value, 2),
            },
            # Open positions from local DB (source of truth)
            'open_positions': open_positions_serialized,
            'open_positions_count': local_positions_count,
            # AI max positions based on profile
            'ai_max_positions': get_ai_max_positions(settings),
            # AI Position Range based on available USDT
            'ai_position_range': calculate_ai_position_range(settings, usdt_free, invested_value)
        }
        
    except Exception as e:
        logger.error(f"MEXC balance fetch failed for user {user_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch MEXC balance: {str(e)}"
        )

def get_ai_max_positions(settings) -> int:
    """Get max positions - USER SETTING HAT IMMER PRIORITÄT"""
    # Die User-Einstellung hat immer Priorität, nicht das AI-Profil
    return settings.max_positions or 3


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
    from order_sizer import order_sizer
    
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
    
    # Get current price first
    ticker = await mexc.get_ticker_24h(request.symbol)
    current_price = float(ticker['lastPrice'])
    
    # DUST CHECK: Block sell for dust positions
    is_dust, dust_details = order_sizer.is_dust_position(position.symbol, position.qty, current_price)
    if is_dust:
        raise HTTPException(
            status_code=400, 
            detail=f"Dust-Position kann nicht verkauft werden: {dust_details.get('reason')} "
                   f"(Wert: ~${dust_details.get('estimated_notional', 0):.4f})"
        )
    
    # If not confirmed, return position details for confirmation
    if not request.confirm:
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
    
    # Execute real sell on MEXC (current_price already fetched above)
    try:
        # Use order_sizer to format quantity properly
        is_valid, msg, formatted_qty = order_sizer.prepare_sell_quantity(
            symbol=request.symbol,
            available_qty=position.qty,
            current_price=current_price
        )
        
        if not is_valid or formatted_qty is None:
            raise HTTPException(status_code=400, detail=f"Verkauf nicht möglich: {msg}")
        
        order_result = await mexc.place_order(
            symbol=request.symbol,
            side="SELL",
            order_type="MARKET",
            quantity=formatted_qty
        )
        order_id = order_result.get('orderId')
        
        executed_price = current_price
        if order_result.get('executedQty') and order_result.get('cummulativeQuoteQty'):
            actual_qty = float(order_result.get('executedQty'))
            if actual_qty > 0:
                executed_price = float(order_result.get('cummulativeQuoteQty')) / actual_qty
        
        if not order_id:
            raise HTTPException(status_code=500, detail="MEXC Order fehlgeschlagen - keine Order ID")
            
    except HTTPException:
        raise
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
    market_type: Optional[str] = None,  # Optional filter
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
    market_type: Optional[str] = None,  # Optional filter
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

@app.get("/api/telegram/status")
async def get_telegram_status(current_user: dict = Depends(get_current_user)):
    """Get Telegram connection status for current user"""
    user_id = current_user['user_id']
    
    # Check if bot is configured
    bot_configured = telegram_bot is not None
    
    # Check if user has linked Telegram
    from bson import ObjectId
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    user_linked = bool(user and user.get('telegram_chat_id'))
    
    return {
        "bot_configured": bot_configured,
        "user_linked": user_linked,
        "chat_id_preview": user['telegram_chat_id'][:5] + "..." if user_linked else None
    }


@app.post("/api/telegram/link")
async def link_telegram(data: dict, current_user: dict = Depends(get_current_user)):
    """
    Link Telegram account using code from Telegram Bot
    User tippt /link in Telegram → bekommt Code → gibt Code hier ein
    """
    user_id = current_user['user_id']
    code = data.get('code', '').upper().strip()
    
    if not code:
        raise HTTPException(status_code=400, detail="Code ist erforderlich")
    
    # Suche Code in DB
    link_doc = await db.db.telegram_link_codes.find_one({'code': code, 'used': False})
    
    if not link_doc:
        raise HTTPException(
            status_code=400, 
            detail="Ungültiger Code. Tippe /link im Telegram Bot für einen neuen Code."
        )
    
    # Prüfe Expiration
    expires_at = link_doc.get('expires_at')
    if expires_at:
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            await db.db.telegram_link_codes.delete_one({'code': code})
            raise HTTPException(
                status_code=400, 
                detail="Code abgelaufen. Tippe /link im Telegram Bot für einen neuen Code."
            )
    
    chat_id = link_doc.get('chat_id')
    if not chat_id:
        raise HTTPException(status_code=400, detail="Ungültiger Code (keine Chat-ID)")
    
    # Verknüpfe User mit Telegram Chat
    from bson import ObjectId
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"telegram_chat_id": chat_id}}
    )
    
    # Markiere Code als verwendet
    await db.db.telegram_link_codes.update_one(
        {'code': code},
        {'$set': {'used': True, 'linked_user_id': user_id}}
    )
    
    # Log
    await db.log(user_id, "INFO", f"Telegram verknüpft (Chat: {chat_id[:5]}...)")
    
    # Sende Bestätigung an Telegram
    if telegram_bot:
        await telegram_bot.send_message(
            int(chat_id),
            "✅ <b>Erfolgreich verknüpft!</b>\n\nDu erhältst jetzt Trading-Benachrichtigungen.\n\nTippe /help für alle Befehle."
        )
    
    return {"message": "Telegram erfolgreich verknüpft!", "linked": True}


@app.post("/api/telegram/unlink")
async def unlink_telegram(current_user: dict = Depends(get_current_user)):
    """Unlink Telegram account"""
    user_id = current_user['user_id']
    
    from bson import ObjectId
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$unset": {"telegram_chat_id": ""}}
    )
    
    await db.log(user_id, "INFO", "Telegram-Konto getrennt")
    
    return {"message": "Telegram getrennt", "linked": False}


@app.post("/api/telegram/test")
async def test_telegram(current_user: dict = Depends(get_current_user)):
    """Send test message to linked Telegram"""
    user_id = current_user['user_id']
    
    if not telegram_bot:
        raise HTTPException(status_code=400, detail="Telegram Bot nicht konfiguriert")
    
    from bson import ObjectId
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user or not user.get('telegram_chat_id'):
        raise HTTPException(status_code=400, detail="Telegram nicht verknüpft")
    
    chat_id = user['telegram_chat_id']
    
    success = await telegram_bot.send_message(
        int(chat_id),
        "🧪 <b>Test erfolgreich!</b>\n\nReeTrade ist mit deinem Telegram verbunden."
    )
    
    if success:
        return {"message": "Test-Nachricht gesendet!"}
    else:
        raise HTTPException(status_code=500, detail="Senden fehlgeschlagen")


# ============ ML MODEL STATUS ============

@app.get("/api/ml/status")
async def get_ml_status(current_user: dict = Depends(get_current_user)):
    """Get ML Model Status"""
    from ml_trading_model import get_ml_model
    
    ml_model = get_ml_model(db)
    status = ml_model.get_status()
    
    return {
        "ml_available": status['ml_available'],
        "model_trained": status['model_trained'],
        "training_samples": status['training_samples'],
        "min_samples_needed": status['min_samples_needed'],
        "model_accuracy": status['model_accuracy'],
        "exploration_mode": status['exploration_mode'],
        "message": "ML sammelt Daten" if status['exploration_mode'] else f"ML trainiert mit {status['model_accuracy']:.1%} Genauigkeit"
    }


@app.post("/api/ml/train")
async def train_ml_model(current_user: dict = Depends(get_current_user)):
    """Manuell ML-Modell trainieren"""
    from ml_trading_model import get_ml_model
    
    user_id = current_user['user_id']
    ml_model = get_ml_model(db)
    
    success = await ml_model.train_model(user_id)
    
    if success:
        return {
            "success": True,
            "message": f"ML-Modell trainiert! Accuracy: {ml_model.model_accuracy:.1%}",
            "accuracy": ml_model.model_accuracy
        }
    else:
        return {
            "success": False,
            "message": f"Brauche mindestens {ml_model.MIN_SAMPLES_FOR_TRAINING} Trades. Aktuell: {len(ml_model.training_data)}",
            "samples": len(ml_model.training_data)
        }


@app.get("/api/rl/status")
async def get_rl_status(current_user: dict = Depends(get_current_user)):
    """Get Reinforcement Learning AI Status"""
    from rl_trading_ai import get_rl_trading_ai
    
    rl_ai = get_rl_trading_ai(db)
    status = rl_ai.get_status()
    
    # Berechne Lernfortschritt und Exploitation Readiness
    epsilon = status.get('exploration_pct', 100) / 100  # 0-1
    total_trades = status['total_trades']
    
    # Exploitation wird dominant ab epsilon < 0.5 (50%)
    exploitation_threshold = 0.5
    is_exploration_phase = epsilon > 0.8
    is_transitioning = 0.5 <= epsilon <= 0.8
    is_exploitation_ready = epsilon < exploitation_threshold
    
    # Geschätzter Lernfortschritt (0-100%)
    # Basiert auf: Trades (max 50 für 50%) + Epsilon-Reduktion (max 50%)
    trade_progress = min(total_trades / 100, 0.5) * 100  # 50% aus Trades
    epsilon_progress = (1 - epsilon) * 50  # 50% aus Epsilon-Reduktion
    learning_progress = trade_progress + epsilon_progress
    
    # Geschätzte Trades bis Exploitation dominant
    # Epsilon decay: epsilon = max(0.1, 1.0 - trades * decay_rate)
    # Bei decay_rate ~0.01 braucht man ~50 Trades für 50% Exploitation
    trades_until_exploitation = max(0, int((epsilon - exploitation_threshold) / 0.01)) if epsilon > exploitation_threshold else 0
    
    return {
        "model_type": status['model_type'],
        "total_trades": status['total_trades'],
        "winning_trades": status['winning_trades'],
        "win_rate": status['win_rate'],
        "win_rate_pct": f"{status['win_rate']*100:.1f}%",
        "exploration_pct": status['exploration_pct'],
        "epsilon": epsilon,
        "is_learning": status['is_learning'],
        "memory_size": status['memory_size'],
        "active_episodes": status['active_episodes'],
        
        # ============ EXIT STATISTIKEN ============
        "exit_stats": status.get('exit_stats', {}),
        
        # Neuer Lernstatus
        "learning_status": {
            "phase": "exploration" if is_exploration_phase else ("transition" if is_transitioning else "exploitation"),
            "is_exploration_phase": is_exploration_phase,
            "is_transitioning": is_transitioning,
            "is_exploitation_ready": is_exploitation_ready,
            "learning_progress_pct": round(learning_progress, 1),
            "trades_until_exploitation": trades_until_exploitation,
            "exploitation_threshold": exploitation_threshold * 100,
            "status_message": (
                "🎲 Lernphase – KI exploriert hauptsächlich random" if is_exploration_phase else
                "📈 Übergangsphase – KI lernt aktiv" if is_transitioning else
                "🎯 Exploitation-Modus – KI nutzt gelerntes Wissen"
            )
        },
        
        "message": f"RL-KI: {status['total_trades']} Trades, {status['win_rate']*100:.1f}% Win-Rate, {status['exploration_pct']:.0f}% Exploration"
    }


@app.post("/api/rl/reset")
async def reset_rl_model(
    current_user: dict = Depends(get_current_user)
):
    """
    Setzt die RL-KI komplett zurück für einen sauberen Neustart.
    
    ACHTUNG: Dies löscht ALLE Daten!
    - Replay Buffer (alle Erfahrungen)
    - Neural Networks (alle gelernten Gewichte)
    - Trade-Statistiken
    - Trade-Historie in der Datenbank
    - Epsilon wird auf 1.0 zurückgesetzt
    
    Ein Backup wird automatisch erstellt.
    """
    from rl_trading_ai import get_rl_trading_ai
    
    user_id = current_user['user_id']
    
    # Log the reset action
    await db.log(user_id, "WARNING", "[RL] 🔄 KOMPLETTER RESET angefordert vom Benutzer")
    
    # 1. Zähle alte Trades
    old_trades_count = await db.db.trades.count_documents({"user_id": user_id})
    
    # 2. Lösche Trade-Historie aus MongoDB
    delete_result = await db.db.trades.delete_many({"user_id": user_id})
    deleted_trades = delete_result.deleted_count
    
    await db.log(user_id, "WARNING", f"[RL] 🗑️ {deleted_trades} Trades aus der Datenbank gelöscht")
    
    # 3. Get the RL AI instance and reset it
    rl_ai = get_rl_trading_ai(db)
    result = rl_ai.reset_model(reason=f"User {user_id} requested full reset via API")
    
    await db.log(user_id, "WARNING", f"[RL] ✅ KOMPLETTER RESET abgeschlossen! Gelöscht: {deleted_trades} Trades, {result['old_stats']['memory']} Memory-Einträge")
    
    return {
        "success": result['success'],
        "message": "RL-KI wurde komplett zurückgesetzt!",
        "old_stats": {
            **result['old_stats'],
            "db_trades_deleted": deleted_trades
        },
        "new_stats": result['new_stats'],
        "backup_created": result.get('backup_path') is not None,
        "info": "Die KI startet jetzt mit 100% Exploration und lernt von Grund auf neu. Trade-Historie wurde gelöscht."
    }


@app.get("/api/coin-stats")
async def get_coin_stats(current_user: dict = Depends(get_current_user)):
    """
    Holt aggregierte Statistiken pro Coin.
    
    Zeigt für jeden gehandelten Coin:
    - Durchschnittlicher Spread
    - Durchschnittliche Slippage
    - Durchschnittlicher Net PnL
    - Winrate
    - Profit Factor
    - Edge After Costs
    - Anzahl Trades
    - MFE/MAE Durchschnitte
    """
    user_id = current_user['user_id']
    
    stats = await db.get_coin_stats(user_id)
    
    # Formatiere für Frontend
    formatted_stats = []
    for s in stats:
        formatted_stats.append({
            'symbol': s.get('symbol', ''),
            'trade_count': s.get('trade_count', 0),
            'avg_spread_pct': round(s.get('avg_spread', 0) or 0, 4),
            'avg_slippage_pct': round(s.get('avg_slippage', 0) or 0, 4),
            'avg_net_pnl_pct': round(s.get('avg_net_pnl', 0) or 0, 3),
            'avg_gross_pnl_pct': round(s.get('avg_gross_pnl', 0) or 0, 3),
            'winrate': round(s.get('winrate', 0) or 0, 1),
            'profit_factor': round(s.get('profit_factor', 0) or 0, 2),
            'edge_after_costs': round(s.get('edge_after_costs', 0) or 0, 4),
            'total_net_pnl_dollar': round(s.get('total_net_pnl', 0) or 0, 2),
            'avg_hold_seconds': round(s.get('avg_hold_seconds', 0) or 0, 0),
            'avg_mfe_pct': round(s.get('avg_mfe', 0) or 0, 3),
            'avg_mae_pct': round(s.get('avg_mae', 0) or 0, 3),
            'total_fees': round(s.get('total_fees', 0) or 0, 4),
            'total_notional': round(s.get('total_notional', 0) or 0, 2),
            # Bewertung: Ist dieser Coin profitabel?
            'is_profitable': (s.get('edge_after_costs', 0) or 0) > 0,
            'recommendation': (
                '✅ Profitabel' if (s.get('edge_after_costs', 0) or 0) > 0.1 else
                '⚠️ Grenzwertig' if (s.get('edge_after_costs', 0) or 0) > -0.1 else
                '❌ Unprofitabel'
            )
        })
    
    return {
        'coins': formatted_stats,
        'total_coins': len(formatted_stats),
        'profitable_coins': sum(1 for s in formatted_stats if s['is_profitable']),
        'summary': {
            'best_coin': max(formatted_stats, key=lambda x: x['edge_after_costs'])['symbol'] if formatted_stats else None,
            'worst_coin': min(formatted_stats, key=lambda x: x['edge_after_costs'])['symbol'] if formatted_stats else None,
        }
    }


@app.get("/api/mfe-mae-analysis")
async def get_mfe_mae_analysis(
    current_user: dict = Depends(get_current_user),
    limit: int = 100
):
    """
    Analysiert MFE (Maximum Favorable Excursion) und MAE (Maximum Adverse Excursion).
    
    Gibt Insights darüber:
    - Wieviel vom maximalen Profit wurde realisiert?
    - Werden Trades zu früh oder zu spät geschlossen?
    - Wie tief gehen Trades ins Minus bevor sie sich erholen/geschlossen werden?
    """
    user_id = current_user['user_id']
    
    analysis = await db.get_mfe_mae_analysis(user_id, limit)
    
    return analysis


@app.get("/api/rl/hold-duration-analysis")
async def get_hold_duration_analysis(
    current_user: dict = Depends(get_current_user),
    days: int = 7,
    all_time: bool = False
):
    """
    Detaillierte Analyse der Hold-Duration-Verteilung.
    
    Prüft ob die KI zu früh verkauft (direkt nach MIN_HOLD_SECONDS).
    
    Parameter:
    - days: Anzahl Tage zurück (default 7)
    - all_time: Wenn True, werden ALLE Trades analysiert (ignoriert days)
    """
    from datetime import timezone
    from collections import defaultdict
    
    user_id = current_user['user_id']
    
    # Hole Trades - erweiterte Abfrage
    if all_time:
        cutoff = datetime(2020, 1, 1)  # Praktisch alle Trades
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Zuerst: Alle Trades mit exit_time zählen
    all_trades_with_exit = await db.trades.find({
        'user_id': user_id,
        'exit_time': {'$exists': True, '$ne': None}
    }).to_list(1000)
    
    # Dann: Mit entry_time Filter
    trades = []
    trades_without_entry = 0
    trades_old = 0
    
    for trade in all_trades_with_exit:
        entry = trade.get('entry_time')
        if not entry:
            trades_without_entry += 1
            continue
        
        # Parse entry_time
        if isinstance(entry, str):
            try:
                entry = datetime.fromisoformat(entry.replace('Z', '+00:00'))
            except:
                trades_without_entry += 1
                continue
        
        # Prüfe ob im Zeitraum
        try:
            if entry.replace(tzinfo=None) < cutoff.replace(tzinfo=None):
                trades_old += 1
                continue
        except:
            pass
        
        trades.append(trade)
    
    # Debug info
    debug_info = {
        'total_with_exit': len(all_trades_with_exit),
        'trades_without_entry_time': trades_without_entry,
        'trades_older_than_cutoff': trades_old,
        'trades_in_period': len(trades),
        'cutoff_date': cutoff.isoformat() if cutoff else None
    }
    
    # Buckets für Hold Duration
    buckets = {
        '90-120s': {'count': 0, 'pnls': [], 'winners': 0},
        '120-180s': {'count': 0, 'pnls': [], 'winners': 0},
        '180-300s': {'count': 0, 'pnls': [], 'winners': 0},
        '300-600s': {'count': 0, 'pnls': [], 'winners': 0},
        '600s+': {'count': 0, 'pnls': [], 'winners': 0}
    }
    
    # Exit Source Tracking
    exit_sources = defaultdict(lambda: {'count': 0, 'pnl_sum': 0, 'hold_times': []})
    
    # Immediate exits (90-95s)
    immediate_exits = []
    
    # Exploitation hold distribution
    exploitation_holds = []
    
    for trade in trades:
        entry = trade.get('entry_time')
        exit_time = trade.get('exit_time')
        
        if not entry or not exit_time:
            continue
        
        # Parse datetime
        if isinstance(entry, str):
            entry = datetime.fromisoformat(entry.replace('Z', '+00:00'))
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
        
        # Calculate hold duration
        try:
            hold_secs = (exit_time - entry).total_seconds()
        except:
            continue
        
        pnl = trade.get('pnl_pct', 0) or 0
        exit_source = trade.get('exit_reason', trade.get('sell_source', 'unknown'))
        
        # Exit Source tracking
        exit_sources[exit_source]['count'] += 1
        exit_sources[exit_source]['pnl_sum'] += pnl
        exit_sources[exit_source]['hold_times'].append(hold_secs)
        
        # Exploitation tracking
        if exit_source in ['exploitation', 'ai_exit']:
            exploitation_holds.append(hold_secs)
        
        # Bucket assignment
        if hold_secs < 90:
            continue
        elif hold_secs < 120:
            bucket = '90-120s'
        elif hold_secs < 180:
            bucket = '120-180s'
        elif hold_secs < 300:
            bucket = '180-300s'
        elif hold_secs < 600:
            bucket = '300-600s'
        else:
            bucket = '600s+'
        
        buckets[bucket]['count'] += 1
        buckets[bucket]['pnls'].append(pnl)
        if pnl > 0:
            buckets[bucket]['winners'] += 1
        
        # Immediate exit tracking (90-95s)
        if 90 <= hold_secs <= 95:
            immediate_exits.append({
                'symbol': trade.get('symbol'),
                'hold_seconds': round(hold_secs, 1),
                'pnl_pct': round(pnl, 3),
                'exit_source': exit_source
            })
    
    # Calculate bucket stats
    total_trades = sum(b['count'] for b in buckets.values())
    bucket_stats = []
    for bucket_name, data in buckets.items():
        count = data['count']
        bucket_stats.append({
            'bucket': bucket_name,
            'count': count,
            'percentage': round(count / total_trades * 100, 1) if total_trades > 0 else 0,
            'avg_pnl': round(sum(data['pnls']) / count, 3) if count > 0 else 0,
            'winners': data['winners'],
            'win_rate': round(data['winners'] / count * 100, 1) if count > 0 else 0
        })
    
    # Exit source stats
    exit_source_stats = []
    for source, data in sorted(exit_sources.items(), key=lambda x: -x[1]['count']):
        count = data['count']
        exit_source_stats.append({
            'source': source,
            'count': count,
            'percentage': round(count / total_trades * 100, 1) if total_trades > 0 else 0,
            'avg_pnl': round(data['pnl_sum'] / count, 3) if count > 0 else 0,
            'avg_hold_seconds': round(sum(data['hold_times']) / count, 1) if count > 0 else 0
        })
    
    # Exploitation hold distribution
    exploitation_distribution = {
        '90-95s': 0, '95-100s': 0, '100-110s': 0, '110-120s': 0,
        '120-150s': 0, '150-180s': 0, '180-240s': 0, '240-300s': 0, '300s+': 0
    }
    for h in exploitation_holds:
        if h < 95: exploitation_distribution['90-95s'] += 1
        elif h < 100: exploitation_distribution['95-100s'] += 1
        elif h < 110: exploitation_distribution['100-110s'] += 1
        elif h < 120: exploitation_distribution['110-120s'] += 1
        elif h < 150: exploitation_distribution['120-150s'] += 1
        elif h < 180: exploitation_distribution['150-180s'] += 1
        elif h < 240: exploitation_distribution['180-240s'] += 1
        elif h < 300: exploitation_distribution['240-300s'] += 1
        else: exploitation_distribution['300s+'] += 1
    
    # Immediate exit analysis
    immediate_by_source = defaultdict(lambda: {'count': 0, 'pnl_sum': 0})
    for e in immediate_exits:
        src = e['exit_source']
        immediate_by_source[src]['count'] += 1
        immediate_by_source[src]['pnl_sum'] += e['pnl_pct']
    
    immediate_stats = []
    for src, data in immediate_by_source.items():
        immediate_stats.append({
            'source': src,
            'count': data['count'],
            'avg_pnl': round(data['pnl_sum'] / data['count'], 3) if data['count'] > 0 else 0
        })
    
    # Diagnose
    diagnosis = []
    immediate_ratio = len(immediate_exits) / total_trades if total_trades > 0 else 0
    if immediate_ratio > 0.5:
        diagnosis.append({
            'severity': 'HIGH',
            'issue': 'Zu viele Immediate Exits',
            'detail': f'{immediate_ratio*100:.1f}% der Trades werden bei 90-95s geschlossen',
            'suggestion': 'q_diff Threshold erhöhen oder MIN_HOLD_SECONDS anpassen'
        })
    
    if bucket_stats[0]['count'] > 0:  # 90-120s bucket
        short_bucket_pnl = bucket_stats[0]['avg_pnl']
        if short_bucket_pnl < -0.1:
            diagnosis.append({
                'severity': 'MEDIUM',
                'issue': 'Kurze Trades unprofitabel',
                'detail': f'90-120s Bucket: Avg PnL {short_bucket_pnl:+.3f}%',
                'suggestion': 'KI lernt möglicherweise falsches Muster - längere Haltezeiten testen'
            })
    
    return {
        'total_trades': total_trades,
        'analysis_period_days': days,
        'debug': debug_info,  # Debug-Infos für Diagnose
        'bucket_analysis': bucket_stats,
        'exit_source_analysis': exit_source_stats,
        'exploitation_hold_distribution': [
            {'bucket': k, 'count': v} for k, v in exploitation_distribution.items()
        ],
        'immediate_exits': {
            'count': len(immediate_exits),
            'percentage': round(immediate_ratio * 100, 1),
            'by_source': immediate_stats,
            'examples': immediate_exits[:10]
        },
        'diagnosis': diagnosis
    }


@app.get("/api/rl/trading-stats")
async def get_rl_trading_stats(
    current_user: dict = Depends(get_current_user),
    hours: int = 24
):
    """
    Comprehensive RL Trading Statistics
    
    Supported periods: 1h, 6h, 24h
    
    Returns:
    - Hold stats (avg, min, max)
    - Net PnL stats (avg, total, theoretical comparison)
    - Fees analysis (total, ratio)
    - Sell source breakdown (exploitation, random, emergency, time_limit)
    - Trade counts (total, winning, losing)
    - Core performance (win rate, avg win/loss, profit factor)
    - RL-specific metrics (exploration ratio, duration by outcome)
    - Health status (healthy/warning/critical with reasons)
    """
    user_id = current_user['user_id']
    
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()  # Convert to string for comparison
    
    # Fetch all closed trades in period
    # Note: ts is stored as ISO string, so we compare strings
    trades = await db.db.trades.find({
        "user_id": user_id,
        "ts": {"$gte": cutoff_str},
        "side": "SELL"  # Only closed trades
    }).to_list(1000)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NO DATA CASE
    # ═══════════════════════════════════════════════════════════════════════════
    if not trades:
        return {
            "period_hours": hours,
            "total_closed_trades": 0,
            
            # Hold stats
            "hold_stats": {
                "avg_hold_seconds": 0,
                "min_hold_seconds": 0,
                "max_hold_seconds": 0,
                "avg_hold_formatted": "0m 0s",
                "min_hold_formatted": "0m 0s",
                "max_hold_formatted": "0m 0s"
            },
            
            # Net PnL stats
            "pnl_stats": {
                "avg_net_pnl_usdt": 0,
                "avg_net_pnl_pct": 0,
                "avg_theoretical_pnl_pct": 0,
                "total_net_pnl_usdt": 0,
                "total_net_pnl_pct": 0,
                "total_theoretical_pnl_pct": 0,
                "pnl_gap_pct": 0
            },
            
            # Fees
            "fee_stats": {
                "total_fees_paid": 0,
                "total_slippage": 0,
                "total_costs": 0,
                "fee_ratio_pct": 0
            },
            
            # Sell sources
            "sell_sources": {
                "counts": {"exploitation": 0, "random_exploration": 0, "emergency": 0, "time_limit": 0, "unknown": 0},
                "percentages": {"exploitation": 0, "random_exploration": 0, "emergency": 0, "time_limit": 0, "unknown": 0}
            },
            
            # Trade counts
            "trade_counts": {
                "total": 0,
                "winning": 0,
                "losing": 0
            },
            
            # Performance
            "performance": {
                "win_rate_pct": 0,
                "avg_win_usdt": 0,
                "avg_loss_usdt": 0,
                "avg_win_pct": 0,
                "avg_loss_pct": 0,
                "profit_factor": 0,
                "gross_profit": 0,
                "gross_loss": 0
            },
            
            # RL metrics
            "rl_metrics": {
                "exploration_sell_ratio_pct": 0,
                "exploitation_sell_ratio_pct": 0,
                "avg_duration_winning": 0,
                "avg_duration_losing": 0,
                "avg_duration_winning_formatted": "0m 0s",
                "avg_duration_losing_formatted": "0m 0s"
            },
            
            # Health status
            "health": {
                "status": "warning",
                "status_color": "yellow",
                "reasons": ["no_data"]
            }
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DATA COLLECTION
    # ═══════════════════════════════════════════════════════════════════════════
    durations = []
    durations_winning = []
    durations_losing = []
    
    net_pnls_pct = []
    net_pnls_usdt = []
    theoretical_pnls_pct = []
    
    winning_pnls_usdt = []
    winning_pnls_pct = []
    losing_pnls_usdt = []
    losing_pnls_pct = []
    
    total_fees = 0
    total_slippage = 0
    total_notional = 0
    
    sell_sources = {
        "exploitation": 0,
        "random_exploration": 0,
        "emergency": 0,
        "time_limit": 0,
        "unknown": 0
    }
    
    # Neue Metriken für Edge Analysis
    mfe_values = []  # Max Favorable Excursion
    mae_values = []  # Max Adverse Excursion
    spread_values = []  # Spreads
    slippage_per_trade = []  # Slippage pro Trade
    trade_timestamps = []  # Für Frequency Analysis
    price_moves = []  # Actual price moves
    
    for t in trades:
        # Duration
        duration = t.get('duration_seconds') or 0
        durations.append(duration)
        
        # PnL (USDT)
        pnl_usdt = t.get('pnl') or 0
        net_pnls_usdt.append(pnl_usdt)
        
        # PnL (%)
        net_pnl_pct = t.get('pnl_pct') or 0
        net_pnls_pct.append(net_pnl_pct)
        
        # Theoretical PnL (gross before fees)
        theoretical_pct = t.get('gross_pnl_pct') or net_pnl_pct
        theoretical_pnls_pct.append(theoretical_pct)
        
        # Winning vs Losing
        if pnl_usdt > 0:
            winning_pnls_usdt.append(pnl_usdt)
            winning_pnls_pct.append(net_pnl_pct)
            durations_winning.append(duration)
        elif pnl_usdt < 0:
            losing_pnls_usdt.append(pnl_usdt)
            losing_pnls_pct.append(net_pnl_pct)
            durations_losing.append(duration)
        
        # Fees & Costs
        fees = t.get('fees_paid') or 0
        slippage = t.get('slippage_cost') or 0
        notional = t.get('notional') or 0
        
        total_fees += fees
        total_slippage += slippage
        total_notional += notional
        
        # MFE/MAE (Trade Quality)
        mfe = t.get('mfe') or 0  # Max profit during trade
        mae = t.get('mae') or 0  # Max loss during trade
        mfe_values.append(mfe)
        mae_values.append(mae)
        
        # Spread & Slippage per trade
        spread = t.get('spread_pct') or 0
        spread_values.append(spread)
        slippage_per_trade.append(slippage)
        
        # Timestamp for frequency analysis
        ts = t.get('ts')
        if ts:
            trade_timestamps.append(ts)
        
        # Price move (absolute)
        price_move = abs(theoretical_pct) if theoretical_pct else 0
        price_moves.append(price_move)
        
        # Sell source extraction
        reason = (t.get('reason') or '').lower()
        
        if 'time_limit' in reason:
            sell_sources['time_limit'] += 1
        elif 'emergency' in reason:
            sell_sources['emergency'] += 1
        elif 'random_exploration' in reason or 'exploration sell' in reason:
            sell_sources['random_exploration'] += 1
        elif 'exploitation' in reason or 'ai_exit' in reason:
            sell_sources['exploitation'] += 1
        else:
            sell_sources['unknown'] += 1
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CALCULATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    total = len(trades)
    total_winning = len(winning_pnls_usdt)
    total_losing = len(losing_pnls_usdt)
    
    # Small value to prevent division by zero
    EPSILON = 0.0001
    
    # Hold stats
    avg_hold = sum(durations) / len(durations) if durations else 0
    min_hold = min(durations) if durations else 0
    max_hold = max(durations) if durations else 0
    
    # PnL stats
    avg_net_pnl_usdt = sum(net_pnls_usdt) / total if total > 0 else 0
    avg_net_pnl_pct = sum(net_pnls_pct) / total if total > 0 else 0
    avg_theoretical_pnl_pct = sum(theoretical_pnls_pct) / total if total > 0 else 0
    
    total_net_pnl_usdt = sum(net_pnls_usdt)
    total_net_pnl_pct = sum(net_pnls_pct)
    total_theoretical_pnl_pct = sum(theoretical_pnls_pct)
    
    # Gap between theoretical and net (shows fee/slippage impact)
    pnl_gap_pct = avg_theoretical_pnl_pct - avg_net_pnl_pct
    
    # Fee ratio: total_fees / total_notional * 100
    # Definition: What percentage of traded volume went to fees
    fee_ratio_pct = (total_fees / max(total_notional, EPSILON)) * 100
    
    # Sell source percentages
    sell_source_pct = {k: (v / max(total, 1) * 100) for k, v in sell_sources.items()}
    
    # Performance metrics
    win_rate = (total_winning / max(total, 1)) * 100
    avg_win_usdt = sum(winning_pnls_usdt) / max(total_winning, 1)
    avg_loss_usdt = sum(losing_pnls_usdt) / max(total_losing, 1)  # Will be negative
    avg_win_pct = sum(winning_pnls_pct) / max(total_winning, 1)
    avg_loss_pct = sum(losing_pnls_pct) / max(total_losing, 1)  # Will be negative
    
    # Profit factor: gross_profit / gross_loss
    gross_profit = sum(p for p in net_pnls_usdt if p > 0)
    gross_loss = abs(sum(p for p in net_pnls_usdt if p < 0))
    profit_factor = gross_profit / max(gross_loss, EPSILON)
    
    # RL-specific metrics
    exploration_sells = sell_sources['random_exploration']
    exploitation_sells = sell_sources['exploitation']
    total_ai_sells = exploration_sells + exploitation_sells
    
    exploration_ratio = (exploration_sells / max(total_ai_sells, 1)) * 100
    exploitation_ratio = (exploitation_sells / max(total_ai_sells, 1)) * 100
    
    avg_duration_winning = sum(durations_winning) / max(len(durations_winning), 1)
    avg_duration_losing = sum(durations_losing) / max(len(durations_losing), 1)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EDGE ANALYSIS & NEW METRICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # 1. Edge After Costs = Theoretical PnL - Fees - Slippage (as %)
    total_costs_pct = fee_ratio_pct + (total_slippage / max(total_notional, EPSILON) * 100)
    edge_after_costs_pct = avg_theoretical_pnl_pct - total_costs_pct / max(total, 1) if total > 0 else 0
    
    # Alternative: Edge After Costs = Net PnL - Theoretical PnL (shows cost impact)
    cost_impact_pct = avg_net_pnl_pct - avg_theoretical_pnl_pct
    
    # 2. Edge Efficiency = Net PnL / Theoretical PnL (how much edge survives costs)
    edge_efficiency_pct = (avg_net_pnl_pct / max(abs(avg_theoretical_pnl_pct), EPSILON)) * 100 if avg_theoretical_pnl_pct != 0 else 0
    
    # 3. Trade Quality Metrics (MFE/MAE)
    avg_mfe = sum(mfe_values) / max(len(mfe_values), 1)
    avg_mae = sum(mae_values) / max(len(mae_values), 1)
    mfe_mae_ratio = avg_mfe / max(abs(avg_mae), EPSILON) if avg_mae != 0 else 0
    
    # 4. Liquidity Monitoring
    avg_spread = sum(spread_values) / max(len(spread_values), 1)
    avg_slippage_per_trade = sum(slippage_per_trade) / max(len(slippage_per_trade), 1)
    
    # 5. Noise Trading Detection
    avg_price_move = sum(price_moves) / max(len(price_moves), 1)
    avg_trading_cost = (total_fees + total_slippage) / max(total, 1) if total > 0 else 0
    avg_trading_cost_pct = total_costs_pct / max(total, 1) if total > 0 else 0
    is_noise_trading = avg_price_move < avg_trading_cost_pct and total >= 5
    
    # 6. Trade Frequency Analysis
    trades_per_hour = 0
    avg_time_between_trades = 0
    is_overtrading = False
    
    if len(trade_timestamps) >= 2:
        # Sort timestamps and calculate time differences
        try:
            sorted_ts = sorted([ts if isinstance(ts, str) else ts.isoformat() for ts in trade_timestamps])
            if sorted_ts:
                first_trade = datetime.fromisoformat(sorted_ts[0].replace('Z', '+00:00'))
                last_trade = datetime.fromisoformat(sorted_ts[-1].replace('Z', '+00:00'))
                time_span_hours = max((last_trade - first_trade).total_seconds() / 3600, 0.1)
                trades_per_hour = total / time_span_hours
                avg_time_between_trades = (time_span_hours * 3600) / max(total - 1, 1)  # in seconds
                
                # Overtrading: > 3 trades/hour AND negative edge
                is_overtrading = trades_per_hour > 3 and avg_net_pnl_pct < 0
        except:
            pass
    
    # 7. Minimum Expected Move Threshold
    min_profitable_move = avg_trading_cost_pct * 1.5  # Need 1.5x costs to be profitable
    trades_above_threshold = sum(1 for m in price_moves if m > min_profitable_move) if price_moves else 0
    profitable_move_ratio = (trades_above_threshold / max(total, 1)) * 100

    # ═══════════════════════════════════════════════════════════════════════════
    # HEALTH STATUS CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════
    status = "healthy"
    status_reasons = []
    
    # Critical checks
    if avg_net_pnl_pct < -0.5:
        status = "critical"
        status_reasons.append("Net PnL strongly negative")
    
    if profit_factor < 0.5 and total >= 5:
        status = "critical"
        status_reasons.append(f"Profit factor very low ({profit_factor:.2f})")
    
    if sell_source_pct.get('random_exploration', 0) > 70:
        status = "critical"
        status_reasons.append("Too many random exploration sells (>70%)")
    
    if fee_ratio_pct > 1.0:
        status = "critical"
        status_reasons.append(f"Fee ratio extremely high ({fee_ratio_pct:.2f}%)")
    
    if avg_hold < 60 and total >= 5:
        status = "critical"
        status_reasons.append(f"Avg hold too short ({avg_hold:.0f}s) - possible overtrading")
    
    # Warning checks (only if not already critical)
    if status != "critical":
        if avg_net_pnl_pct < 0:
            status = "warning"
            status_reasons.append("Net PnL negative")
        
        if profit_factor < 1.0 and total >= 5:
            if status != "warning":
                status = "warning"
            status_reasons.append(f"Profit factor below 1.0 ({profit_factor:.2f})")
        
        if sell_source_pct.get('random_exploration', 0) > 50:
            if status != "warning":
                status = "warning"
            status_reasons.append("High random exploration sells (>50%)")
        
        if pnl_gap_pct > 0.3:
            if status != "warning":
                status = "warning"
            status_reasons.append(f"Large gap between theoretical and net PnL ({pnl_gap_pct:.2f}%)")
        
        if fee_ratio_pct > 0.5:
            if status != "warning":
                status = "warning"
            status_reasons.append(f"Fee ratio elevated ({fee_ratio_pct:.2f}%)")
        
        if avg_hold < 90 and total >= 5:
            if status != "warning":
                status = "warning"
            status_reasons.append(f"Avg hold near minimum ({avg_hold:.0f}s)")
    
    # Healthy status reasons
    if status == "healthy" and total >= 3:
        if win_rate >= 50:
            status_reasons.append(f"Win rate healthy ({win_rate:.1f}%)")
        if profit_factor >= 1.0:
            status_reasons.append(f"Profit factor positive ({profit_factor:.2f})")
        if exploitation_ratio > 50:
            status_reasons.append(f"Exploitation dominant ({exploitation_ratio:.0f}%)")
    
    # New warning checks for edge analysis
    if is_noise_trading and status != "critical":
        if status != "warning":
            status = "warning"
        status_reasons.append("⚠️ Trades smaller than costs - possible noise trading")
    
    if is_overtrading:
        if status != "critical":
            status = "warning"
        status_reasons.append(f"⚠️ High trade frequency ({trades_per_hour:.1f}/h) with negative edge - overtrading")
    
    if avg_slippage_per_trade > 0.05 and total >= 5:  # > $0.05 slippage per trade
        if status != "critical":
            status = "warning"
        status_reasons.append(f"⚠️ High average slippage (${avg_slippage_per_trade:.4f}/trade)")
    
    if edge_efficiency_pct < 30 and total >= 10 and avg_theoretical_pnl_pct > 0:
        if status != "critical":
            status = "warning"
        status_reasons.append(f"⚠️ Low edge efficiency ({edge_efficiency_pct:.0f}%) - costs destroying profits")
    
    if not status_reasons:
        status_reasons.append("Insufficient data for assessment")
    
    # Status color mapping
    status_color = {"healthy": "green", "warning": "yellow", "critical": "red"}.get(status, "gray")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def fmt_duration(secs):
        """Format seconds as Xm Ys"""
        return f"{int(secs//60)}m {int(secs%60)}s"
    
    return {
        "period_hours": hours,
        "total_closed_trades": total,
        
        # 1. HOLD STATS
        "hold_stats": {
            "avg_hold_seconds": round(avg_hold, 1),
            "min_hold_seconds": round(min_hold, 1),
            "max_hold_seconds": round(max_hold, 1),
            "avg_hold_formatted": fmt_duration(avg_hold),
            "min_hold_formatted": fmt_duration(min_hold),
            "max_hold_formatted": fmt_duration(max_hold)
        },
        
        # 2. NET PNL STATS
        "pnl_stats": {
            "avg_net_pnl_usdt": round(avg_net_pnl_usdt, 4),
            "avg_net_pnl_pct": round(avg_net_pnl_pct, 3),
            "avg_theoretical_pnl_pct": round(avg_theoretical_pnl_pct, 3),
            "total_net_pnl_usdt": round(total_net_pnl_usdt, 4),
            "total_net_pnl_pct": round(total_net_pnl_pct, 3),
            "total_theoretical_pnl_pct": round(total_theoretical_pnl_pct, 3),
            "pnl_gap_pct": round(pnl_gap_pct, 3)
        },
        
        # 3. FEES
        "fee_stats": {
            "total_fees_paid": round(total_fees, 4),
            "total_slippage": round(total_slippage, 4),
            "total_costs": round(total_fees + total_slippage, 4),
            "fee_ratio_pct": round(fee_ratio_pct, 3)
        },
        
        # 4. SELL SOURCE BREAKDOWN
        "sell_sources": {
            "counts": sell_sources,
            "percentages": {k: round(v, 1) for k, v in sell_source_pct.items()}
        },
        
        # 5. TRADE COUNTS
        "trade_counts": {
            "total": total,
            "winning": total_winning,
            "losing": total_losing
        },
        
        # 6. CORE PERFORMANCE METRICS
        "performance": {
            "win_rate_pct": round(win_rate, 1),
            "avg_win_usdt": round(avg_win_usdt, 4),
            "avg_loss_usdt": round(avg_loss_usdt, 4),
            "avg_win_pct": round(avg_win_pct, 3),
            "avg_loss_pct": round(avg_loss_pct, 3),
            "profit_factor": round(profit_factor, 2),
            "gross_profit": round(gross_profit, 4),
            "gross_loss": round(gross_loss, 4)
        },
        
        # 7. RL-SPECIFIC METRICS
        "rl_metrics": {
            "exploration_sell_ratio_pct": round(exploration_ratio, 1),
            "exploitation_sell_ratio_pct": round(exploitation_ratio, 1),
            "avg_duration_winning": round(avg_duration_winning, 1),
            "avg_duration_losing": round(avg_duration_losing, 1),
            "avg_duration_winning_formatted": fmt_duration(avg_duration_winning),
            "avg_duration_losing_formatted": fmt_duration(avg_duration_losing)
        },
        
        # 8. EDGE ANALYSIS (NEW)
        "edge_analysis": {
            "edge_after_costs_pct": round(edge_after_costs_pct, 3),
            "cost_impact_pct": round(cost_impact_pct, 3),
            "edge_efficiency_pct": round(edge_efficiency_pct, 1),
            "is_profitable_edge": edge_after_costs_pct > 0 and total >= 5
        },
        
        # 9. TRADE QUALITY (NEW)
        "trade_quality": {
            "avg_mfe_pct": round(avg_mfe, 3),
            "avg_mae_pct": round(avg_mae, 3),
            "mfe_mae_ratio": round(mfe_mae_ratio, 2),
            "exits_too_early": avg_mfe > abs(avg_mae) * 1.5 and avg_net_pnl_pct < avg_mfe * 0.5 if total >= 5 else False
        },
        
        # 10. NOISE DETECTION (NEW)
        "noise_detection": {
            "avg_price_move_pct": round(avg_price_move, 3),
            "avg_trading_cost_pct": round(avg_trading_cost_pct, 3),
            "is_noise_trading": is_noise_trading,
            "min_profitable_move_pct": round(min_profitable_move, 3),
            "profitable_move_ratio_pct": round(profitable_move_ratio, 1)
        },
        
        # 11. TRADE FREQUENCY (NEW)
        "frequency_analysis": {
            "trades_per_hour": round(trades_per_hour, 2),
            "avg_time_between_trades_sec": round(avg_time_between_trades, 0),
            "avg_time_between_trades_formatted": fmt_duration(avg_time_between_trades),
            "is_overtrading": is_overtrading
        },
        
        # 12. LIQUIDITY MONITORING (NEW)
        "liquidity": {
            "avg_spread_pct": round(avg_spread, 4),
            "avg_slippage_per_trade": round(avg_slippage_per_trade, 4),
            "high_slippage_warning": avg_slippage_per_trade > 0.05
        },
        
        # 13. HEALTH STATUS
        "health": {
            "status": status,
            "status_color": status_color,
            "reasons": status_reasons
        }
    }

@app.post("/api/migrate/remove-tp")
async def migrate_remove_tp(current_user: dict = Depends(get_current_user)):
    """
    Migriere bestehende Positionen: Entferne festes TP, setze nur Notfall-SL
    """
    user_id = current_user['user_id']
    
    try:
        live_account = await db.get_live_account(user_id)
        if not live_account or not live_account.open_positions:
            return {"message": "Keine offenen Positionen", "updated": 0}
        
        updated = 0
        for pos in live_account.open_positions:
            # Setze Notfall-SL auf -10% vom Entry
            pos.stop_loss = pos.entry_price * 0.90
            # Setze TP auf sehr hohen Wert (wird ignoriert)
            pos.take_profit = pos.entry_price * 999
            updated += 1
        
        await db.update_live_account(live_account)
        
        await db.log(user_id, "INFO", f"[MIGRATION] {updated} Positionen auf KI-Modus umgestellt (kein festes TP)")
        
        return {
            "message": f"{updated} Positionen migriert",
            "updated": updated,
            "info": "TP entfernt, nur Notfall-SL bei -10%"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
