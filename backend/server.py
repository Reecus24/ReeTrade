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
daily_summary_task: asyncio.Task = None
limiter = Limiter(key_func=get_remote_address)
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global worker, worker_task, telegram_bot, telegram_polling_task, daily_summary_task
    
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
        daily_summary_task = asyncio.create_task(daily_summary_scheduler())
        logger.info("Telegram bot started with daily summary scheduler")
    
    yield
    
    # Shutdown
    logger.info("Shutting down")
    if worker:
        await worker.stop()
    if worker_task:
        worker_task.cancel()
    if telegram_polling_task:
        telegram_polling_task.cancel()
    if daily_summary_task:
        daily_summary_task.cancel()
    db.close()


async def telegram_polling_loop():
    """Polling loop für Telegram Befehle
    
    WICHTIG: Verwendet Distributed Lock um 409 Conflict zu vermeiden!
    Nur die Leader-Instanz führt Polling aus.
    """
    global telegram_bot
    
    if not telegram_bot:
        return
    
    # Import hier um zirkuläre Imports zu vermeiden
    from distributed_lock import get_telegram_lock
    
    # Hole Lock
    tg_lock = get_telegram_lock(db)
    await tg_lock.initialize()
    
    offset = 0
    default_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    startup_message_sent = False
    
    while True:
        try:
            # ============ LEADER ELECTION ============
            is_leader = await tg_lock.try_acquire()
            
            if not is_leader:
                # Nicht Leader - warte und versuche erneut
                logger.debug("[Telegram] Not leader, waiting...")
                await asyncio.sleep(10)
                continue
            
            # Wir sind Leader - starte Heartbeat wenn noch nicht aktiv
            if tg_lock._heartbeat_task is None:
                await tg_lock.start_heartbeat_loop(interval=10)
            
            # Sende Startup-Nachricht (nur einmal)
            if not startup_message_sent and default_chat_id:
                await telegram_bot.send_message(
                    int(default_chat_id),
                    "🤖 <b>ReeTrade Bot gestartet!</b>\n\nTippe /help für alle Befehle."
                )
                startup_message_sent = True
                logger.info("[Telegram] ✅ Leader - starting polling")
            
            # ============ POLLING ============
            updates = await telegram_bot.get_updates(offset)
            
            for update in updates:
                offset = update['update_id'] + 1
                
                if 'message' in update and 'text' in update['message']:
                    chat_id = update['message']['chat']['id']
                    text = update['message']['text'].strip()
                    
                    # Handle /link command - generate code OR link with existing code
                    if text.lower().startswith('/link'):
                        parts = text.split()
                        if len(parts) >= 2:
                            # User hat einen Code eingegeben (alter Flow - von Website generiert)
                            code = parts[1].upper()
                            response = await handle_telegram_link(chat_id, code)
                            await telegram_bot.send_message(chat_id, response)
                            continue
                        else:
                            # Nur "/link" ohne Code - generiere neuen Code (neuer Flow)
                            response = await telegram_bot.handle_command(chat_id, "/link", None)
                            await telegram_bot.send_message(chat_id, response)
                            continue
                    
                    # Finde user_id basierend auf chat_id
                    user = await db.users.find_one({"telegram_chat_id": str(chat_id)})
                    user_id = str(user['_id']) if user else None
                    
                    # Wenn kein User gefunden, versuche Fallback
                    if not user_id:
                        # Fallback 1: Default chat_id
                        if str(chat_id) == default_chat_id:
                            first_user = await db.users.find_one({"live_mode_confirmed": True})
                            user_id = str(first_user['_id']) if first_user else None
                            if user_id:
                                logger.info(f"[TELEGRAM] Fallback: Using default user for chat {chat_id}")
                        
                        # Fallback 2: Wenn nur EIN User existiert, nutze diesen
                        if not user_id:
                            user_count = await db.users.count_documents({})
                            if user_count == 1:
                                single_user = await db.users.find_one({})
                                user_id = str(single_user['_id']) if single_user else None
                                if user_id:
                                    logger.info(f"[TELEGRAM] Fallback: Single user mode for chat {chat_id}")
                                    # Auto-Link this chat_id to the single user
                                    await db.users.update_one(
                                        {"_id": single_user['_id']},
                                        {"$set": {"telegram_chat_id": str(chat_id)}}
                                    )
                                    logger.info(f"[TELEGRAM] Auto-linked chat {chat_id} to user {user_id[:8]}...")
                        
                        if not user_id:
                            logger.warning(f"[TELEGRAM] No user found for chat_id {chat_id}. Use /link CODE to connect.")
                    
                    if text.startswith('/'):
                        response = await telegram_bot.handle_command(chat_id, text.split()[0], user_id)
                        await telegram_bot.send_message(chat_id, response)
            
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Cleanup: Release lock und stoppe heartbeat
            logger.info("[Telegram] Polling cancelled, releasing lock...")
            await tg_lock.stop_heartbeat_loop()
            await tg_lock.release()
            break
        except Exception as e:
            # Bei Fehler: Kurz warten, aber Lock verlieren wir nicht automatisch
            logger.error(f"Telegram polling error: {e}")
            
            # Bei 409 Conflict: Wir sind nicht mehr allein, Lock abgeben
            if "409" in str(e) or "Conflict" in str(e):
                logger.warning("[Telegram] 409 Conflict detected - releasing lock")
                await tg_lock.release()
            
            await asyncio.sleep(5)


async def handle_telegram_link(chat_id: int, code: str) -> str:
    """Handle /link command to connect Telegram account"""
    
    code_upper = code.upper().strip()
    logger.info(f"[TELEGRAM LINK] Attempting to link with code: '{code_upper}' for chat_id: {chat_id}")
    
    # Look up code in database
    link_doc = await db.db.telegram_link_codes.find_one({'code': code_upper})
    
    if not link_doc:
        # Debug: List all codes in DB
        all_codes = await db.db.telegram_link_codes.find({}).to_list(100)
        logger.warning(f"[TELEGRAM LINK] Code '{code_upper}' not found. Existing codes in DB: {[c.get('code') for c in all_codes]}")
        return "❌ Ungültiger oder abgelaufener Code.\n\nBitte generiere einen neuen Code in der Web-App."
    
    logger.info(f"[TELEGRAM LINK] Code found! User ID: {link_doc.get('user_id')}")
    
    # Check expiration (handle both timezone-aware and naive datetimes)
    expires_at = link_doc.get('expires_at')
    if expires_at:
        now = datetime.now(timezone.utc)
        # Convert naive datetime to aware if needed
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if now > expires_at:
            # Delete expired code
            await db.db.telegram_link_codes.delete_one({'code': code_upper})
            logger.warning(f"[TELEGRAM LINK] Code expired")
            return "❌ Code ist abgelaufen.\n\nBitte generiere einen neuen Code in der Web-App."
    
    user_id = link_doc['user_id']
    
    # Save chat_id to user
    from bson import ObjectId
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"telegram_chat_id": str(chat_id)}}
    )
    logger.info(f"[TELEGRAM LINK] User updated: matched={result.matched_count}, modified={result.modified_count}")
    
    # Delete used code
    await db.db.telegram_link_codes.delete_one({'code': code_upper})
    
    # Log
    await db.log(user_id, "INFO", f"Telegram-Konto verknüpft (Chat ID: {str(chat_id)[:5]}...)")
    
    return """✅ <b>Telegram erfolgreich verknüpft!</b>

Du erhältst jetzt Benachrichtigungen für:
• 🟢 Trade geöffnet
• 🔴 Trade geschlossen
• 🧠 KI Smart Exit Entscheidungen
• 📊 Tägliche Zusammenfassung (21:00 Uhr)

<b>Befehle:</b>
/status - Offene Positionen
/balance - Wallet-Stand
/profit - Heutiger Profit
/ki - KI Status
/help - Alle Befehle"""


async def daily_summary_scheduler():
    """Scheduler für tägliche Zusammenfassung um 21:00 Uhr"""
    global telegram_bot
    
    if not telegram_bot:
        return
    
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not chat_id:
        return
    
    logger.info("Daily summary scheduler started - will send at 21:00")
    
    while True:
        try:
            now = datetime.now()
            
            # Berechne Zeit bis 21:00 Uhr
            target_hour = 21
            target_minute = 0
            
            if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
                # Heute schon vorbei, warte bis morgen
                tomorrow = now + timedelta(days=1)
                target_time = tomorrow.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            else:
                target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            
            wait_seconds = (target_time - now).total_seconds()
            logger.info(f"Daily summary: waiting {wait_seconds/3600:.1f} hours until {target_time}")
            
            await asyncio.sleep(wait_seconds)
            
            # Zeit für die Zusammenfassung!
            logger.info("Sending daily summary...")
            await send_daily_summary_to_all(int(chat_id))
            
            # Warte mindestens 1 Minute bevor wir wieder prüfen
            await asyncio.sleep(60)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Daily summary error: {e}")
            await asyncio.sleep(300)  # 5 Minuten warten bei Fehler


async def send_daily_summary_to_all(chat_id: int):
    """Sende tägliche Zusammenfassung"""
    global telegram_bot
    
    if not telegram_bot:
        return
    
    try:
        # Finde alle User mit Live-Mode
        users = await db.users.find({"live_mode_confirmed": True}).to_list(100)
        
        if not users:
            # Fallback: Erster User
            first_user = await db.users.find_one({})
            users = [first_user] if first_user else []
        
        for user in users:
            user_id = str(user['_id'])
            
            # Hole Trades von heute
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            trades = await db.get_trades(user_id, limit=1000)
            
            today_trades = [t for t in trades if t.get('exit_time') and t['exit_time'] >= today_start]
            
            if not today_trades:
                # Keine Trades heute
                summary = {
                    'trade_count': 0,
                    'winners': 0,
                    'losers': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'total_pnl_pct': 0,
                    'best_trade': 'Keine',
                    'worst_trade': 'Keine',
                    'balance': 0
                }
            else:
                total_pnl = sum(t.get('pnl', 0) for t in today_trades)
                winners = [t for t in today_trades if t.get('pnl', 0) > 0]
                losers = [t for t in today_trades if t.get('pnl', 0) <= 0]
                
                best = max(today_trades, key=lambda x: x.get('pnl', 0))
                worst = min(today_trades, key=lambda x: x.get('pnl', 0))
                
                # Hole Balance
                account = await db.get_live_account(user_id)
                balance = account.balance if account else 0
                
                summary = {
                    'trade_count': len(today_trades),
                    'winners': len(winners),
                    'losers': len(losers),
                    'win_rate': (len(winners) / len(today_trades) * 100) if today_trades else 0,
                    'total_pnl': total_pnl,
                    'total_pnl_pct': (total_pnl / balance * 100) if balance > 0 else 0,
                    'best_trade': f"{best.get('symbol', '?')} +${best.get('pnl', 0):.2f}",
                    'worst_trade': f"{worst.get('symbol', '?')} ${worst.get('pnl', 0):.2f}",
                    'balance': balance
                }
            
            await telegram_bot.send_daily_summary(chat_id, summary)
            logger.info(f"Daily summary sent for user {user_id}")
            
    except Exception as e:
        logger.error(f"Error sending daily summary: {e}")

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
        
        # Serialize open_positions from local DB (source of truth for frontend)
        open_positions_serialized = []
        if live_account and live_account.open_positions:
            for pos in live_account.open_positions:
                open_positions_serialized.append({
                    'id': str(pos.id) if hasattr(pos, 'id') else None,
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'qty': pos.qty,
                    'entry_price': pos.entry_price,
                    'current_price': getattr(pos, 'current_price', None),
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
            # Open positions from local DB (source of truth)
            'open_positions': open_positions_serialized,
            'open_positions_count': local_positions_count,
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


@app.post("/api/telegram/summary")
async def send_summary_now(current_user: dict = Depends(get_current_user)):
    """Tages-Zusammenfassung jetzt senden"""
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not chat_id:
        raise HTTPException(status_code=400, detail="Telegram nicht konfiguriert")
    
    await send_daily_summary_to_all(int(chat_id))
    return {"message": "Zusammenfassung gesendet!"}


# ============ TELEGRAM ACCOUNT LINKING ============

@app.get("/api/telegram/link-code")
async def get_telegram_link_code(current_user: dict = Depends(get_current_user)):
    """Generate a temporary code for linking Telegram account"""
    import secrets
    
    user_id = current_user['user_id']
    
    # Generate a 6-character alphanumeric code
    code = secrets.token_hex(3).upper()  # e.g., "A1B2C3"
    
    # Store in database with expiration (10 minutes)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    logger.info(f"[TELEGRAM LINK] Generating code '{code}' for user {user_id}")
    
    result = await db.db.telegram_link_codes.update_one(
        {'user_id': user_id},
        {'$set': {
            'code': code,
            'user_id': user_id,
            'created_at': datetime.now(timezone.utc),
            'expires_at': expires_at
        }},
        upsert=True
    )
    
    logger.info(f"[TELEGRAM LINK] Code saved: matched={result.matched_count}, modified={result.modified_count}, upserted={result.upserted_id}")
    
    # Verify it was saved
    saved = await db.db.telegram_link_codes.find_one({'code': code})
    logger.info(f"[TELEGRAM LINK] Verification - code in DB: {saved is not None}")
    
    # Clean up old expired codes
    await db.db.telegram_link_codes.delete_many({
        'expires_at': {'$lt': datetime.now(timezone.utc)}
    })
    
    return {
        "code": code,
        "expires_in_minutes": 10,
        "instructions": f"Sende /link {code} an den ReeTrade Bot in Telegram"
    }


@app.get("/api/telegram/link-status")
async def get_telegram_link_status(current_user: dict = Depends(get_current_user)):
    """Check if Telegram is linked for this user"""
    user_id = current_user['user_id']
    
    # Check if user has telegram_chat_id
    user = await db.users.find_one({"_id": __import__('bson').ObjectId(user_id)})
    
    if user and user.get('telegram_chat_id'):
        return {
            "linked": True,
            "chat_id": user['telegram_chat_id'][:5] + "..." if len(user['telegram_chat_id']) > 5 else user['telegram_chat_id']
        }
    
    return {"linked": False, "chat_id": None}


@app.post("/api/telegram/unlink")
async def unlink_telegram(current_user: dict = Depends(get_current_user)):
    """Unlink Telegram account"""
    user_id = current_user['user_id']
    
    await db.users.update_one(
        {"_id": __import__('bson').ObjectId(user_id)},
        {"$unset": {"telegram_chat_id": ""}}
    )
    
    await db.log(user_id, "INFO", "Telegram-Konto getrennt")
    
    return {"message": "Telegram-Konto getrennt", "linked": False}


@app.post("/api/telegram/link-with-code")
async def link_telegram_with_code(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Link Telegram account using code from Telegram Bot"""
    user_id = current_user['user_id']
    code = data.get('code', '').upper().strip()
    
    if not code:
        raise HTTPException(status_code=400, detail="Code ist erforderlich")
    
    # Suche Code in DB (generiert von Telegram Bot)
    link_doc = await db.db.telegram_link_codes.find_one({'code': code})
    
    if not link_doc:
        raise HTTPException(status_code=400, detail="Ungültiger Code. Bitte /link in Telegram eingeben für neuen Code.")
    
    # Prüfe ob abgelaufen
    expires_at = link_doc.get('expires_at')
    if expires_at:
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            await db.db.telegram_link_codes.delete_one({'code': code})
            raise HTTPException(status_code=400, detail="Code ist abgelaufen. Bitte /link in Telegram für neuen Code.")
    
    chat_id = link_doc.get('chat_id')
    if not chat_id:
        raise HTTPException(status_code=400, detail="Ungültiger Code (keine Chat-ID)")
    
    # Verknüpfe User mit Telegram Chat
    await db.users.update_one(
        {"_id": __import__('bson').ObjectId(user_id)},
        {"$set": {"telegram_chat_id": str(chat_id)}}
    )
    
    # Lösche verwendeten Code
    await db.db.telegram_link_codes.delete_one({'code': code})
    
    await db.log(user_id, "INFO", f"Telegram verknüpft (Chat: {chat_id})")
    
    # Sende Bestätigung an Telegram
    if telegram_bot:
        await telegram_bot.send_message(
            int(chat_id),
            "✅ <b>Erfolgreich verknüpft!</b>\n\nDein Telegram ist jetzt mit ReeTrade verbunden.\n\nTippe /help für alle Befehle."
        )
    
    return {"message": "Telegram erfolgreich verknüpft!", "linked": True}



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
    
    return {
        "model_type": status['model_type'],
        "total_trades": status['total_trades'],
        "winning_trades": status['winning_trades'],
        "win_rate": status['win_rate'],
        "win_rate_pct": f"{status['win_rate']*100:.1f}%",
        "exploration_pct": status['exploration_pct'],
        "is_learning": status['is_learning'],
        "memory_size": status['memory_size'],
        "active_episodes": status['active_episodes'],
        "message": f"RL-KI: {status['total_trades']} Trades, {status['win_rate']*100:.1f}% Win-Rate, {status['exploration_pct']:.0f}% Exploration"
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
    
    # Fetch all closed trades in period
    trades = await db.db.trades.find({
        "user_id": user_id,
        "ts": {"$gte": cutoff},
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
        
        # 8. HEALTH STATUS
        "health": {
            "status": status,
            "status_color": status_color,
            "reasons": status_reasons
        }
    }


@app.get("/api/rl/buy-cooldown")
async def get_buy_cooldown_status(current_user: dict = Depends(get_current_user)):
    """
    Get Global Buy Cooldown Status
    
    Returns cooldown status for the UI display
    """
    user_id = current_user['user_id']
    
    try:
        status = worker.get_buy_cooldown_status(user_id)
        return status
    except Exception as e:
        return {
            "cooldown_active": False,
            "remaining_seconds": 0,
            "remaining_formatted": "Ready",
            "error": str(e)
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
