import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from db_operations import Database
from mexc_client import MexcClient
from strategy import TradingStrategy
from risk_manager import RiskManager
from regime_detector import RegimeDetector
from models import Position, Trade, UserSettings, PaperAccount

logger = logging.getLogger(__name__)

class MultiUserTradingWorker:
    # Background worker for multi-user automated trading
    
    def __init__(self, db: Database):
        self.db = db
        self.running = False
        self.user_initial_equity: Dict[str, float] = {}  # Track for daily loss limit
        self.user_last_trade_time: Dict[str, datetime] = {}  # Cooldown tracking
        self.regime_detector = RegimeDetector()
    
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
        while self.running:
            try:
                # Get all users with bot_running=true
                active_settings = await self.db.get_all_active_users()
                
                if not active_settings:
                    await asyncio.sleep(900)  # 15 min
                    continue
                
                logger.info(f"Trading cycle for {len(active_settings)} active user(s)")
                
                # Process each user
                for settings_doc in active_settings:
                    user_id = settings_doc.get('user_id')
                    try:
                        await self.process_user(user_id)
                        # Small delay between users to avoid rate limits
                        await asyncio.sleep(2)
                    except Exception as e:
                        await self.db.log(user_id, "ERROR", f"User trading cycle error: {str(e)}")
                        logger.exception(f"Error processing user {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
            
            # Wait 15 minutes
            await asyncio.sleep(900)
    
    async def process_user(self, user_id: str):
        settings = await self.db.get_settings(user_id)
        
        if not settings.bot_running:
            return
        
        await self.db.log(user_id, "INFO", "Starting trading cycle")
        
        # Refresh top pairs daily
        should_refresh = True
        if settings.last_pairs_refresh:
            # Make datetime timezone-aware if it isn't
            last_refresh = settings.last_pairs_refresh
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=timezone.utc)
            should_refresh = (datetime.now(timezone.utc) - last_refresh) > timedelta(hours=24)
        
        if should_refresh:
            await self.refresh_top_pairs(user_id)
            settings = await self.db.get_settings(user_id)  # Reload
        
        if not settings.top_pairs:
            await self.db.log(user_id, "WARNING", "No top pairs available")
            return
        
        # Scan symbols for signals
        await self.scan_and_trade(user_id, settings)
    
    async def refresh_top_pairs(self, user_id: str):
        try:
            await self.db.log(user_id, "INFO", "Refreshing top pairs...")
            
            # Use default MEXC client for public data
            mexc = MexcClient()
            top_pairs = await mexc.get_top_pairs(quote="USDT", limit=20)
            
            await self.db.update_settings(user_id, {
                'top_pairs': top_pairs,
                'last_pairs_refresh': datetime.now(timezone.utc)
            })
            
            await self.db.log(user_id, "INFO", f"Top pairs updated: {len(top_pairs)} symbols", 
                            {'pairs': top_pairs[:5]})
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"Failed to refresh top pairs: {str(e)}")
    
    async def scan_and_trade(self, user_id: str, settings: UserSettings):
        account = await self.db.get_paper_account(user_id)
        
        # Initialize tracking
        if user_id not in self.user_initial_equity:
            self.user_initial_equity[user_id] = account.equity
        
        strategy = TradingStrategy(
            ema_fast=settings.ema_fast,
            ema_slow=settings.ema_slow,
            rsi_period=settings.rsi_period,
            rsi_min=settings.rsi_min,
            rsi_overbought=settings.rsi_overbought
        )
        risk_mgr = RiskManager(settings)
        
        # Get MEXC client with user keys if live mode
        mexc = await self.get_user_mexc_client(user_id, settings)
        
        # Check daily loss limit
        if risk_mgr.check_daily_loss_limit(account, self.user_initial_equity[user_id]):
            await self.db.log(user_id, "ERROR", "Daily loss limit hit - stopping bot")
            await self.db.update_settings(user_id, {'bot_running': False})
            return
        
        # Check existing positions for exits
        for pos in account.open_positions[:]:
            await self.check_position_exit(user_id, pos, account, settings, mexc)
        
        # Check cooldown
        if self.is_in_cooldown(user_id, 5):  # Fixed 5 candles cooldown
            await self.db.log(user_id, "DEBUG", "In cooldown period (5 candles), skipping new entries")
            return
        
        # Look for new entries with REGIME DETECTION
        if risk_mgr.can_open_position(account):
            for symbol in settings.top_pairs[:10]:  # Check top 10
                try:
                    # Check if symbol is paused (3 losses in 12h)
                    if await self.db.is_symbol_paused(user_id, symbol):
                        await self.db.log(user_id, "WARNING", f"{symbol} paused due to consecutive losses")
                        continue
                    
                    # Get 4H klines for regime detection (MUST HAPPEN FIRST)
                    klines_4h = await mexc.get_klines(symbol, interval="4h", limit=250)
                    
                    if len(klines_4h) < 200:
                        await self.db.log(user_id, "DEBUG", f"{symbol} insufficient 4H data for regime detection")
                        continue
                    
                    # DETECT REGIME
                    regime, regime_context = self.regime_detector.detect_regime(klines_4h)
                    
                    # Log detected regime for every symbol
                    await self.db.log(user_id, "INFO", f"{symbol} Regime: {regime}", regime_context)
                    
                    # REGIME-BASED FILTERING (BEFORE SIGNAL CHECK)
                    
                    # BEARISH: No long trades
                    if regime == "BEARISH":
                        await self.db.log(user_id, "INFO", f"{symbol} blocked - BEARISH regime (no long trades)")
                        continue
                    
                    # SIDEWAYS: No EMA crossover trading
                    if regime == "SIDEWAYS":
                        await self.db.log(user_id, "INFO", f"{symbol} blocked - SIDEWAYS regime (no EMA trading)")
                        continue
                    
                    # BULLISH: Proceed with entry check
                    if regime != "BULLISH":
                        await self.db.log(user_id, "INFO", f"{symbol} blocked - Regime {regime} not BULLISH")
                        continue
                    
                    # Get 15m klines for entry signal
                    klines_15m = await mexc.get_klines(symbol, interval="15m", limit=500)
                    
                    if len(klines_15m) < settings.ema_slow:
                        continue
                    
                    # Check EMA signal
                    signal, context = strategy.generate_signal(klines_15m)
                    
                    if signal == "LONG":
                        # BULLISH REGIME: Adjusted parameters
                        current_price = float(klines_15m[-1][4])
                        
                        # Calculate ATR stop (mult 2.5)
                        atr = strategy.calculate_atr(klines_15m, 14)
                        if atr:
                            stop_loss = current_price - (atr * 2.5)
                            # TP = 1:2.5 R:R
                            risk_amount = current_price - stop_loss
                            take_profit = current_price + (risk_amount * 2.5)
                        else:
                            # Fallback
                            stop_loss = risk_mgr.calculate_stop_loss(current_price, None)
                            take_profit = risk_mgr.calculate_take_profit(current_price, stop_loss)
                        
                        # Reduce risk to 0.5% for bullish regime
                        original_risk = settings.risk_per_trade
                        settings.risk_per_trade = 0.005  # 0.5%
                        
                        # Open position with regime-adjusted parameters
                        await self.open_position_with_regime(
                            user_id, symbol, klines_15m, account, settings,
                            strategy, risk_mgr, context, mexc, regime,
                            stop_loss, take_profit
                        )
                        
                        # Restore original risk
                        settings.risk_per_trade = original_risk
                        
                        # Update last trade time and break
                        self.user_last_trade_time[user_id] = datetime.now(timezone.utc)
                        break  # One entry per cycle
                    
                except Exception as e:
                    await self.db.log(user_id, "ERROR", f"Error scanning {symbol}: {str(e)}")
        
        # Save updated account
        await self.db.update_paper_account(account)
    
    def is_in_cooldown(self, user_id: str, cooldown_candles: int) -> bool:
        if user_id not in self.user_last_trade_time:
            return False
        
        last_trade = self.user_last_trade_time[user_id]
        cooldown_minutes = cooldown_candles * 15  # 15m candles
        cooldown_duration = timedelta(minutes=cooldown_minutes)
        
        return (datetime.now(timezone.utc) - last_trade) < cooldown_duration
    
    async def get_user_mexc_client(self, user_id: str, settings: UserSettings) -> MexcClient:
        if settings.mode == 'live' and settings.live_confirmed:
            keys = await self.db.get_mexc_keys(user_id)
            if keys:
                return MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
            else:
                await self.db.log(user_id, "WARNING", "Live mode but no API keys found")
        
        # Return default client for paper mode or if no keys
        return MexcClient()
    
    async def open_position(
        self,
        user_id: str,
        symbol: str,
        klines: list,
        account: PaperAccount,
        settings: UserSettings,
        strategy: TradingStrategy,
        risk_mgr: RiskManager,
        context: dict,
        mexc: MexcClient
    ):
        try:
            current_price = float(klines[-1][4])  # Close price
            
            # Calculate ATR if enabled
            atr = None
            if settings.atr_stop:
                atr = strategy.calculate_atr(klines)
            
            # Calculate stop loss and take profit
            stop_loss = risk_mgr.calculate_stop_loss(current_price, atr)
            take_profit = risk_mgr.calculate_take_profit(current_price, stop_loss)
            
            # Calculate position size
            qty, reason = risk_mgr.calculate_position_size(account, current_price, stop_loss)
            
            if qty == 0:
                await self.db.log(user_id, "WARNING", f"Cannot size position for {symbol}: {reason}")
                return
            
            # Apply fees and slippage
            entry_price = risk_mgr.apply_fees_and_slippage(current_price, "BUY")
            
            # Create position
            position = Position(
                symbol=symbol,
                side="LONG",
                entry_price=entry_price,
                qty=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=datetime.now(timezone.utc)
            )
            
            # Update account
            position_value = qty * entry_price
            account.cash -= position_value
            account.open_positions.append(position)
            
            # Log trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=symbol,
                side="BUY",
                qty=qty,
                entry=entry_price,
                mode=settings.mode,
                reason=f"EMA crossover, RSI={context.get('rsi', 0)}"
            )
            await self.db.add_trade(trade)
            
            await self.db.log(
                user_id,
                "INFO",
                f"OPEN LONG {symbol} @ {entry_price:.4f}",
                {
                    'qty': round(qty, 4),
                    'stop_loss': round(stop_loss, 4),
                    'take_profit': round(take_profit, 4),
                    'position_value': round(position_value, 2),
                    **context
                }
            )
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"Failed to open position {symbol}: {str(e)}")
    
    async def open_position_with_regime(
        self,
        user_id: str,
        symbol: str,
        klines: list,
        account: PaperAccount,
        settings: UserSettings,
        strategy: TradingStrategy,
        risk_mgr: RiskManager,
        context: dict,
        mexc: MexcClient,
        regime: str,
        stop_loss: float,
        take_profit: float
    ):
        try:
            current_price = float(klines[-1][4])
            
            # Calculate position size with adjusted risk (0.5% for bullish)
            qty, reason = risk_mgr.calculate_position_size(account, current_price, stop_loss)
            
            if qty == 0:
                await self.db.log(user_id, "WARNING", f"Cannot size position for {symbol}: {reason}")
                return
            
            # Apply fees and slippage
            entry_price = risk_mgr.apply_fees_and_slippage(current_price, "BUY")
            
            # Create position
            position = Position(
                symbol=symbol,
                side="LONG",
                entry_price=entry_price,
                qty=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=datetime.now(timezone.utc)
            )
            
            # Update account
            position_value = qty * entry_price
            account.cash -= position_value
            account.open_positions.append(position)
            
            # Log trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=symbol,
                side="BUY",
                qty=qty,
                entry=entry_price,
                mode=settings.mode,
                reason=f"Regime: {regime}, EMA crossover, RSI={context.get('rsi', 0)}"
            )
            await self.db.add_trade(trade)
            
            # AUDIT LOG for trade execution
            await self.db.audit_log(
                user_id=user_id,
                action="TRADE_EXECUTED",
                details={
                    'symbol': symbol,
                    'side': 'BUY',
                    'qty': round(qty, 4),
                    'entry_price': round(entry_price, 4),
                    'stop_loss': round(stop_loss, 4),
                    'take_profit': round(take_profit, 4),
                    'regime': regime,
                    'risk_pct': settings.risk_per_trade * 100,
                    'mode': settings.mode
                }
            )
            
            await self.db.log(
                user_id,
                "INFO",
                f"OPEN LONG {symbol} @ {entry_price:.4f} [Regime: {regime}]",
                {
                    'qty': round(qty, 4),
                    'stop_loss': round(stop_loss, 4),
                    'take_profit': round(take_profit, 4),
                    'position_value': round(position_value, 2),
                    'regime': regime,
                    'risk_pct': settings.risk_per_trade * 100,
                    **context
                }
            )
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"Failed to open position {symbol}: {str(e)}")
    
    async def check_position_exit(
        self,
        user_id: str,
        position: Position,
        account: PaperAccount,
        settings: UserSettings,
        mexc: MexcClient
    ):
        try:
            # Get current price
            ticker = await mexc.get_ticker_24h(position.symbol)
            current_price = float(ticker['lastPrice'])
            
            should_exit = False
            exit_reason = ""
            
            # Check stop loss
            if current_price <= position.stop_loss:
                should_exit = True
                exit_reason = "Stop loss hit"
            
            # Check take profit
            elif current_price >= position.take_profit:
                should_exit = True
                exit_reason = "Take profit hit"
            
            if should_exit:
                await self.close_position(user_id, position, current_price, account, settings, exit_reason)
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"Error checking position {position.symbol}: {str(e)}")
    
    async def close_position(
        self,
        user_id: str,
        position: Position,
        exit_price: float,
        account: PaperAccount,
        settings: UserSettings,
        reason: str
    ):
        try:
            risk_mgr = RiskManager(settings)
            
            # Apply fees and slippage
            exit_price = risk_mgr.apply_fees_and_slippage(exit_price, "SELL")
            
            # Calculate PnL
            pnl = (exit_price - position.entry_price) * position.qty
            pnl_pct = (pnl / (position.entry_price * position.qty)) * 100
            
            # Update account
            cash_returned = position.qty * exit_price
            account.cash += cash_returned
            account.equity = account.cash + sum(
                p.qty * exit_price for p in account.open_positions if p.symbol != position.symbol
            )
            
            # Remove position
            account.open_positions = [
                p for p in account.open_positions if p.symbol != position.symbol
            ]
            
            # Log trade
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=position.symbol,
                side="SELL",
                qty=position.qty,
                entry=position.entry_price,
                exit=exit_price,
                pnl=pnl,
                mode=settings.mode,
                reason=reason
            )
            await self.db.add_trade(trade)
            
            await self.db.log(
                user_id,
                "INFO" if pnl > 0 else "WARNING",
                f"CLOSE {position.symbol} @ {exit_price:.4f}",
                {
                    'entry': round(position.entry_price, 4),
                    'pnl': round(pnl, 2),
                    'pnl_pct': round(pnl_pct, 2),
                    'reason': reason
                }
            )
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"Failed to close position {position.symbol}: {str(e)}")
    
    async def start(self):
        if self.running:
            return
        
        self.running = True
        logger.info("Multi-user trading worker started")
        
        # Start both tasks
        await asyncio.gather(
            self.heartbeat(),
            self.trading_loop()
        )
    
    async def stop(self):
        self.running = False
        logger.info("Multi-user trading worker stopped")
