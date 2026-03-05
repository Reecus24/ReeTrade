import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import os
from db_operations import Database
from mexc_client import MexcClient
from mexc_futures_client import MexcFuturesClient
from strategy import TradingStrategy
from risk_manager import RiskManager
from regime_detector import RegimeDetector
from order_sizer import order_sizer
from models import Position, Trade, UserSettings, PaperAccount
from ai_engine_v2 import (
    AITradingEngineV2, TradingMode, MarketConditions, AccountState, MarketRegime,
    RISK_PROFILES_V2, ai_engine_v2
)
from ml_data_collector import get_ml_collector
from ki_learning_engine import get_ki_engine
from smart_exit_engine import SmartExitEngine, check_position_exit, PositionContext
from telegram_bot import get_telegram_bot

logger = logging.getLogger(__name__)

class MultiUserTradingWorker:
    """Background worker for multi-user LIVE automated trading with AI support"""
    
    def __init__(self, db: Database):
        self.db = db
        self.running = False
        self.user_initial_equity: Dict[str, float] = {}
        self.user_last_trade_time: Dict[str, datetime] = {}
        self.regime_detector = RegimeDetector()
        self.exchange_info_loaded = False
        self.ai_engine = ai_engine_v2  # AI Trading Engine V2
        self.ml_collector = get_ml_collector(db)  # ML Data Collector für Training
        self.ki_engine = get_ki_engine(db)  # KI Learning Engine
        self.smart_exit = SmartExitEngine(db)  # Smart Exit Engine für intelligente Exits
        
        # Telegram Bot
        tg_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram = get_telegram_bot(tg_token, db) if tg_token else None
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        # Coin rotation: track which batch of coins to scan next
        self.user_coin_batch: Dict[str, int] = {}  # {user_id: batch_index}
        self.user_all_coins: Dict[str, list] = {}  # {user_id: [all coins]}
        self.COINS_PER_BATCH = 20
        self.MAX_BATCHES = 5  # 5 batches x 20 = 100 coins before refresh
        
        # Dedupe für Telegram-Benachrichtigungen
        self._sent_notifications: Dict[str, float] = {}  # {key: timestamp}
        self._notification_cooldown = 60  # Sekunden bis gleiche Nachricht erneut gesendet wird
    
    async def notify_telegram(self, notification_type: str, data: Dict, user_id: str = None):
        """Sende Telegram-Benachrichtigung (mit Dedupe) an User-spezifische Chat ID"""
        if not self.telegram:
            return
        
        try:
            # Hole User-spezifische Chat ID aus DB
            chat_id = None
            if user_id:
                user = await self.db.users.find_one({"_id": __import__('bson').ObjectId(user_id)})
                if user and user.get('telegram_chat_id'):
                    chat_id = int(user['telegram_chat_id'])
            
            # Fallback zu Default Chat ID
            if not chat_id and self.telegram_chat_id:
                chat_id = int(self.telegram_chat_id)
            
            if not chat_id:
                return
            
            # Dedupe-Key erstellen
            symbol = data.get('symbol', '')
            dedupe_key = f"{notification_type}:{symbol}:{chat_id}"
            
            # Prüfen ob kürzlich gesendet
            now = datetime.now(timezone.utc).timestamp()
            last_sent = self._sent_notifications.get(dedupe_key, 0)
            
            if now - last_sent < self._notification_cooldown:
                logger.debug(f"Telegram notification dedupe: {dedupe_key} (sent {now - last_sent:.0f}s ago)")
                return
            
            # Markieren als gesendet
            self._sent_notifications[dedupe_key] = now
            
            # Alte Einträge aufräumen (älter als 5 Minuten)
            cutoff = now - 300
            self._sent_notifications = {k: v for k, v in self._sent_notifications.items() if v > cutoff}
            
            if notification_type == 'trade_opened':
                await self.telegram.notify_trade_opened(chat_id, data)
            elif notification_type == 'trade_closed':
                await self.telegram.notify_trade_closed(chat_id, data)
            elif notification_type == 'stop_loss':
                await self.telegram.notify_stop_loss(chat_id, data)
            elif notification_type == 'take_profit':
                await self.telegram.notify_take_profit(chat_id, data)
            elif notification_type == 'smart_exit':
                await self.telegram.notify_smart_exit(chat_id, data)
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
    
    def _calculate_rsi(self, closes: list, period: int = 14) -> float:
        """Berechne RSI aus Schlusskursen"""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_ema(self, closes: list, period: int) -> float:
        """Berechne EMA aus Schlusskursen"""
        if len(closes) < period:
            return closes[-1] if closes else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period
        
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def calculate_used_budget(self, account: PaperAccount) -> float:
        """Calculate total notional of all open positions"""
        used = 0.0
        for pos in account.open_positions:
            used += pos.entry_price * pos.qty
        return used
    
    def calculate_live_budget(
        self, 
        settings: UserSettings, 
        used_budget: float,
        usdt_free: float
    ) -> dict:
        """Calculate budget info for LIVE mode with reserve system."""
        available_to_bot = max(0, usdt_free - settings.reserve_usdt)
        budget_remaining = max(0, settings.trading_budget_usdt - used_budget)
        remaining_budget = min(available_to_bot, budget_remaining)
        
        return {
            'usdt_free': usdt_free,
            'reserve_usdt': settings.reserve_usdt,
            'available_to_bot': available_to_bot,
            'trading_budget': settings.trading_budget_usdt,
            'used_budget': used_budget,
            'remaining_budget': remaining_budget,
            'max_order_notional': settings.max_order_notional_usdt
        }
    
    async def heartbeat(self):
        while self.running:
            try:
                active_settings = await self.db.get_all_active_users()
                for settings_doc in active_settings:
                    user_id = settings_doc.get('user_id')
                    await self.db.update_settings(user_id, {
                        'last_heartbeat': datetime.now(timezone.utc)
                    })
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(60)
    
    async def trading_loop(self):
        """Main trading loop - 1 minute intervals for new entries"""
        while self.running:
            try:
                active_settings = await self.db.get_all_active_users()
                
                if not active_settings:
                    await asyncio.sleep(60)
                    continue
                
                logger.info(f"Trading cycle for {len(active_settings)} active user(s)")
                
                for settings_doc in active_settings:
                    user_id = settings_doc.get('user_id')
                    try:
                        await self.process_user(user_id)
                        await asyncio.sleep(2)
                    except Exception as e:
                        await self.db.log(user_id, "ERROR", f"Trading cycle error: {str(e)}")
                        logger.exception(f"Error processing user {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
            
            await asyncio.sleep(60)  # 1 minute
    
    async def exit_check_loop(self):
        """Ultra-fast loop to check exits every 1 second for immediate SL/TP reaction"""
        while self.running:
            try:
                active_settings = await self.db.get_all_active_users()
                
                for settings_doc in active_settings:
                    user_id = settings_doc.get('user_id')
                    try:
                        await self.check_exits_for_user(user_id)
                    except Exception as e:
                        logger.error(f"Exit check error for {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Exit check loop error: {e}")
            
            await asyncio.sleep(1)  # 1 SECOND - immediate reaction to price changes
    
    async def mexc_sync_loop(self):
        """Sync with MEXC trade history every 90 seconds to detect external sells"""
        while self.running:
            try:
                active_settings = await self.db.get_all_active_users()
                
                for settings_doc in active_settings:
                    user_id = settings_doc.get('user_id')
                    try:
                        await self.sync_mexc_trades(user_id)
                    except Exception as e:
                        logger.error(f"MEXC sync error for {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"MEXC sync loop error: {e}")
            
            await asyncio.sleep(90)  # 1.5 minutes
    
    async def sync_mexc_trades(self, user_id: str):
        """Sync open positions with MEXC - detect external sells via balance check"""
        settings = await self.db.get_settings(user_id)
        
        # Only sync if live mode is active and confirmed
        if not (settings.live_running and settings.live_confirmed):
            return
        
        account = await self.db.get_live_account(user_id)
        if not account or not account.open_positions:
            return
        
        # Get MEXC client with user's keys (already decrypted)
        keys = await self.db.get_mexc_keys(user_id)
        if not keys:
            return
        
        mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        
        # Get current MEXC balances
        try:
            account_info = await mexc.get_account()
            balances = {b['asset']: float(b['free']) + float(b['locked']) for b in account_info.get('balances', []) if float(b['free']) + float(b['locked']) > 0}
        except Exception as e:
            logger.warning(f"Failed to get MEXC balances for sync: {e}")
            return
        
        # Check each open position against actual balance
        positions_to_close = []
        
        for position in account.open_positions:
            try:
                # Extract base asset from symbol (e.g., HUSDT -> H)
                base_asset = position.symbol.replace('USDT', '').replace('USDC', '').replace('BTC', '')
                
                # Check if we still own this asset
                actual_balance = balances.get(base_asset, 0)
                
                # If balance is less than 10% of our recorded position, assume sold externally
                if actual_balance < position.qty * 0.1:
                    # Get current price for PnL calculation
                    try:
                        ticker = await mexc.get_ticker_24h(position.symbol)
                        current_price = float(ticker['lastPrice'])
                    except Exception:
                        current_price = position.entry_price  # Fallback
                    
                    positions_to_close.append({
                        'position': position,
                        'exit_price': current_price,
                        'reason': f'MEXC_SYNC: Extern verkauft (Balance: {actual_balance:.4f})'
                    })
                    await self.db.log(user_id, "WARNING", 
                        f"[SYNC] 🔄 {position.symbol} extern verkauft erkannt! Balance: {actual_balance:.4f}, Position war: {position.qty:.4f}")
                
            except Exception as e:
                logger.warning(f"Error checking balance for {position.symbol}: {e}")
        
        # Close detected positions
        for close_info in positions_to_close:
            pos = close_info['position']
            exit_price = close_info['exit_price']
            reason = close_info['reason']
            
            # Calculate PnL
            pnl = (exit_price - pos.entry_price) * pos.qty
            pnl_pct = ((exit_price - pos.entry_price) / pos.entry_price) * 100
            
            # Record the trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=pos.symbol,
                side="SELL",
                qty=pos.qty,
                entry=pos.entry_price,
                exit=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                mode='live',
                reason=reason,
                notional=pos.entry_price * pos.qty
            )
            await self.db.add_trade(trade)
            
            # Remove position
            account.open_positions.remove(pos)
            account.cash += (pos.qty * exit_price)
            
            await self.db.log(user_id, "INFO",
                f"[LIVE] Position {pos.symbol} geschlossen via MEXC Sync | PnL: ${pnl:.2f} ({pnl_pct:.1f}%)")
        
        if positions_to_close:
            await self.db.update_live_account(account)
    
    async def check_exits_for_user(self, user_id: str):
        """Quick exit check for a user - runs every 30 seconds"""
        settings = await self.db.get_settings(user_id)
        
        # Only check live mode
        if not (settings.live_running and settings.live_confirmed):
            return
        
        account = await self.db.get_live_account(user_id)
        if not account or not account.open_positions:
            return
        
        # Get MEXC client
        try:
            mexc = await self.get_user_mexc_client(user_id, settings)
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"[EXIT] MEXC Client Fehler: {str(e)[:50]}")
            return
        
        # Get AI profile for partial profit settings
        trading_mode = TradingMode(settings.trading_mode) if settings.trading_mode else TradingMode.MANUAL
        profile = RISK_PROFILES_V2.get(trading_mode, {}) if trading_mode != TradingMode.MANUAL else {}
        
        # Track positions being sold to prevent duplicates
        if not hasattr(self, '_selling_positions'):
            self._selling_positions = set()
        
        for position in account.open_positions[:]:
            # Skip if already being sold (prevent duplicate sells)
            position_key = f"{user_id}_{position.symbol}_{position.id}"
            if position_key in self._selling_positions:
                continue
            
            try:
                ticker = await mexc.get_ticker_24h(position.symbol)
                current_price = float(ticker['lastPrice'])
                
                # Calculate current PnL for logging
                pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                
                should_exit = False
                exit_reason = ""
                
                # ============ PARTIAL PROFIT LOGIC ============
                partial_enabled = profile.get('partial_profit_enabled', False)
                partial_trigger = profile.get('partial_profit_trigger_pct', 8.0)
                partial_close_pct = profile.get('partial_profit_close_pct', 50.0)
                move_sl_to_entry = profile.get('partial_profit_move_sl_to_entry', True)
                
                if partial_enabled and not position.partial_profit_taken and pnl_pct >= partial_trigger:
                    # Mark as selling to prevent duplicates
                    partial_key = f"{position_key}_partial"
                    if partial_key in self._selling_positions:
                        continue
                    self._selling_positions.add(partial_key)
                    
                    # Time for partial profit!
                    await self.db.log(user_id, "WARNING", 
                        f"[PARTIAL] 🎯 {position.symbol} +{pnl_pct:.1f}% >= {partial_trigger}% → Teilgewinn {partial_close_pct}%!")
                    
                    try:
                        await self.take_partial_profit(
                            user_id, position, current_price, account, settings, mexc,
                            partial_close_pct, move_sl_to_entry
                        )
                        await self.db.update_live_account(account)
                    finally:
                        self._selling_positions.discard(partial_key)
                    continue  # Skip full exit check this iteration
                
                # ============ SMART EXIT ANALYSIS (KI-gesteuert) ============
                # Hole erweiterte Marktdaten für intelligente Analyse
                try:
                    # Hole KI-Lernzustand für diesen User
                    ki_state = await self.ki_engine.get_ki_state(user_id)
                    
                    # Hole zusätzliche Indikatoren für Smart Analysis
                    klines = await mexc.get_klines(position.symbol, "1h", limit=50)
                    closes = [float(k[4]) for k in klines]
                    
                    # Berechne Indikatoren
                    rsi = self._calculate_rsi(closes) if len(closes) >= 14 else 50
                    momentum_1h = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0
                    momentum_4h = ((closes[-1] - closes[-5]) / closes[-5] * 100) if len(closes) >= 5 else 0
                    
                    # EMA Berechnung
                    ema20 = self._calculate_ema(closes, 20) if len(closes) >= 20 else current_price
                    price_vs_ema20 = ((current_price - ema20) / ema20 * 100)
                    
                    # Kerzen-Analyse
                    last_candle = klines[-1] if klines else None
                    candle_type = "neutral"
                    if last_candle:
                        open_p, close_p = float(last_candle[1]), float(last_candle[4])
                        if close_p > open_p * 1.005:
                            candle_type = "bullish"
                        elif close_p < open_p * 0.995:
                            candle_type = "bearish"
                    
                    # Zähle rote/grüne Kerzen
                    red_count = 0
                    for i in range(-1, -6, -1):
                        if i < -len(klines):
                            break
                        k = klines[i]
                        if float(k[4]) < float(k[1]):
                            red_count += 1
                        else:
                            break
                    
                    # Erstelle Marktdaten für Smart Exit
                    market_data = {
                        'price': current_price,
                        'pnl_pct': pnl_pct,
                        'rsi': rsi,
                        'adx': 25,  # Wird später berechnet
                        'momentum_1h': momentum_1h,
                        'momentum_4h': momentum_4h,
                        'price_vs_ema20': price_vs_ema20,
                        'volume_ratio': float(ticker.get('volume', 0)) / max(float(ticker.get('quoteVolume', 1)), 1),
                        'last_candle_type': candle_type,
                        'consecutive_red_candles': red_count
                    }
                    
                    # Position-Daten
                    position_data = {
                        'symbol': position.symbol,
                        'entry_price': position.entry_price,
                        'quantity': position.qty,
                        'entry_time': position.entry_time,
                        'stop_loss': position.stop_loss,
                        'take_profit': position.take_profit
                    }
                    
                    # Smart Exit Analyse
                    exit_signal = await check_position_exit(position_data, market_data, self.db, ki_state)
                    
                    # Wenn Smart Exit empfiehlt zu verkaufen
                    if exit_signal.should_exit:
                        should_exit = True
                        exit_reason = f"🧠 KI-EXIT ({exit_signal.exit_type}): {exit_signal.reasoning[0] if exit_signal.reasoning else 'Smart Analysis'}"
                        
                        # Log die KI-Entscheidung
                        await self.db.log(user_id, "WARNING", 
                            f"[SMART EXIT] {position.symbol} | Confidence: {exit_signal.confidence}% | Type: {exit_signal.exit_type}")
                        for reason in exit_signal.reasoning[:3]:
                            await self.db.log(user_id, "INFO", f"  → {reason}")
                        
                        # KI-Log eintragen
                        await self.ki_engine.log_decision(user_id, {
                            'type': 'SMART_EXIT',
                            'symbol': position.symbol,
                            'exit_type': exit_signal.exit_type,
                            'confidence': exit_signal.confidence,
                            'pnl_at_exit': pnl_pct,
                            'reasons': exit_signal.reasoning
                        })
                
                except Exception as smart_err:
                    logger.warning(f"Smart Exit error for {position.symbol}: {smart_err}")
                    # Fallback auf normale SL/TP Checks
                
                # ============ FALLBACK: STOP LOSS CHECK ============
                if not should_exit and current_price <= position.stop_loss:
                    should_exit = True
                    if position.sl_moved_to_entry:
                        exit_reason = f"🔄 BREAK-EVEN EXIT @ {current_price:.4f}"
                    else:
                        exit_reason = f"🛑 STOP LOSS @ {current_price:.4f}"
                
                # ============ FALLBACK: TAKE PROFIT CHECK ============
                elif not should_exit and current_price >= position.take_profit:
                    should_exit = True
                    if position.partial_profit_taken:
                        exit_reason = f"🎯 FINAL TP (nach Teilgewinn) @ {current_price:.4f}"
                    else:
                        exit_reason = f"🎯 TAKE PROFIT @ {current_price:.4f}"
                
                if should_exit:
                    # Mark position as being sold BEFORE attempting sell
                    self._selling_positions.add(position_key)
                    
                    await self.db.log(user_id, "WARNING", f"[EXIT] {position.symbol} - {exit_reason} | PnL: {pnl_pct:.1f}%")
                    try:
                        await self.close_position(user_id, position, current_price, account, settings, exit_reason, mexc)
                        await self.db.update_live_account(account)
                    finally:
                        # Remove from selling set after done (success or fail)
                        self._selling_positions.discard(position_key)
                else:
                    # Log check every 5 minutes (10 checks)
                    if not hasattr(self, '_exit_log_counter'):
                        self._exit_log_counter = {}
                    counter_key = f"{user_id}_{position.symbol}"
                    self._exit_log_counter[counter_key] = self._exit_log_counter.get(counter_key, 0) + 1
                    if self._exit_log_counter[counter_key] >= 10:
                        sl_label = "BE" if position.sl_moved_to_entry else f"{position.stop_loss:.4f}"
                        partial_label = " [50% verkauft]" if position.partial_profit_taken else ""
                        await self.db.log(user_id, "INFO", 
                            f"[EXIT CHECK] {position.symbol}: Preis={current_price:.4f} | SL={sl_label} | PnL={pnl_pct:.1f}%{partial_label}")
                        self._exit_log_counter[counter_key] = 0
                    
            except Exception as e:
                logger.error(f"Exit check error for {position.symbol}: {e}")
                await self.db.log(user_id, "ERROR", f"[EXIT] {position.symbol} Check Fehler: {str(e)[:50]}")

    async def take_partial_profit(
        self, user_id: str, position, current_price: float,
        account, settings, mexc,
        close_pct: float, move_sl_to_entry: bool
    ):
        """Take partial profit by selling a percentage of the position"""
        try:
            # Calculate partial quantity to sell
            partial_qty = position.qty * (close_pct / 100)
            
            # Apply exchange filters
            formatted_qty = order_sizer.round_quantity(position.symbol, partial_qty)
            if formatted_qty is None or formatted_qty <= 0:
                await self.db.log(user_id, "WARNING", f"[PARTIAL] Ungültige Qty für {position.symbol}")
                return False
            
            # Check if we actually have this token in wallet
            try:
                account_info = await mexc.get_account()
                base_asset = position.symbol.replace('USDT', '')
                asset_balance = next(
                    (b for b in account_info.get('balances', []) if b.get('asset') == base_asset),
                    {'free': '0'}
                )
                available_qty = float(asset_balance.get('free', 0))
                
                if available_qty < formatted_qty:
                    formatted_qty = order_sizer.round_quantity(position.symbol, available_qty * 0.95)
                    if formatted_qty is None or formatted_qty <= 0:
                        await self.db.log(user_id, "WARNING", f"[PARTIAL] Nicht genug {base_asset} verfügbar")
                        return False
            except Exception:
                pass
            
            # Place REAL partial sell order
            await self.db.log(user_id, "WARNING", 
                f"[PARTIAL] ⚡ SELL {formatted_qty:.4f} {position.symbol} @ MARKET ({close_pct}% Teilgewinn)")
            
            order_result = await mexc.place_order(
                symbol=position.symbol,
                side="SELL",
                order_type="MARKET",
                quantity=formatted_qty
            )
            
            if order_result.get('status') != 'FILLED':
                await self.db.log(user_id, "ERROR", f"[PARTIAL] Order nicht gefüllt: {order_result}")
                return False
            
            # Get actual execution price
            actual_qty_sold = float(order_result.get('executedQty', formatted_qty))
            cumulative_quote = float(order_result.get('cummulativeQuoteQty', 0))
            actual_exit_price = cumulative_quote / actual_qty_sold if actual_qty_sold > 0 else current_price
            
            # Calculate PnL for the partial sell
            partial_pnl = (actual_exit_price - position.entry_price) * actual_qty_sold
            partial_pnl_pct = ((actual_exit_price - position.entry_price) / position.entry_price) * 100
            
            # Update position
            if position.original_qty is None:
                position.original_qty = position.qty
            position.qty -= actual_qty_sold
            position.partial_profit_taken = True
            position.partial_profit_time = datetime.now(timezone.utc)
            
            # Move SL to break-even (entry price)
            if move_sl_to_entry:
                old_sl = position.stop_loss
                position.stop_loss = position.entry_price
                position.sl_moved_to_entry = True
                await self.db.log(user_id, "INFO", 
                    f"[PARTIAL] 🔒 SL auf Break-Even verschoben: {old_sl:.6f} → {position.entry_price:.6f}")
            
            # Record partial trade
            await self.db.add_trade({
                'user_id': user_id,
                'ts': datetime.now(timezone.utc),
                'symbol': position.symbol,
                'side': 'SELL',
                'qty': actual_qty_sold,
                'entry': position.entry_price,
                'exit': actual_exit_price,
                'pnl': round(partial_pnl, 4),
                'pnl_pct': round(partial_pnl_pct, 2),
                'mode': 'live',
                'reason': f"PARTIAL {close_pct}% @ +{partial_pnl_pct:.1f}%",
                'notional': round(cumulative_quote, 2)
            })
            
            await self.db.log(user_id, "WARNING", 
                f"[PARTIAL] ✅ {position.symbol} Teilgewinn: +${partial_pnl:.2f} (+{partial_pnl_pct:.1f}%) | Rest: {position.qty:.4f}")
            
            return True
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"[PARTIAL] Fehler: {str(e)[:80]}")
            logger.error(f"Partial profit error: {e}")
            return False

    
    async def process_user(self, user_id: str):
        """Process trading for a single user (LIVE only)"""
        settings = await self.db.get_settings(user_id)
        
        # Only process live mode
        if not (settings.live_running and settings.live_confirmed):
            return
        
        # Load exchange info once
        if not self.exchange_info_loaded:
            try:
                mexc = MexcClient()
                exchange_info = await mexc.get_exchange_info()
                order_sizer.update_symbol_filters(exchange_info)
                self.exchange_info_loaded = True
                logger.info("Exchange info loaded for order sizing")
            except Exception as e:
                logger.error(f"Failed to load exchange info: {e}")
        
        # Refresh top pairs every 4 hours
        should_refresh = True
        if settings.last_pairs_refresh:
            last_refresh = settings.last_pairs_refresh
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=timezone.utc)
            should_refresh = (datetime.now(timezone.utc) - last_refresh) > timedelta(hours=4)
        
        if should_refresh:
            await self.refresh_top_pairs(user_id)
            settings = await self.db.get_settings(user_id)
        
        if not settings.top_pairs:
            await self.db.log(user_id, "WARNING", "No top pairs available")
            return
        
        await self.db.log(user_id, "WARNING", "[LIVE] Starting trading cycle")
        await self.scan_and_trade(user_id, settings)
        await self.db.update_settings(user_id, {'live_heartbeat': datetime.now(timezone.utc)})
    
    async def refresh_top_pairs(self, user_id: str):
        """INTELLIGENT MOMENTUM ROTATION: Select coins optimized for trade size"""
        try:
            settings = await self.db.get_settings(user_id)
            
            # Get AI position size for intelligent filtering
            trading_mode = TradingMode(settings.trading_mode) if settings.trading_mode else TradingMode.MANUAL
            is_ai_mode = trading_mode != TradingMode.MANUAL
            
            # Get USDT free balance for position sizing
            mexc = MexcClient()
            keys = await self.db.get_mexc_keys(user_id)
            usdt_free = 500  # Default fallback
            if keys:
                try:
                    mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
                    account_info = await mexc.get_account()
                    usdt_balance = next(
                        (b for b in account_info.get('balances', []) if b.get('asset') == 'USDT'),
                        {'free': '500'}
                    )
                    usdt_free = float(usdt_balance.get('free', 500))
                except Exception:
                    usdt_free = settings.trading_budget_usdt or 500
            
            # Calculate expected position size for filtering - NEW: based on available USDT
            trading_budget = settings.trading_budget_usdt or 500
            if is_ai_mode:
                profile = RISK_PROFILES_V2.get(trading_mode, {})
                # Use midpoint of position % range
                position_pct = (profile.get('position_pct_min', 10) + profile.get('position_pct_max', 25)) / 2
                expected_position_size = usdt_free * (position_pct / 100)
                # Apply trading budget cap
                expected_position_size = min(expected_position_size, trading_budget)
            else:
                expected_position_size = settings.live_max_order_usdt or 50
            
            await self.db.log(user_id, "INFO", 
                f"🔍 Intelligente Coin-Suche gestartet | Modus: {trading_mode.value} | USDT Free: ${usdt_free:.2f} | Erwartete Order: ${expected_position_size:.2f}")
            
            mexc = MexcClient()
            # Fetch 100 coins as requested by user
            momentum_pairs = await mexc.get_momentum_universe(quote="USDT", base_limit=100)
            
            await self.db.log(user_id, "INFO", f"📊 {len(momentum_pairs)} USDT Coins gefunden - starte Filterung...")
            
            filtered_pairs = []
            skipped_bearish = 0
            skipped_price_too_high = 0
            skipped_price_filter_examples = []
            
            for pair_data in momentum_pairs:
                symbol = pair_data['symbol']
                price = pair_data.get('price', 0)
                
                if price <= 0:
                    continue
                
                # ============ INTELLIGENT PRICE FILTER ============
                # Calculate what quantity we could buy
                potential_qty = expected_position_size / price if price > 0 else 0
                
                # Filter 1: Position would be too small (< 0.1 units is often impractical)
                if potential_qty < 0.1:
                    skipped_price_too_high += 1
                    if len(skipped_price_filter_examples) < 3:
                        skipped_price_filter_examples.append(
                            f"{symbol} (Preis: ${price:.2f}, Qty: {potential_qty:.4f})"
                        )
                    continue
                
                # Filter 2: Trade value would be < 1% of coin price (inefficient capital)
                # This catches cases where we buy tiny fractions of expensive coins
                if expected_position_size < price * 0.01:
                    skipped_price_too_high += 1
                    if len(skipped_price_filter_examples) < 3:
                        skipped_price_filter_examples.append(
                            f"{symbol} (Preis: ${price:.2f} zu hoch für ${expected_position_size:.2f} Trade)"
                        )
                    continue
                
                # Optimal: Coins where our trade represents meaningful position
                # Prefer coins where we can buy at least 1 unit OR trade is >5% of price
                is_optimal = potential_qty >= 1.0 or expected_position_size >= price * 0.05
                
                try:
                    klines_4h = await mexc.get_klines(symbol, interval="4h", limit=250)
                    
                    if len(klines_4h) >= 200:
                        regime, regime_ctx = self.regime_detector.detect_regime(klines_4h)
                        
                        # AI Aggressive: Accept ALL regimes (BULLISH prioritized, then SIDEWAYS, then BEARISH)
                        # Other modes: Only BULLISH
                        acceptable_regimes = ["BULLISH"]
                        if trading_mode == TradingMode.AI_AGGRESSIVE:
                            acceptable_regimes = ["BULLISH", "SIDEWAYS", "BEARISH"]
                        elif trading_mode == TradingMode.AI_MODERATE:
                            acceptable_regimes = ["BULLISH", "SIDEWAYS"]
                        
                        if regime in acceptable_regimes:
                            # Priority score: BULLISH=3, SIDEWAYS=2, BEARISH=1
                            regime_priority = {"BULLISH": 3, "SIDEWAYS": 2, "BEARISH": 1}.get(regime, 0)
                            filtered_pairs.append({
                                **pair_data,
                                'regime': regime,
                                'regime_priority': regime_priority,
                                'adx': regime_ctx.get('adx', 0),
                                'potential_qty': potential_qty,
                                'is_optimal': is_optimal
                            })
                            
                            # Get up to 100 coins for full rotation
                            if len(filtered_pairs) >= 100:
                                break
                        else:
                            skipped_bearish += 1
                except Exception as e:
                    logger.warning(f"Error checking regime for {symbol}: {e}")
                    continue
            
            # Sort: Prioritize by regime (BULLISH > SIDEWAYS > BEARISH), then optimal coins, then by ADX
            filtered_pairs.sort(key=lambda x: (
                x.get('regime_priority', 0),  # BULLISH=3, SIDEWAYS=2, BEARISH=1
                x.get('is_optimal', False), 
                x.get('adx', 0)
            ), reverse=True)
            
            # Store ALL filtered coins for rotation (up to 100)
            all_tradable_symbols = [p['symbol'] for p in filtered_pairs[:100]]
            
            # Save first batch (20) as active, store all for rotation
            active_batch = all_tradable_symbols[:self.COINS_PER_BATCH]
            
            await self.db.update_settings(user_id, {
                'top_pairs': active_batch,
                'all_pairs': all_tradable_symbols,  # Store all for rotation
                'last_pairs_refresh': datetime.now(timezone.utc)
            })
            
            # Reset batch index
            self.user_coin_batch[user_id] = 0
            self.user_all_coins[user_id] = all_tradable_symbols
            
            # Detailed logging
            bullish_count = sum(1 for p in filtered_pairs if p.get('regime') == 'BULLISH')
            sideways_count = sum(1 for p in filtered_pairs if p.get('regime') == 'SIDEWAYS')
            
            regime_info = f"{bullish_count} BULLISH"
            if sideways_count > 0:
                regime_info += f" + {sideways_count} SIDEWAYS"
            
            total_batches = (len(all_tradable_symbols) + self.COINS_PER_BATCH - 1) // self.COINS_PER_BATCH
            
            await self.db.log(
                user_id, "INFO", 
                f"✅ Coin-Pool aktualisiert:\n"
                f"   • {len(all_tradable_symbols)} Coins total ({regime_info})\n"
                f"   • {total_batches} Batches à {self.COINS_PER_BATCH} Coins\n"
                f"   • Aktiver Batch: 1-{min(self.COINS_PER_BATCH, len(all_tradable_symbols))}\n"
                f"   • {skipped_price_too_high} übersprungen (Preis zu hoch)\n"
                f"   • {skipped_bearish} übersprungen (BEARISH)",
                {'symbols': active_batch[:10]}
            )
            
            if skipped_price_filter_examples:
                await self.db.log(
                    user_id, "INFO",
                    f"💡 Beispiele gefilterter Coins (Preis zu hoch): {', '.join(skipped_price_filter_examples)}"
                )
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"Failed to run momentum rotation: {str(e)}")
    
    async def scan_and_trade(self, user_id: str, settings: UserSettings):
        """Scan for trading opportunities and execute (LIVE only) with AI support"""
        account = await self.db.get_live_account(user_id)
        scan_time = datetime.now(timezone.utc)
        
        # Initialize tracking
        if user_id not in self.user_initial_equity:
            self.user_initial_equity[user_id] = account.equity if account else 10000.0
        
        strategy = TradingStrategy(
            ema_fast=settings.ema_fast,
            ema_slow=settings.ema_slow,
            rsi_period=settings.rsi_period,
            rsi_min=settings.rsi_min,
            rsi_overbought=settings.rsi_overbought
        )
        risk_mgr = RiskManager(settings)
        
        # Get MEXC client with user keys
        mexc = await self.get_user_mexc_client(user_id, settings)
        
        # Get live USDT balance
        live_usdt_free = 0
        try:
            account_info = await mexc.get_account()
            balances = account_info.get('balances', [])
            usdt_balance = next((b for b in balances if b.get('asset') == 'USDT'), None)
            if usdt_balance:
                live_usdt_free = float(usdt_balance.get('free', 0))
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"[LIVE] Failed to fetch MEXC balance: {e}")
            return
        
        # Calculate budget
        used_budget = self.calculate_used_budget(account) if account else 0
        budget_info = self.calculate_live_budget(settings, used_budget, live_usdt_free)
        available_budget = budget_info['remaining_budget']
        
        # DAILY CAP CHECK
        today_exposure = await self.db.get_today_exposure(user_id, 'live')
        today_trades = await self.db.get_today_trades_count(user_id, 'live')
        today_pnl = await self.db.get_today_pnl(user_id, 'live')
        daily_cap = settings.live_daily_cap_usdt
        daily_remaining = max(0, daily_cap - today_exposure)
        
        # Calculate drawdown
        initial_equity = self.user_initial_equity.get(user_id, live_usdt_free)
        current_equity = live_usdt_free + used_budget
        drawdown_pct = ((current_equity - initial_equity) / initial_equity * 100) if initial_equity > 0 else 0
        
        positions_count = len(account.open_positions) if account else 0
        
        # ============ AI MODE SETUP ============
        trading_mode = TradingMode(settings.trading_mode) if settings.trading_mode else TradingMode.MANUAL
        is_ai_mode = trading_mode != TradingMode.MANUAL
        
        ai_decision = None
        effective_max_positions = settings.max_positions
        effective_position_size = settings.live_max_order_usdt
        ai_min_position = None
        ai_max_position = None
        
        # Get AI V2 profile limits and calculate expected position sizes based on AVAILABLE USDT
        if is_ai_mode:
            profile = RISK_PROFILES_V2.get(trading_mode, {})
            effective_max_positions = profile.get('max_positions', settings.max_positions)
            
            # NEW: Calculate AI position size based on AVAILABLE USDT (not trading budget!)
            position_pct_min = profile.get('position_pct_min', 5.0)
            position_pct_max = profile.get('position_pct_max', 20.0)
            
            # Position size = available_usdt * profile_percent
            ai_min_position = round(live_usdt_free * (position_pct_min / 100), 2)
            ai_max_position = round(live_usdt_free * (position_pct_max / 100), 2)
            
            # Apply trading budget cap
            trading_budget = settings.trading_budget_usdt or 500
            trading_budget_remaining = max(0, trading_budget - used_budget)
            ai_min_position = min(ai_min_position, trading_budget_remaining)
            ai_max_position = min(ai_max_position, trading_budget_remaining)
            
            # Use midpoint as effective size
            effective_position_size = round((ai_min_position + ai_max_position) / 2, 2)
            
            await self.db.log(user_id, "INFO", 
                f"[LIVE] 🤖 AI V2 Mode: {trading_mode.value} | Position: {position_pct_min:.0f}%-{position_pct_max:.0f}% USDT | Berechnet: ${ai_min_position:.0f}-${ai_max_position:.0f} | Max Pos: {effective_max_positions}")
        
        # Update status - use calculated AI values if in AI mode
        await self.db.update_settings(user_id, {
            'live_last_scan': scan_time.isoformat(),
            'live_last_decision': 'SCANNING',
            'live_budget_used': round(used_budget, 2),
            'live_budget_available': round(available_budget, 2),
            'live_daily_used': round(today_exposure, 2),
            'live_daily_remaining': round(daily_remaining, 2),
            'live_positions_count': positions_count,
            'ai_confidence': ai_decision.confidence if ai_decision else (85 if is_ai_mode else None),
            'ai_risk_score': ai_decision.risk_score if ai_decision else None,
            'ai_reasoning': ai_decision.reasoning if ai_decision else None,
            'ai_min_position': ai_decision.position_size_usdt if ai_decision else ai_min_position,
            'ai_max_position': ai_decision.position_size_usdt if ai_decision else ai_max_position,
            'ai_current_position': ai_decision.position_size_usdt if ai_decision else effective_position_size
        })
        
        mode_label = f"🤖 {trading_mode.value}" if is_ai_mode else "Manual"
        trade_size_label = f"${ai_min_position:.0f}-${ai_max_position:.0f}" if is_ai_mode and ai_min_position else f"${effective_position_size:.0f}"
        await self.db.log(user_id, "INFO", 
            f"[LIVE] ═══ SCAN START ({mode_label}) ═══ USDT Free: ${live_usdt_free:.2f} | Trade: {trade_size_label} | Positions: {positions_count}/{effective_max_positions}")
        
        # Budget checks
        min_notional = settings.live_min_notional_usdt
        
        if available_budget < min_notional:
            await self.db.log(user_id, "INFO", f"[LIVE] ⛔ BLOCKED: Kein Budget (${available_budget:.2f} < ${min_notional})")
            await self.db.update_settings(user_id, {
                'live_last_decision': f'BLOCKED: Budget zu niedrig (${available_budget:.2f})',
                'live_last_symbol': '-'
            })
            return
        
        if daily_remaining < min_notional:
            await self.db.log(user_id, "INFO", f"[LIVE] ⛔ BLOCKED: Tageslimit erreicht (${today_exposure:.2f}/${daily_cap:.2f})")
            await self.db.update_settings(user_id, {
                'live_last_decision': 'BLOCKED: Tageslimit',
                'live_last_symbol': '-'
            })
            return
        
        # Use AI-adjusted max positions
        if positions_count >= effective_max_positions:
            await self.db.log(user_id, "INFO", f"[LIVE] ⛔ BLOCKED: Max Positionen erreicht ({positions_count}/{effective_max_positions})")
            await self.db.update_settings(user_id, {
                'live_last_decision': f'BLOCKED: Max Positionen ({positions_count}/{effective_max_positions})',
                'live_last_symbol': '-'
            })
            return
        
        # Cooldown DEAKTIVIERT - Bot kann sofort wieder traden
        # if self.is_in_cooldown(user_id, settings.cooldown_candles):
        #     cooldown_mins = settings.cooldown_candles * 15
        #     await self.db.log(user_id, "INFO", f"[LIVE] ⏸️ SKIPPED: Cooldown active ({cooldown_mins} Min)")
        #     return
        
        # Scan for signals - scan all available pairs (up to 20)
        signal_candidates = []
        symbols_checked = 0
        symbols_already_owned = 0
        
        # Get list of symbols we already own (for diversification)
        owned_symbols = set()
        if account and account.open_positions:
            owned_symbols = {pos.symbol for pos in account.open_positions}
        
        # ADDITIONAL CHECK: Also check _buying_positions to prevent race conditions
        buying_symbols = {key.split('_')[1] for key in self._buying_positions if '_' in key}
        owned_symbols = owned_symbols.union(buying_symbols)
        
        # Calculate effective position size for runtime filtering
        effective_scan_position = effective_position_size if is_ai_mode else settings.live_max_order_usdt
        
        await self.db.log(user_id, "INFO", f"[LIVE] 🔍 Scanne {len(settings.top_pairs[:20])} Coins | Trade-Größe: ${effective_scan_position:.2f} | Bereits im Portfolio: {len(owned_symbols)}")
        
        # Get coins to scan based on user selection
        coins_to_scan = settings.top_pairs[:20]
        
        # If user has selected specific SPOT coins, filter the list
        if not getattr(settings, 'spot_trade_all', True):
            selected_spot = getattr(settings, 'selected_spot_coins', [])
            if selected_spot:
                coins_to_scan = [c for c in coins_to_scan if c in selected_spot]
                await self.db.log(user_id, "INFO", f"[LIVE] 🎯 User-Auswahl: {len(selected_spot)} SPOT Coins aktiviert")
        
        for symbol in coins_to_scan:
            symbols_checked += 1
            try:
                # Skip if we already own this symbol (diversification)
                if symbol in owned_symbols:
                    symbols_already_owned += 1
                    continue
                
                # Check if symbol is paused (DB-based pause from consecutive losses)
                is_paused = await self.db.is_symbol_paused(user_id, symbol)
                if is_paused:
                    continue
                
                # Get 4H klines for regime
                klines_4h = await mexc.get_klines(symbol, interval="4h", limit=250)
                if len(klines_4h) < 200:
                    continue
                
                # Detect regime
                regime, regime_context = self.regime_detector.detect_regime(klines_4h)
                adx_value = regime_context.get('adx', 0)
                
                # Calculate volatility percentile (ATR based)
                current_price = float(klines_4h[-1][4])
                atr_values = []
                for i in range(14, len(klines_4h)):
                    high = float(klines_4h[i][2])
                    low = float(klines_4h[i][3])
                    close_prev = float(klines_4h[i-1][4])
                    tr = max(high - low, abs(high - close_prev), abs(low - close_prev))
                    atr_values.append(tr)
                
                current_atr = sum(atr_values[-14:]) / 14 if len(atr_values) >= 14 else 0
                avg_atr = sum(atr_values) / len(atr_values) if atr_values else 1
                volatility_percentile = min(100, (current_atr / avg_atr) * 50) if avg_atr > 0 else 50
                atr_percent = (current_atr / current_price * 100) if current_price > 0 else 1
                
                # AI Mode: Get AI decision with REAL market data (V2 Engine)
                if is_ai_mode:
                    # Get USDT free balance for position sizing
                    try:
                        account_info = await mexc.get_account()
                        usdt_balance = next(
                            (b for b in account_info.get('balances', []) if b.get('asset') == 'USDT'),
                            {'free': '0'}
                        )
                        usdt_free = float(usdt_balance.get('free', 0))
                    except:
                        usdt_free = available_budget
                    
                    # Calculate open positions value
                    open_positions_value = sum(
                        pos.entry_price * pos.qty for pos in account.open_positions
                    ) if account and account.open_positions else 0
                    
                    # Convert regime string (BULLISH/SIDEWAYS/BEARISH) to enum (bullish/sideways/bearish)
                    try:
                        regime_enum = MarketRegime(regime.lower())
                    except ValueError:
                        await self.db.log(user_id, "WARNING", f"[LIVE] ⚠️ {symbol}: Unbekanntes Regime '{regime}' - überspringe")
                        continue
                    
                    # Get 24h volume for low-cap detection
                    volume_24h = 0
                    try:
                        ticker = await mexc.get_ticker_24h(symbol)
                        volume_24h = float(ticker.get('quoteVolume', 0))  # Volume in USDT
                    except Exception:
                        pass
                    
                    market_conditions = MarketConditions(
                        regime=regime_enum,
                        adx_value=adx_value,
                        atr_value=current_atr,
                        atr_percent=atr_percent,
                        volatility_percentile=volatility_percentile,
                        momentum_score=regime_context.get('momentum', 0),
                        rsi_value=regime_context.get('rsi', 50),
                        current_price=current_price,
                        volume_24h=volume_24h
                    )
                    
                    # Calculate remaining trading budget
                    trading_budget = settings.trading_budget_usdt or 500
                    trading_budget_remaining = max(0, trading_budget - open_positions_value)
                    
                    account_state = AccountState(
                        total_equity=current_equity,
                        usdt_free=usdt_free,
                        current_drawdown_pct=drawdown_pct,
                        open_positions_count=positions_count,
                        open_positions_value=open_positions_value,
                        today_pnl=today_pnl,
                        today_trades_count=today_trades
                    )
                    
                    # Get AI decision - use futures-aware method if enabled
                    if settings.futures_enabled:
                        ai_decision = self.ai_engine.make_futures_decision(
                            user_id, trading_mode, market_conditions, account_state, 
                            trading_budget_remaining, 
                            user_futures_enabled=True,
                            max_leverage=settings.futures_max_leverage
                        )
                    else:
                        ai_decision = self.ai_engine.make_decision(
                            user_id, trading_mode, market_conditions, account_state, trading_budget_remaining
                        )
                    
                    # ============ KI LEARNING CHECK ============
                    # Ab Trade 11: KI muss Trade genehmigen
                    ki_state = await self.ki_engine.get_ki_state(user_id)
                    if ki_state.ki_active:
                        # KI ist aktiv - muss Trade prüfen
                        market_data_for_ki = {
                            'rsi': regime_context.get('rsi', 50),
                            'adx': adx_value,
                            'volume_24h': volume_24h,
                            'regime': regime,
                            'direction': ai_decision.direction if hasattr(ai_decision, 'direction') else 'long'
                        }
                        should_trade, ki_reason, ki_warnings = self.ki_engine.should_ki_trade(ki_state, market_data_for_ki)
                        
                        if not should_trade:
                            await self.db.log(user_id, "INFO", 
                                f"[KI] 🧠 VETO für {symbol}: {ki_reason} | Warnings: {', '.join(ki_warnings)}")
                            continue
                        else:
                            await self.db.log(user_id, "INFO", 
                                f"[KI] ✅ {symbol}: {ki_reason} (Confidence: {ki_state.ki_confidence*100:.0f}%)")
                    # ============ END KI LEARNING CHECK ============
                    
                    if not ai_decision.should_trade:
                        reason = ai_decision.reasoning[-1] if ai_decision.reasoning else 'Unbekannt'
                        await self.db.log(user_id, "INFO", f"[LIVE] 🤖 {symbol}: AI SKIP - {reason}")
                        continue
                    
                    # Update effective position size from AI V2
                    effective_position_size = ai_decision.position_size_usdt
                
                # Only BULLISH for manual mode
                if not is_ai_mode and regime != "BULLISH":
                    continue
                
                # Get 15m klines for entry signal
                klines_15m = await mexc.get_klines(symbol, interval="15m", limit=500)
                if len(klines_15m) < settings.ema_slow:
                    continue
                
                # Check signal
                signal, context = strategy.generate_signal(klines_15m)
                if signal != "LONG":
                    # Log why no signal
                    rsi_val = context.get('rsi', 50)
                    ema_fast = context.get('ema_fast', 0)
                    ema_slow = context.get('ema_slow', 0)
                    reason = "Kein LONG Signal"
                    if rsi_val > 70:
                        reason = "RSI überkauft ({:.0f})".format(rsi_val)
                    elif ema_fast < ema_slow:
                        reason = "EMA bearish (Fast < Slow)"
                    await self.db.log(user_id, "INFO", f"[LIVE] ⏭️ {symbol}: {reason} | RSI={rsi_val:.0f}, ADX={adx_value:.1f}")
                    continue
                
                # SIGNAL FOUND!
                current_price = float(klines_15m[-1][4])
                ema_fast_val = context.get('ema_fast', 0)
                ema_slow_val = context.get('ema_slow', 0)
                rsi_val = context.get('rsi', 0)
                
                # Calculate stop/take profit (AI V2 with ATR-based SL/TP)
                if is_ai_mode and ai_decision:
                    # Use AI V2 ATR-based SL/TP prices directly
                    stop_loss = ai_decision.stop_loss_price
                    take_profit = ai_decision.take_profit_price
                    await self.db.log(user_id, "INFO", 
                        f"[LIVE] 🤖 {symbol}: SL={stop_loss:.8f} (-{ai_decision.stop_loss_pct:.2f}%), TP={take_profit:.8f} (+{ai_decision.take_profit_pct:.2f}%), R:R={ai_decision.risk_reward_ratio:.1f}:1")
                else:
                    # Manual mode - use ATR-based calculation
                    atr = strategy.calculate_atr(klines_15m, 14)
                    if atr:
                        stop_loss = current_price - (atr * 2.0)
                        risk_amount = current_price - stop_loss
                        take_profit = current_price + (risk_amount * 2.5)
                    else:
                        stop_loss = risk_mgr.calculate_stop_loss(current_price, None)
                        take_profit = risk_mgr.calculate_take_profit(current_price, stop_loss)
                
                # Score calculation
                ema_spread = ((ema_fast_val - ema_slow_val) / ema_slow_val * 100) if ema_slow_val > 0 else 0
                opportunity_score = (
                    adx_value * 0.4 +
                    (100 - rsi_val) * 0.3 +
                    min(ema_spread * 10, 30) * 0.3
                )
                
                signal_candidates.append({
                    'symbol': symbol,
                    'score': opportunity_score,
                    'regime': regime,
                    'adx': adx_value,
                    'rsi': rsi_val,
                    'current_price': current_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'klines_15m': klines_15m,
                    'context': context,
                    'ai_decision': ai_decision,
                    'volatility_percentile': volatility_percentile
                })
                
                await self.db.log(user_id, "INFO", f"[LIVE] SIGNAL: {symbol} Score={opportunity_score:.1f}, ADX={adx_value:.1f}, RSI={rsi_val:.1f}")
                
            except Exception as e:
                await self.db.log(user_id, "ERROR", f"[LIVE] Error scanning {symbol}: {str(e)}")
        
        # Execute best signal
        if signal_candidates:
            signal_candidates.sort(key=lambda x: x['score'], reverse=True)
            
            await self.db.log(user_id, "INFO", 
                f"[LIVE] 🎯 {len(signal_candidates)} Signale! Wähle besten: " +
                ", ".join([f"{c['symbol']}({c['score']:.1f})" for c in signal_candidates[:5]])
            )
            
            # Get AI decision from best candidate
            best_ai_decision = signal_candidates[0].get('ai_decision') if signal_candidates else None
            
            for candidate in signal_candidates:
                symbol = candidate['symbol']
                candidate_ai = candidate.get('ai_decision')
                
                # Use AI position size if available
                position_budget = candidate_ai.position_size_usdt if candidate_ai else available_budget
                
                # Determine if we should use FUTURES (AI mode with futures enabled)
                use_futures = False
                if is_ai_mode and candidate_ai and settings.futures_enabled:
                    market_type = getattr(candidate_ai, 'market_type', 'spot')
                    use_futures = market_type == 'futures'
                
                # FINAL SAFETY CHECK: Double-check we don't already own this symbol
                current_owned = set()
                if account and account.open_positions:
                    current_owned = {pos.symbol for pos in account.open_positions}
                
                if symbol in current_owned:
                    await self.db.log(user_id, "WARNING", f"[LIVE] ⚠️ {symbol} bereits im Portfolio - Trade übersprungen")
                    continue
                
                if use_futures:
                    # Execute FUTURES trade
                    trade_success = await self.open_futures_position(
                        user_id, symbol, candidate, account, settings, 
                        position_budget, candidate_ai
                    )
                    trade_type = f"FUTURES {candidate_ai.direction.upper()} {candidate_ai.leverage}x"
                else:
                    # Execute SPOT trade (existing logic)
                    trade_success = await self.open_live_position(
                        user_id, symbol, candidate, account, settings, strategy, risk_mgr, mexc, 
                        position_budget, is_ai_mode, candidate_ai
                    )
                    trade_type = "SPOT"
                
                if trade_success:
                    self.set_last_trade_time(user_id)
                    decision_text = f'TRADE [{trade_type}]: {symbol} (Score: {candidate["score"]:.1f})'
                    if is_ai_mode and candidate_ai:
                        decision_text = f'🤖 AI TRADE [{trade_type}]: {symbol} (Score: {candidate["score"]:.1f})'
                    
                    # ============ KI LEARNING: Record Trade ============
                    await self.ki_engine.record_trade(user_id, {
                        'symbol': symbol,
                        'type': trade_type,
                        'entry_price': candidate['current_price'],
                        'rsi': candidate.get('rsi', 50),
                        'adx': candidate.get('adx', 0),
                        'volume_24h': candidate.get('volume_24h', 0),
                        'regime': candidate.get('regime', 'UNKNOWN')
                    })
                    # ============ END KI LEARNING ============
                    
                    await self.db.update_settings(user_id, {
                        'live_last_decision': decision_text,
                        'live_last_regime': candidate['regime'],
                        'live_last_symbol': symbol,
                        'ai_confidence': candidate_ai.confidence if candidate_ai else None,
                        'ai_risk_score': candidate_ai.risk_score if candidate_ai else None,
                        'ai_reasoning': candidate_ai.reasoning if candidate_ai else None,
                        'ai_min_position': candidate_ai.position_size_usdt if candidate_ai else None,
                        'ai_max_position': candidate_ai.position_size_usdt if candidate_ai else None,
                        'ai_current_position': candidate_ai.position_size_usdt if candidate_ai else None,
                        'ai_last_override': {
                            'timestamp': scan_time.isoformat(),
                            'symbol': symbol,
                            'position_size': candidate_ai.position_size_usdt if candidate_ai else None,
                            'stop_loss_pct': candidate_ai.stop_loss_pct if candidate_ai else None,
                            'take_profit_pct': candidate_ai.take_profit_pct if candidate_ai else None,
                            'overrides': []
                        } if is_ai_mode else None
                    })
                    break
                else:
                    await self.db.log(user_id, "WARNING", f"[LIVE] ⚠️ {symbol} fehlgeschlagen - versuche nächsten...")
            else:
                # No trade executed but we have AI data from best candidate
                if best_ai_decision:
                    await self.db.update_settings(user_id, {
                        'ai_confidence': best_ai_decision.confidence,
                        'ai_risk_score': best_ai_decision.risk_score,
                        'ai_reasoning': best_ai_decision.reasoning,
                        'ai_min_position': best_ai_decision.position_size_usdt,
                        'ai_max_position': best_ai_decision.position_size_usdt,
                        'ai_current_position': best_ai_decision.position_size_usdt,
                    })
        else:
            # NO SIGNALS FOUND - Rotate to next batch of coins
            await self.rotate_to_next_batch(user_id, settings)
            
            await self.db.update_settings(user_id, {
                'live_last_decision': f'KEIN SIGNAL bei {symbols_checked} Coins → Nächster Batch',
                'live_last_symbol': '-'
            })
            if symbols_already_owned > 0:
                await self.db.log(user_id, "INFO", f"[LIVE] 💼 {symbols_already_owned} Coins übersprungen (bereits im Portfolio)")
        
        await self.db.log(user_id, "INFO", f"[LIVE] ═══ SCAN COMPLETE ═══ {symbols_checked} Coins, {len(signal_candidates)} Signale, {symbols_already_owned} übersprungen")
    
    async def rotate_to_next_batch(self, user_id: str, settings: UserSettings):
        """Rotate to next batch of coins when no signals found"""
        # Get all coins (from memory or DB)
        if user_id not in self.user_all_coins or not self.user_all_coins[user_id]:
            # Load from DB
            all_pairs = getattr(settings, 'all_pairs', None) or settings.top_pairs
            self.user_all_coins[user_id] = all_pairs
            self.user_coin_batch[user_id] = 0
        
        all_coins = self.user_all_coins[user_id]
        if not all_coins:
            return
        
        # Calculate current and next batch
        current_batch = self.user_coin_batch.get(user_id, 0)
        total_batches = (len(all_coins) + self.COINS_PER_BATCH - 1) // self.COINS_PER_BATCH
        next_batch = (current_batch + 1) % total_batches
        
        # If we've cycled through all batches, refresh the coin pool
        if next_batch == 0:
            await self.db.log(user_id, "INFO", f"🔄 Alle {total_batches} Batches durchlaufen - Hole neue Coins...")
            await self.refresh_top_pairs(user_id)
            return
        
        # Get next batch of coins
        start_idx = next_batch * self.COINS_PER_BATCH
        end_idx = min(start_idx + self.COINS_PER_BATCH, len(all_coins))
        next_coins = all_coins[start_idx:end_idx]
        
        # Update settings with new active batch
        await self.db.update_settings(user_id, {
            'top_pairs': next_coins
        })
        
        self.user_coin_batch[user_id] = next_batch
        
        await self.db.log(user_id, "INFO", 
            f"🔄 Batch {next_batch + 1}/{total_batches} → Coins {start_idx + 1}-{end_idx}: {', '.join(next_coins[:5])}...")
    
    async def open_live_position(
        self, user_id: str, symbol: str, candidate: dict,
        account: PaperAccount, settings: UserSettings,
        strategy: TradingStrategy, risk_mgr: RiskManager,
        mexc: MexcClient, available_budget: float,
        is_ai_mode: bool = False, ai_decision = None
    ) -> bool:
        """Open a live position on MEXC with optional AI position sizing"""
        try:
            # SAFETY CHECK: Verify we don't already own this symbol
            if account and account.open_positions:
                owned = {pos.symbol for pos in account.open_positions}
                if symbol in owned:
                    await self.db.log(user_id, "WARNING", f"[LIVE] ⚠️ ABBRUCH: {symbol} bereits im Portfolio!")
                    return False
            
            current_price = candidate['current_price']
            stop_loss = candidate['stop_loss']
            take_profit = candidate['take_profit']
            min_notional = settings.live_min_notional_usdt
            
            # Calculate position size (AI or manual)
            if is_ai_mode and ai_decision and ai_decision.position_size_usdt > 0:
                ai_size = ai_decision.position_size_usdt
                
                # Check if we have enough available budget
                if ai_size > available_budget * 0.95:
                    # Not enough budget for AI-calculated size, use what we have
                    notional = available_budget * 0.95
                    await self.db.log(user_id, "INFO", f"[LIVE] 🤖 AI wollte ${ai_size:.2f}, verfügbar nur ${available_budget:.2f} → nutze ${notional:.2f}")
                elif ai_size < min_notional:
                    # AI calculated too small, try minimum if available
                    if available_budget >= min_notional:
                        notional = min_notional
                        await self.db.log(user_id, "INFO", f"[LIVE] 🤖 AI Size ${ai_size:.2f} < Min ${min_notional} → verwende Minimum")
                    else:
                        notional = available_budget * 0.95
                        await self.db.log(user_id, "INFO", f"[LIVE] 🤖 Budget ${available_budget:.2f} zu niedrig für Min ${min_notional}")
                else:
                    notional = ai_size
                    await self.db.log(user_id, "INFO", f"[LIVE] 🤖 AI Position Size: ${notional:.2f}")
            else:
                # Manual position sizing
                max_order = min(settings.live_max_order_usdt, available_budget)
                notional = min(max_order, available_budget * 0.95)
            
            if notional < min_notional:
                await self.db.log(user_id, "WARNING", f"[LIVE] Notional ${notional:.2f} below minimum ${min_notional} (Budget: ${available_budget:.2f})")
                return False
            
            qty = notional / current_price
            
            # Apply exchange filters
            formatted_qty = order_sizer.round_quantity(symbol, qty)
            if formatted_qty is None or formatted_qty <= 0:
                await self.db.log(user_id, "WARNING", f"[LIVE] Invalid quantity for {symbol}")
                return False
            
            # Place REAL order
            await self.db.log(user_id, "WARNING", f"[LIVE] ⚡ PLACING REAL ORDER: {symbol} BUY {formatted_qty} @ MARKET")
            
            order_result = await mexc.place_order(
                symbol=symbol,
                side="BUY",
                order_type="MARKET",
                quantity=formatted_qty
            )
            
            # Parse order result - get ACTUAL executed price
            executed_qty = float(order_result.get('executedQty', formatted_qty))
            
            # MEXC returns price=0 for MARKET orders, need to calculate from fills
            avg_price = 0
            fills = order_result.get('fills', [])
            if fills:
                total_qty = sum(float(f.get('qty', 0)) for f in fills)
                total_cost = sum(float(f.get('qty', 0)) * float(f.get('price', 0)) for f in fills)
                if total_qty > 0:
                    avg_price = total_cost / total_qty
                    
            # Fallback: if no fills data, get current ticker price
            if avg_price == 0 or avg_price == current_price:
                try:
                    ticker = await mexc.get_ticker_24h(symbol)
                    avg_price = float(ticker.get('lastPrice', current_price))
                except Exception:
                    avg_price = current_price
            
            # Recalculate SL/TP based on ACTUAL execution price
            if is_ai_mode and ai_decision:
                actual_stop_loss = avg_price * (1 - ai_decision.stop_loss_pct / 100)
                actual_take_profit = avg_price * (1 + ai_decision.take_profit_pct / 100)
            else:
                # Fallback to original calculated values adjusted for actual price
                sl_pct = (current_price - stop_loss) / current_price if current_price > 0 else 0.03
                tp_pct = (take_profit - current_price) / current_price if current_price > 0 else 0.075
                actual_stop_loss = avg_price * (1 - sl_pct)
                actual_take_profit = avg_price * (1 + tp_pct)
            
            actual_notional = executed_qty * avg_price
            
            await self.db.log(user_id, "INFO", 
                f"[LIVE] 📊 EXECUTED @ ${avg_price:.8f} | SL: ${actual_stop_loss:.8f} | TP: ${actual_take_profit:.8f}")
            
            # Create position record with ACTUAL execution price
            position = Position(
                symbol=symbol,
                side="LONG",
                entry_price=avg_price,
                qty=executed_qty,
                stop_loss=actual_stop_loss,
                take_profit=actual_take_profit,
                entry_time=datetime.now(timezone.utc)
            )
            
            # Update account
            if not account:
                account = PaperAccount(user_id=user_id, equity=0, cash=0, open_positions=[])
            
            account.open_positions.append(position)
            await self.db.update_live_account(account)
            
            # Record trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=symbol,
                side="BUY",
                qty=executed_qty,
                entry=avg_price,
                mode='live',
                reason=f"Score={candidate['score']:.1f}, ADX={candidate['adx']:.1f}",
                notional=actual_notional
            )
            await self.db.add_trade(trade)
            
            # === ML DATA COLLECTION: Speichere Snapshot für Training ===
            try:
                # Calculate SL/TP percentages for ML data
                calc_sl_pct = ai_decision.stop_loss_pct if (is_ai_mode and ai_decision) else ((current_price - stop_loss) / current_price * 100 if current_price > 0 else 3.0)
                calc_tp_pct = ai_decision.take_profit_pct if (is_ai_mode and ai_decision) else ((take_profit - current_price) / current_price * 100 if current_price > 0 else 7.5)
                
                market_data = {
                    'price_change_1h': candidate.get('price_change_1h', 0),
                    'price_change_24h': candidate.get('price_change_24h', 0),
                    'rsi': candidate.get('rsi', 50),
                    'adx': candidate.get('adx', 0),
                    'atr_percent': candidate.get('atr_percent', 0),
                    'ema_fast': candidate.get('ema_fast', 0),
                    'ema_slow': candidate.get('ema_slow', 0),
                    'ema_distance': candidate.get('ema_distance', 0),
                    'volume_24h': candidate.get('volume_24h', 0),
                    'volume_change': candidate.get('volume_change', 0),
                    'regime': candidate.get('regime', 'UNKNOWN'),
                    'volatility_percentile': candidate.get('volatility_percentile', 50),
                    'momentum_score': candidate.get('momentum', 0),
                    'position_percent': (actual_notional / available_budget * 100) if available_budget > 0 else 0,
                    'open_positions': len(account.open_positions) if account else 0
                }
                ai_data = {
                    'confidence': candidate.get('ai_confidence'),
                    'profile': settings.trading_mode
                }
                await self.ml_collector.save_entry_snapshot(
                    user_id=user_id,
                    symbol=symbol,
                    entry_price=avg_price,
                    position_size_usdt=actual_notional,
                    stop_loss_pct=calc_sl_pct,
                    take_profit_pct=calc_tp_pct,
                    market_data=market_data,
                    ai_data=ai_data
                )
                await self.db.log(user_id, "INFO", f"[ML] 📊 Training-Snapshot gespeichert für {symbol}")
            except Exception as ml_err:
                logger.warning(f"ML snapshot error: {ml_err}")
            # === END ML DATA COLLECTION ===
            
            await self.db.log(user_id, "WARNING",
                f"[LIVE] ✅ ORDER CONFIRMED: {symbol} | Qty: {executed_qty} | Price: ${avg_price:.4f} | Notional: ${actual_notional:.2f}")
            
            # === TELEGRAM BENACHRICHTIGUNG: Trade geöffnet ===
            await self.notify_telegram('trade_opened', {
                'symbol': symbol,
                'side': 'BUY',
                'quantity': executed_qty,
                'entry_price': avg_price,
                'value': actual_notional,
                'stop_loss': actual_stop_loss,
                'take_profit': actual_take_profit
            }, user_id)
            
            await self.db.log(user_id, "INFO",
                f"[LIVE] 📊 TRADE DETAILS | Stop: ${stop_loss:.4f} | TP: ${take_profit:.4f}")
            
            return True
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"[LIVE] ❌ ORDER FAILED: {symbol} - {str(e)}")
            return False
    
    async def close_position(
        self, user_id: str, position: Position, exit_price: float,
        account: PaperAccount, settings: UserSettings, reason: str, mexc: MexcClient
    ):
        """Close a SPOT or FUTURES position with real SELL order"""
        try:
            # Check if this is a Futures position
            is_futures = getattr(position, 'market_type', 'spot') == 'futures'
            
            if is_futures:
                # Close FUTURES position
                await self.close_futures_position(user_id, position, exit_price, account, settings, reason)
            else:
                # Close SPOT position (existing logic)
                await self._close_spot_position(user_id, position, exit_price, account, settings, reason, mexc)
                
        except Exception as e:
            logger.error(f"Close position error: {e}")
            await self.db.log(user_id, "ERROR", f"[LIVE] ❌ CLOSE FAILED: {position.symbol} - {str(e)}")
    
    async def _close_spot_position(
        self, user_id: str, position: Position, exit_price: float,
        account: PaperAccount, settings: UserSettings, reason: str, mexc: MexcClient
    ):
        """Close a SPOT position with real SELL order"""
        try:
            # Place REAL SELL order
            await self.db.log(user_id, "WARNING", f"[LIVE] ⚡ PLACING SELL ORDER: {position.symbol} SELL {position.qty}")
            
            formatted_qty = order_sizer.round_quantity(position.symbol, position.qty)
            if formatted_qty is None or formatted_qty <= 0:
                formatted_qty = position.qty
            
            order_result = await mexc.place_order(
                symbol=position.symbol,
                side="SELL",
                order_type="MARKET",
                quantity=formatted_qty
            )
            
            # Parse result
            executed_qty = float(order_result.get('executedQty', position.qty))
            actual_exit_price = float(order_result.get('price', exit_price))
            
            if actual_exit_price == 0:
                fills = order_result.get('fills', [])
                if fills:
                    total_qty = sum(float(f.get('qty', 0)) for f in fills)
                    total_cost = sum(float(f.get('qty', 0)) * float(f.get('price', 0)) for f in fills)
                    actual_exit_price = total_cost / total_qty if total_qty > 0 else exit_price
                else:
                    actual_exit_price = exit_price
            
            # Calculate PnL
            pnl = (actual_exit_price - position.entry_price) * executed_qty
            pnl_pct = ((actual_exit_price - position.entry_price) / position.entry_price) * 100
            
            # Remove from account
            account.open_positions.remove(position)
            account.cash += (executed_qty * actual_exit_price)
            
            # Record trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=position.symbol,
                side="SELL",
                qty=executed_qty,
                entry=position.entry_price,
                exit=actual_exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                mode='live',
                reason=reason,
                notional=position.entry_price * executed_qty
            )
            await self.db.add_trade(trade)
            
            # === ML DATA COLLECTION: Update Snapshot mit Exit-Ergebnis ===
            try:
                exit_reason_ml = "UNKNOWN"
                if "STOP" in reason.upper():
                    exit_reason_ml = "STOP_LOSS"
                elif "PROFIT" in reason.upper() or "TP" in reason.upper():
                    exit_reason_ml = "TAKE_PROFIT"
                elif "PARTIAL" in reason.upper():
                    exit_reason_ml = "PARTIAL"
                elif "MANUAL" in reason.upper():
                    exit_reason_ml = "MANUAL"
                elif "BREAK" in reason.upper() or "EVEN" in reason.upper():
                    exit_reason_ml = "BREAK_EVEN"
                
                await self.ml_collector.update_exit_result(
                    user_id=user_id,
                    symbol=position.symbol,
                    exit_price=actual_exit_price,
                    pnl_percent=pnl_pct,
                    pnl_usdt=pnl,
                    exit_reason=exit_reason_ml
                )
                
                # Log ML stats periodically
                stats = await self.ml_collector.get_training_stats(user_id)
                await self.db.log(user_id, "INFO", 
                    f"[ML] 🧠 Training Data: {stats['completed_trades']} Trades | Win Rate: {stats['win_rate']:.1f}%")
            except Exception as ml_err:
                logger.warning(f"ML exit update error: {ml_err}")
            # === END ML DATA COLLECTION ===
            
            await self.db.log(user_id, "WARNING" if pnl < 0 else "INFO",
                f"[LIVE] ✅ SELL CONFIRMED: {position.symbol} | Exit: ${actual_exit_price:.4f} | PnL: ${pnl:.2f} ({pnl_pct:.1f}%)")
            
            # === TELEGRAM BENACHRICHTIGUNG: Trade geschlossen ===
            # Berechne Duration
            duration_str = "?"
            if hasattr(position, 'entry_time') and position.entry_time:
                duration = datetime.now(timezone.utc) - position.entry_time
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                duration_str = f"{hours}h {minutes}m"
            
            # Bestimme Benachrichtigungstyp
            if "STOP" in reason.upper():
                await self.notify_telegram('stop_loss', {
                    'symbol': position.symbol,
                    'entry_price': position.entry_price,
                    'exit_price': actual_exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                }, user_id)
            elif "PROFIT" in reason.upper() or "TP" in reason.upper():
                await self.notify_telegram('take_profit', {
                    'symbol': position.symbol,
                    'entry_price': position.entry_price,
                    'exit_price': actual_exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                }, user_id)
            elif "SMART" in reason.upper() or "KI" in reason.upper():
                await self.notify_telegram('smart_exit', {
                    'symbol': position.symbol,
                    'exit_type': 'smart_analysis',
                    'confidence': 75,
                    'reasons': [reason]
                }, user_id)
            else:
                await self.notify_telegram('trade_closed', {
                    'symbol': position.symbol,
                    'entry_price': position.entry_price,
                    'exit_price': actual_exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'exit_reason': reason,
                    'duration': duration_str
                }, user_id)
            
            # ============ KI LEARNING: Record Result ============
            try:
                ki_state = await self.ki_engine.get_ki_state(user_id)
                entry_data = {
                    'symbol': position.symbol,
                    'entry_price': position.entry_price,
                    'rsi': 50,  # Will be enhanced later with actual entry data
                    'adx': 20,
                    'volume_24h': 0,
                    'regime': 'UNKNOWN'
                }
                await self.ki_engine.record_trade_result(
                    user_id, position.symbol, entry_data, pnl_pct, was_ki_trade=ki_state.ki_active
                )
                
                if ki_state.ki_active:
                    emoji = "✅" if pnl > 0 else "❌"
                    await self.db.log(user_id, "INFO", 
                        f"[KI] {emoji} Trade-Ergebnis aufgezeichnet | Confidence: {ki_state.ki_confidence*100:.0f}%")
            except Exception as ki_err:
                logger.warning(f"KI learning record error: {ki_err}")
            # ============ END KI LEARNING ============
            
            # Check consecutive losses
            if pnl < 0:
                recent_losses = await self.db.get_recent_symbol_losses(user_id, position.symbol, hours=12)
                if recent_losses >= 3:
                    await self.db.set_symbol_pause(user_id, position.symbol, 24, "3 losses in 12h", recent_losses)
                    
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"[LIVE] ❌ SELL FAILED: {position.symbol} - {str(e)}")
    
    async def close_futures_position(
        self, user_id: str, position: Position, exit_price: float,
        account: PaperAccount, settings: UserSettings, reason: str
    ):
        """Close a FUTURES position"""
        try:
            keys = await self.db.get_mexc_keys(user_id)
            if not keys:
                raise Exception("MEXC API keys nicht konfiguriert")
            
            futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
            
            # Convert symbol format if needed
            futures_symbol = futures_client.convert_spot_symbol_to_futures(position.symbol)
            is_long = position.side == "LONG"
            
            await self.db.log(user_id, "WARNING", 
                f"[FUTURES] ⚡ CLOSING {position.side}: {futures_symbol} | Qty: {position.qty}")
            
            # Close the position
            if is_long:
                result = await futures_client.close_long(futures_symbol, position.qty)
            else:
                result = await futures_client.close_short(futures_symbol, position.qty)
            
            # Calculate PnL
            if is_long:
                pnl = (exit_price - position.entry_price) * position.qty
                pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
            else:
                pnl = (position.entry_price - exit_price) * position.qty
                pnl_pct = ((position.entry_price - exit_price) / position.entry_price) * 100
            
            # Factor in leverage for ROE
            leverage = getattr(position, 'leverage', 1) or 1
            roe = pnl_pct * leverage
            
            # Remove from account
            account.open_positions.remove(position)
            
            # Record trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=position.symbol,
                side="SELL" if is_long else "BUY",
                qty=position.qty,
                entry=position.entry_price,
                exit=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                mode='live',
                reason=f"[FUTURES {leverage}x {position.side}] {reason}",
                notional=position.entry_price * position.qty
            )
            await self.db.add_trade(trade)
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            await self.db.log(user_id, "WARNING" if pnl < 0 else "INFO",
                f"[FUTURES] {emoji} CLOSED: {futures_symbol} {position.side} | Exit: ${exit_price:.4f} | PnL: ${pnl:.2f} | ROE: {roe:.1f}%")
            
        except Exception as e:
            logger.error(f"Futures close error: {e}")
            await self.db.log(user_id, "ERROR", f"[FUTURES] ❌ CLOSE FAILED: {position.symbol} - {str(e)}")
    
    async def open_futures_position(
        self, user_id: str, symbol: str, candidate: dict,
        account: PaperAccount, settings: UserSettings,
        available_budget: float, ai_decision
    ) -> bool:
        """Open a FUTURES position on MEXC"""
        try:
            keys = await self.db.get_mexc_keys(user_id)
            if not keys:
                raise Exception("MEXC API keys nicht konfiguriert")
            
            futures_client = MexcFuturesClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
            
            # Get decision parameters
            direction = ai_decision.direction  # "long" or "short"
            leverage = ai_decision.leverage
            position_size = ai_decision.position_size_usdt
            current_price = candidate['current_price']
            
            # Convert symbol format
            futures_symbol = futures_client.convert_spot_symbol_to_futures(symbol)
            
            # Apply risk reduction for futures
            profile = RISK_PROFILES_V2.get(TradingMode(settings.trading_mode), {})
            risk_reduction = profile.get('futures_risk_reduction', 0.5)
            actual_position = position_size * risk_reduction
            
            # Clamp to available budget
            actual_position = min(actual_position, available_budget * 0.9)
            
            if actual_position < settings.live_min_notional_usdt:
                await self.db.log(user_id, "INFO", 
                    f"[FUTURES] ⚠️ Position ${actual_position:.2f} < Min ${settings.live_min_notional_usdt} → Skip")
                return False
            
            # Calculate quantity in contracts
            quantity = futures_client.calculate_position_size(actual_position, current_price, 1)  # No extra leverage in qty
            
            # Set leverage
            await futures_client.set_leverage(futures_symbol, leverage)
            
            await self.db.log(user_id, "WARNING", 
                f"[FUTURES] ⚡ OPENING {direction.upper()} {leverage}x: {futures_symbol} | Size: ${actual_position:.2f}")
            
            # Open position
            if direction == "long":
                result = await futures_client.open_long(
                    symbol=futures_symbol,
                    quantity=quantity,
                    leverage=leverage,
                    stop_loss_price=ai_decision.stop_loss_price,
                    take_profit_price=ai_decision.take_profit_price
                )
            else:
                result = await futures_client.open_short(
                    symbol=futures_symbol,
                    quantity=quantity,
                    leverage=leverage,
                    stop_loss_price=ai_decision.stop_loss_price,
                    take_profit_price=ai_decision.take_profit_price
                )
            
            # Create position record
            position = Position(
                symbol=symbol,
                side=direction.upper(),
                entry_price=current_price,
                qty=quantity,
                stop_loss=ai_decision.stop_loss_price,
                take_profit=ai_decision.take_profit_price,
                entry_time=datetime.now(timezone.utc),
                market_type="futures",
                leverage=leverage,
                margin_mode="isolated",
                liquidation_price=ai_decision.liquidation_price,
                margin_used=actual_position
            )
            
            # Update account
            if not account:
                account = PaperAccount(user_id=user_id, equity=0, cash=0, open_positions=[])
            
            account.open_positions.append(position)
            await self.db.update_live_account(account)
            
            # Record trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=symbol,
                side="BUY" if direction == "long" else "SELL",
                qty=quantity,
                entry=current_price,
                mode='live',
                reason=f"[FUTURES {leverage}x {direction.upper()}] Score={candidate['score']:.1f}",
                notional=actual_position * leverage
            )
            await self.db.add_trade(trade)
            
            emoji = "📈" if direction == "long" else "📉"
            await self.db.log(user_id, "WARNING",
                f"[FUTURES] {emoji} OPENED: {futures_symbol} {direction.upper()} {leverage}x | Margin: ${actual_position:.2f} | Liq: ${ai_decision.liquidation_price:.4f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Futures open error: {e}")
            await self.db.log(user_id, "ERROR", f"[FUTURES] ❌ OPEN FAILED: {symbol} - {str(e)}")
            return False
                    
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"[LIVE] ❌ SELL FAILED: {position.symbol} - {str(e)}")
    
    def is_in_cooldown(self, user_id: str, cooldown_candles: int) -> bool:
        """Check if user is in cooldown"""
        cooldown_key = f"{user_id}_live"
        if cooldown_key not in self.user_last_trade_time:
            return False
        
        last_trade = self.user_last_trade_time[cooldown_key]
        cooldown_duration = timedelta(minutes=cooldown_candles * 15)
        
        return (datetime.now(timezone.utc) - last_trade) < cooldown_duration
    
    def set_last_trade_time(self, user_id: str):
        """Set last trade time"""
        cooldown_key = f"{user_id}_live"
        self.user_last_trade_time[cooldown_key] = datetime.now(timezone.utc)
    
    async def get_user_mexc_client(self, user_id: str, settings: UserSettings) -> MexcClient:
        """Get MEXC client with user's API keys"""
        if settings.live_confirmed:
            # get_mexc_keys returns already decrypted keys
            keys = await self.db.get_mexc_keys(user_id)
            if keys:
                return MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
        
        return MexcClient()
    
    async def start(self):
        if self.running:
            return
        
        self.running = True
        logger.info("Multi-user trading worker started (LIVE only)")
        logger.info("Exit checks: 30s | Signal scans: 1m | MEXC sync: 90s")
        
        await asyncio.gather(
            self.heartbeat(),
            self.trading_loop(),
            self.exit_check_loop(),
            self.mexc_sync_loop()
        )
    
    async def stop(self):
        self.running = False
        logger.info("Multi-user trading worker stopped")
