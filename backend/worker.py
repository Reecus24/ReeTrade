import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from db_operations import Database
from mexc_client import MexcClient
from strategy import TradingStrategy
from risk_manager import RiskManager
from regime_detector import RegimeDetector
from order_sizer import order_sizer
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
        self.exchange_info_loaded = False
    
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
        """
        Calculate budget info for LIVE mode with reserve system.
        
        Reserve System Logic:
        1. reserve_usdt: Safety reserve - bot won't touch this
        2. available_to_bot = max(0, usdt_free - reserve_usdt)
        3. trading_budget_usdt: Absolute cap on total exposure
        4. remaining_budget = min(available_to_bot, trading_budget - used_budget)
        """
        # Step 1: Calculate what's available after reserve
        available_to_bot = max(0, usdt_free - settings.reserve_usdt)
        
        # Step 2: Apply trading budget cap
        budget_remaining = max(0, settings.trading_budget_usdt - used_budget)
        
        # Step 3: Final remaining is the minimum of both constraints
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
    
    def calculate_paper_budget(
        self, 
        settings: UserSettings, 
        used_budget: float,
        paper_cash: float
    ) -> dict:
        """Calculate budget info for PAPER mode."""
        # Paper mode: limited by paper_start_balance
        budget_remaining = max(0, settings.paper_start_balance_usdt - used_budget)
        available_to_bot = min(paper_cash, budget_remaining)
        
        return {
            'paper_cash': paper_cash,
            'start_balance': settings.paper_start_balance_usdt,
            'trading_budget': settings.paper_start_balance_usdt,
            'used_budget': used_budget,
            'remaining_budget': available_to_bot,
            'max_order_notional': settings.max_order_notional_usdt
        }
    
    def calculate_effective_balance(
        self, 
        settings: UserSettings, 
        account: PaperAccount,
        live_usdt_free: float = None
    ) -> tuple[float, float, float]:
        """
        Calculate effective balance for trading.
        Returns: (effective_balance, used_budget, available_budget)
        """
        used_budget = self.calculate_used_budget(account)
        
        if settings.mode == 'live' and live_usdt_free is not None:
            # Live mode with reserve system
            budget_info = self.calculate_live_budget(settings, used_budget, live_usdt_free)
            effective = budget_info['remaining_budget']
        else:
            # Paper mode
            budget_info = self.calculate_paper_budget(settings, used_budget, account.cash)
            effective = budget_info['remaining_budget']
        
        return effective, used_budget, budget_info.get('trading_budget', settings.trading_budget_usdt)
    
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
                    await asyncio.sleep(300)  # 5 min
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
            
            # Wait 5 minutes
            await asyncio.sleep(300)
    
    async def process_user(self, user_id: str):
        settings = await self.db.get_settings(user_id)
        
        # Check if either mode is running
        paper_running = settings.paper_running
        live_running = settings.live_running and settings.live_confirmed
        
        if not paper_running and not live_running:
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
        
        # Refresh top pairs every 4 hours (momentum rotation)
        should_refresh = True
        if settings.last_pairs_refresh:
            last_refresh = settings.last_pairs_refresh
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=timezone.utc)
            should_refresh = (datetime.now(timezone.utc) - last_refresh) > timedelta(hours=4)
        
        if should_refresh:
            await self.refresh_top_pairs(user_id)
            settings = await self.db.get_settings(user_id)  # Reload
        
        if not settings.top_pairs:
            await self.db.log(user_id, "WARNING", "No top pairs available")
            return
        
        # Process PAPER mode
        if paper_running:
            await self.db.log(user_id, "INFO", "[PAPER] Starting trading cycle")
            await self.scan_and_trade_mode(user_id, settings, mode='paper')
            await self.db.update_settings(user_id, {'paper_heartbeat': datetime.now(timezone.utc)})
        
        # Process LIVE mode (completely separate)
        if live_running:
            await self.db.log(user_id, "WARNING", "[LIVE] Starting trading cycle")
            await self.scan_and_trade_mode(user_id, settings, mode='live')
            await self.db.update_settings(user_id, {'live_heartbeat': datetime.now(timezone.utc)})
    
    async def refresh_top_pairs(self, user_id: str):
        # MOMENTUM ROTATION: Select Top 10 by momentum score
        try:
            await self.db.log(user_id, "INFO", "Running Momentum Rotation...")
            
            mexc = MexcClient()
            
            # Get momentum-scored universe (Top 50 by volume)
            momentum_pairs = await mexc.get_momentum_universe(quote="USDT", base_limit=50)
            
            # Filter: Only BULLISH regime
            filtered_pairs = []
            for pair_data in momentum_pairs[:20]:  # Check top 20 momentum
                symbol = pair_data['symbol']
                
                try:
                    # Get 4H candles for regime
                    klines_4h = await mexc.get_klines(symbol, interval="4h", limit=250)
                    
                    if len(klines_4h) >= 200:
                        regime, regime_ctx = self.regime_detector.detect_regime(klines_4h)
                        
                        # Only include BULLISH symbols
                        if regime == "BULLISH":
                            filtered_pairs.append({
                                **pair_data,
                                'regime': regime,
                                'adx': regime_ctx.get('adx', 0)
                            })
                            
                            if len(filtered_pairs) >= 10:
                                break
                except Exception as e:
                    logger.warning(f"Error checking regime for {symbol}: {e}")
                    continue
            
            # Extract symbols
            tradable_symbols = [p['symbol'] for p in filtered_pairs]
            
            await self.db.update_settings(user_id, {
                'top_pairs': tradable_symbols,
                'last_pairs_refresh': datetime.now(timezone.utc)
            })
            
            await self.db.log(
                user_id, 
                "INFO", 
                f"Momentum Rotation complete: {len(tradable_symbols)} BULLISH symbols selected",
                {
                    'symbols': tradable_symbols[:5],
                    'scores': [f"{p['symbol']}={p['score']:.2f}" for p in filtered_pairs[:5]]
                }
            )
            
        except Exception as e:
            await self.db.log(user_id, "ERROR", f"Failed to run momentum rotation: {str(e)}")
    
    async def scan_and_trade_mode(self, user_id: str, settings: UserSettings, mode: str):
        """Scan and trade for a specific mode (paper or live)"""
        # Create a modified settings object with the correct mode
        mode_settings = settings.model_copy()
        mode_settings.mode = mode
        
        await self.scan_and_trade(user_id, mode_settings)
    
    async def scan_and_trade(self, user_id: str, settings: UserSettings):
        account = await self.db.get_paper_account(user_id)
        mode_prefix = f"[{settings.mode.upper()}]"
        scan_time = datetime.now(timezone.utc)
        
        # Initialize paper account with user's budget setting if needed
        if account.equity == 10000.0 and settings.paper_start_balance_usdt != 10000.0:
            account.equity = settings.paper_start_balance_usdt
            account.cash = settings.paper_start_balance_usdt
            await self.db.update_paper_account(account)
            await self.db.log(user_id, "INFO", f"{mode_prefix} Paper account initialized with budget: ${settings.paper_start_balance_usdt}")
        
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
        
        # Get live USDT balance if in live mode
        live_usdt_free = None
        if settings.mode == 'live' and settings.live_confirmed:
            try:
                account_info = await mexc.get_account()
                balances = account_info.get('balances', [])
                usdt_balance = next((b for b in balances if b.get('asset') == 'USDT'), None)
                if usdt_balance:
                    live_usdt_free = float(usdt_balance.get('free', 0))
            except Exception as e:
                await self.db.log(user_id, "ERROR", f"{mode_prefix} Failed to fetch MEXC balance: {e}")
                return
        
        # Calculate budget info
        available_budget, used_budget, total_budget = self.calculate_effective_balance(
            settings, account, live_usdt_free
        )
        
        # DAILY CAP CHECK
        today_exposure = await self.db.get_today_exposure(user_id, settings.mode)
        daily_cap = settings.live_daily_cap_usdt if settings.mode == 'live' else settings.paper_daily_cap_usdt
        daily_remaining = max(0, daily_cap - today_exposure)
        
        # Update last scan status in settings
        scan_status = {
            f'{settings.mode}_last_scan': scan_time.isoformat(),
            f'{settings.mode}_last_decision': 'SCANNING',
            f'{settings.mode}_budget_used': round(used_budget, 2),
            f'{settings.mode}_budget_available': round(available_budget, 2),
            f'{settings.mode}_daily_used': round(today_exposure, 2),
            f'{settings.mode}_daily_remaining': round(daily_remaining, 2),
            f'{settings.mode}_positions_count': len(account.open_positions)
        }
        await self.db.update_settings(user_id, scan_status)
        
        # Log scan start with full budget info
        await self.db.log(user_id, "INFO", 
            f"{mode_prefix} ═══ SCAN START ═══ Budget: ${available_budget:.2f} avail | Daily: ${today_exposure:.2f}/${daily_cap:.2f} | Positions: {len(account.open_positions)}/{settings.max_positions}")
        
        # Check daily loss limit
        if risk_mgr.check_daily_loss_limit(account, self.user_initial_equity[user_id]):
            await self.db.log(user_id, "ERROR", f"{mode_prefix} ⛔ BLOCKED: Daily loss limit hit - stopping bot")
            await self.db.update_settings(user_id, {
                f'{settings.mode}_last_decision': 'BLOCKED: Daily loss limit',
                'live_running' if settings.mode == 'live' else 'paper_running': False
            })
            return
        
        # Check existing positions for exits using LIVE market data
        for pos in account.open_positions[:]:
            await self.check_position_exit(user_id, pos, account, settings, mexc)
        
        # Check cooldown - MODE SPECIFIC
        cooldown_active = self.is_in_cooldown(user_id, settings.mode, settings.cooldown_candles)
        if cooldown_active:
            cooldown_mins = settings.cooldown_candles * 15
            await self.db.log(user_id, "INFO", f"{mode_prefix} ⏸️ SKIPPED: Cooldown active ({cooldown_mins} Min nach letztem Trade)")
            await self.db.update_settings(user_id, {
                f'{settings.mode}_last_decision': f'SKIPPED: Cooldown ({cooldown_mins} Min)',
                f'{settings.mode}_last_symbol': 'Warte auf Cooldown-Ende'
            })
            return
        
        # Get min_notional based on mode
        min_notional = settings.live_min_notional_usdt if settings.mode == 'live' else settings.min_notional_usdt
        
        # Check if we have budget for new positions
        if available_budget < min_notional:
            await self.db.log(user_id, "INFO", f"{mode_prefix} ⛔ BLOCKED: Kein Budget (${available_budget:.2f} < ${min_notional})")
            await self.db.update_settings(user_id, {
                f'{settings.mode}_last_decision': f'BLOCKED: Budget zu niedrig (${available_budget:.2f})',
                f'{settings.mode}_last_symbol': '-'
            })
            return
        
        # Check DAILY CAP
        if daily_remaining < min_notional:
            await self.db.log(user_id, "INFO", f"{mode_prefix} ⛔ BLOCKED: Tageslimit erreicht (${today_exposure:.2f}/${daily_cap:.2f})")
            await self.db.update_settings(user_id, {
                f'{settings.mode}_last_decision': f'BLOCKED: Tageslimit (${today_exposure:.0f}/${daily_cap:.0f})',
                f'{settings.mode}_last_symbol': '-'
            })
            return
        
        # Check max positions
        if not risk_mgr.can_open_position(account):
            await self.db.log(user_id, "INFO", f"{mode_prefix} ⛔ BLOCKED: Max Positionen erreicht ({len(account.open_positions)}/{settings.max_positions})")
            await self.db.update_settings(user_id, {
                f'{settings.mode}_last_decision': f'BLOCKED: Max Positionen ({len(account.open_positions)}/{settings.max_positions})',
                f'{settings.mode}_last_symbol': '-'
            })
            return
        
        # Look for new entries with REGIME DETECTION
        symbols_checked = 0
        for symbol in settings.top_pairs[:10]:  # Check top 10
            symbols_checked += 1
            try:
                # Check if symbol is paused (3 losses in 12h)
                is_paused = await self.db.is_symbol_paused(user_id, symbol)
                if is_paused:
                    await self.log_symbol_check(
                        user_id, mode_prefix, symbol,
                        regime="N/A", adx=0, ema_fast=0, ema_slow=0, rsi=0,
                        cooldown=False, paused=True,
                        daily_used=today_exposure, daily_cap=daily_cap,
                        budget_available=available_budget,
                        decision="SKIPPED", reason="Symbol paused (consecutive losses)"
                    )
                    continue
                
                # Get 4H klines for regime detection (MUST HAPPEN FIRST)
                klines_4h = await mexc.get_klines(symbol, interval="4h", limit=250)
                
                if len(klines_4h) < 200:
                    await self.log_symbol_check(
                        user_id, mode_prefix, symbol,
                        regime="N/A", adx=0, ema_fast=0, ema_slow=0, rsi=0,
                        cooldown=False, paused=False,
                        daily_used=today_exposure, daily_cap=daily_cap,
                        budget_available=available_budget,
                        decision="SKIPPED", reason="Insufficient 4H data for regime detection"
                    )
                    continue
                
                # DETECT REGIME
                regime, regime_context = self.regime_detector.detect_regime(klines_4h)
                adx_value = regime_context.get('adx', 0)
                
                # REGIME-BASED FILTERING (BEFORE SIGNAL CHECK)
                
                # BEARISH: No long trades
                if regime == "BEARISH":
                    await self.log_symbol_check(
                        user_id, mode_prefix, symbol,
                        regime=regime, adx=adx_value, ema_fast=0, ema_slow=0, rsi=0,
                        cooldown=False, paused=False,
                        daily_used=today_exposure, daily_cap=daily_cap,
                        budget_available=available_budget,
                        decision="SKIPPED", reason="BEARISH regime - no long trades"
                    )
                    continue
                
                # SIDEWAYS: No EMA crossover trading
                if regime == "SIDEWAYS":
                    await self.log_symbol_check(
                        user_id, mode_prefix, symbol,
                        regime=regime, adx=adx_value, ema_fast=0, ema_slow=0, rsi=0,
                        cooldown=False, paused=False,
                        daily_used=today_exposure, daily_cap=daily_cap,
                        budget_available=available_budget,
                        decision="SKIPPED", reason="SIDEWAYS regime - no EMA trading"
                    )
                    continue
                
                # BULLISH: Proceed with entry check
                if regime != "BULLISH":
                    await self.log_symbol_check(
                        user_id, mode_prefix, symbol,
                        regime=regime, adx=adx_value, ema_fast=0, ema_slow=0, rsi=0,
                        cooldown=False, paused=False,
                        daily_used=today_exposure, daily_cap=daily_cap,
                        budget_available=available_budget,
                        decision="SKIPPED", reason=f"Regime {regime} not BULLISH"
                    )
                    continue
                
                # Get 15m klines for entry signal
                klines_15m = await mexc.get_klines(symbol, interval="15m", limit=500)
                
                if len(klines_15m) < settings.ema_slow:
                    await self.log_symbol_check(
                        user_id, mode_prefix, symbol,
                        regime=regime, adx=adx_value, ema_fast=0, ema_slow=0, rsi=0,
                        cooldown=False, paused=False,
                        daily_used=today_exposure, daily_cap=daily_cap,
                        budget_available=available_budget,
                        decision="SKIPPED", reason="Insufficient 15m data for EMA"
                    )
                    continue
                
                # Check EMA signal
                signal, context = strategy.generate_signal(klines_15m)
                ema_fast_val = context.get('ema_fast', 0)
                ema_slow_val = context.get('ema_slow', 0)
                rsi_val = context.get('rsi', 0)
                
                if signal != "LONG":
                    # Determine specific reason
                    if ema_fast_val <= ema_slow_val:
                        skip_reason = f"No EMA crossover (Fast {ema_fast_val:.2f} <= Slow {ema_slow_val:.2f})"
                    elif rsi_val < settings.rsi_min:
                        skip_reason = f"RSI below threshold ({rsi_val:.1f} < {settings.rsi_min})"
                    elif rsi_val > settings.rsi_overbought:
                        skip_reason = f"RSI overbought ({rsi_val:.1f} > {settings.rsi_overbought})"
                    else:
                        skip_reason = f"No LONG signal (Signal: {signal})"
                    
                    await self.log_symbol_check(
                        user_id, mode_prefix, symbol,
                        regime=regime, adx=adx_value, 
                        ema_fast=ema_fast_val, ema_slow=ema_slow_val, rsi=rsi_val,
                        cooldown=False, paused=False,
                        daily_used=today_exposure, daily_cap=daily_cap,
                        budget_available=available_budget,
                        decision="SKIPPED", reason=skip_reason
                    )
                    continue
                
                # SIGNAL DETECTED!
                await self.log_symbol_check(
                    user_id, mode_prefix, symbol,
                    regime=regime, adx=adx_value,
                    ema_fast=ema_fast_val, ema_slow=ema_slow_val, rsi=rsi_val,
                    cooldown=False, paused=False,
                    daily_used=today_exposure, daily_cap=daily_cap,
                    budget_available=available_budget,
                    decision="SIGNAL", reason="LONG signal detected - opening position"
                )
                
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
                
                # Open position with regime-adjusted parameters and budget limit
                await self.open_position_with_budget(
                    user_id, symbol, klines_15m, account, settings,
                    strategy, risk_mgr, context, mexc, regime,
                    stop_loss, take_profit, available_budget
                )
                
                # Restore original risk
                settings.risk_per_trade = original_risk
                
                # Update last trade time (MODE SPECIFIC) and decision
                self.set_last_trade_time(user_id, settings.mode)
                await self.db.update_settings(user_id, {
                    f'{settings.mode}_last_decision': f'TRADE: {symbol}',
                    f'{settings.mode}_last_regime': regime,
                    f'{settings.mode}_last_symbol': symbol
                })
                break  # One entry per cycle
                
            except Exception as e:
                await self.db.log(user_id, "ERROR", f"{mode_prefix} Error scanning {symbol}: {str(e)}")
        
        # Log scan completion
        if symbols_checked > 0:
            await self.db.log(user_id, "INFO", f"{mode_prefix} ═══ SCAN COMPLETE ═══ Checked {symbols_checked} symbols")
        
        # Save updated account
        await self.db.update_paper_account(account)
    
    async def log_symbol_check(
        self, user_id: str, mode_prefix: str, symbol: str,
        regime: str, adx: float, ema_fast: float, ema_slow: float, rsi: float,
        cooldown: bool, paused: bool,
        daily_used: float, daily_cap: float, budget_available: float,
        decision: str, reason: str
    ):
        """Log detailed symbol check for transparency"""
        log_msg = f"""
{mode_prefix} ══ SYMBOL CHECK ══
Symbol: {symbol}
Regime: {regime} | ADX: {adx:.1f}
EMA Fast: {ema_fast:.2f} | EMA Slow: {ema_slow:.2f}
RSI: {rsi:.1f}
Cooldown: {cooldown} | Paused: {paused}
Daily: ${daily_used:.2f} / ${daily_cap:.2f}
Budget: ${budget_available:.2f}
Decision: {decision}
Reason: {reason}
══════════════════"""
        
        # Use INFO for signals, DEBUG for skips
        level = "INFO" if decision == "SIGNAL" else "DEBUG"
        await self.db.log(user_id, level, log_msg.strip(), {
            'symbol': symbol,
            'regime': regime,
            'adx': round(adx, 2),
            'ema_fast': round(ema_fast, 4),
            'ema_slow': round(ema_slow, 4),
            'rsi': round(rsi, 2),
            'decision': decision,
            'reason': reason
        })
    
    def is_in_cooldown(self, user_id: str, mode: str, cooldown_candles: int) -> bool:
        """Check if user is in cooldown - MODE SPECIFIC"""
        cooldown_key = f"{user_id}_{mode}"
        if cooldown_key not in self.user_last_trade_time:
            return False
        
        last_trade = self.user_last_trade_time[cooldown_key]
        cooldown_minutes = cooldown_candles * 15  # 15m candles
        cooldown_duration = timedelta(minutes=cooldown_minutes)
        
        return (datetime.now(timezone.utc) - last_trade) < cooldown_duration
    
    def set_last_trade_time(self, user_id: str, mode: str):
        """Set last trade time - MODE SPECIFIC"""
        cooldown_key = f"{user_id}_{mode}"
        self.user_last_trade_time[cooldown_key] = datetime.now(timezone.utc)
    
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
        # Deprecated - use open_position_with_budget instead
        await self.open_position_with_budget(
            user_id, symbol, klines, account, settings,
            strategy, risk_mgr, context, mexc, regime,
            stop_loss, take_profit, available_budget=settings.trading_budget_usdt
        )
    
    async def open_position_with_budget(
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
        take_profit: float,
        available_budget: float
    ):
        """Open position with budget limit enforcement"""
        try:
            current_price = float(klines[-1][4])
            
            # Calculate position size with adjusted risk (0.5% for bullish)
            qty, reason = risk_mgr.calculate_position_size(account, current_price, stop_loss)
            
            if qty == 0:
                await self.db.log(user_id, "WARNING", f"Cannot size position for {symbol}: {reason}")
                return
            
            # Calculate notional value
            notional = qty * current_price
            
            # BUDGET LIMIT CHECK 1: Max order notional
            if settings.max_order_notional_usdt and notional > settings.max_order_notional_usdt:
                # Reduce position to max order size
                qty = settings.max_order_notional_usdt / current_price
                notional = qty * current_price
                await self.db.log(user_id, "INFO", f"{symbol} position reduced to max order size: ${notional:.2f}")
            
            # BUDGET LIMIT CHECK 2: Available budget
            if notional > available_budget:
                # Reduce position to available budget
                qty = available_budget / current_price
                notional = qty * current_price
                await self.db.log(user_id, "INFO", f"{symbol} position reduced to available budget: ${notional:.2f}")
            
            # Check if position is still viable
            min_notional = settings.live_min_notional_usdt if settings.mode == 'live' else settings.min_notional_usdt
            if notional < min_notional:
                await self.db.log(user_id, "WARNING", f"{symbol} position too small after budget limits: ${notional:.2f} < min ${min_notional}")
                return
            
            # Round quantity to exchange stepSize
            rounded_qty = order_sizer.round_quantity(symbol, qty)
            
            if rounded_qty == 0:
                await self.db.log(user_id, "WARNING", f"{symbol} qty {qty:.6f} below exchange minimum after rounding")
                return
            
            # Recalculate notional with rounded qty
            notional = rounded_qty * current_price
            
            # Validate notional value
            valid, notional_reason = order_sizer.validate_notional(
                symbol, 
                rounded_qty, 
                current_price, 
                user_min_notional=settings.min_notional_usdt
            )
            
            if not valid:
                await self.db.log(
                    user_id, 
                    "INFO", 
                    f"{symbol} skipped - {notional_reason}",
                    {
                        'qty': round(rounded_qty, 6),
                        'price': round(current_price, 4),
                        'notional': round(notional, 2),
                        'min_notional': settings.min_notional_usdt
                    }
                )
                return
            
            # Calculate fees and slippage costs
            mode_prefix = f"[{settings.mode.upper()}]"
            fee_rate = settings.fee_bps / 10000
            slippage_rate = settings.slippage_bps / 10000
            
            entry_fee = notional * fee_rate
            slippage_cost = notional * slippage_rate
            
            # Apply fees and slippage to entry price
            entry_price = risk_mgr.apply_fees_and_slippage(current_price, "BUY")
            
            # LOG: TRADE OPENED (BEFORE execution)
            trade_opened_log = f"""
{mode_prefix} ══ TRADE OPENED ══
Symbol: {symbol}
Qty: {rounded_qty:.6f}
Entry: {entry_price:.4f}
Notional: {notional:.2f} USDT
ATR Stop: {stop_loss:.4f}
Take Profit: {take_profit:.4f}
Risk: {settings.risk_per_trade * 100:.1f}%
Mode: {settings.mode.upper()}
══════════════════"""
            await self.db.log(user_id, "INFO", trade_opened_log.strip())
            
            # Create position with rounded qty
            position = Position(
                symbol=symbol,
                side="LONG",
                entry_price=entry_price,
                qty=rounded_qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=datetime.now(timezone.utc)
            )
            
            # Update account
            position_value = rounded_qty * entry_price
            account.cash -= position_value
            account.open_positions.append(position)
            
            # Log trade with enhanced info
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=symbol,
                side="BUY",
                qty=rounded_qty,
                entry=entry_price,
                mode=settings.mode,
                reason=f"Regime: {regime}, EMA crossover, RSI={context.get('rsi', 0)}",
                notional=notional,
                fees_paid=entry_fee,
                slippage_cost=slippage_cost
            )
            await self.db.add_trade(trade)
            
            # LOG: ORDER CONFIRMED
            order_confirmed_log = f"""
{mode_prefix} ══ ORDER CONFIRMED ══
Exchange: {'MEXC (SIMULATED)' if settings.mode == 'paper' else 'MEXC'}
Status: FILLED
Executed Price: {entry_price:.4f}
Fee: {entry_fee:.4f} USDT
Slippage: {slippage_cost:.4f} USDT
══════════════════"""
            await self.db.log(user_id, "INFO", order_confirmed_log.strip())
            
            # AUDIT LOG for trade execution
            await self.db.audit_log(
                user_id=user_id,
                action="TRADE_EXECUTED",
                details={
                    'symbol': symbol,
                    'side': 'BUY',
                    'qty': round(rounded_qty, 6),
                    'entry_price': round(entry_price, 4),
                    'stop_loss': round(stop_loss, 4),
                    'take_profit': round(take_profit, 4),
                    'regime': regime,
                    'risk_pct': settings.risk_per_trade * 100,
                    'mode': settings.mode,
                    'notional': round(notional, 2),
                    'fees': round(entry_fee, 4),
                    'slippage': round(slippage_cost, 4),
                    'budget_remaining': round(available_budget - notional, 2)
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
            
            # Calculate fees and slippage for exit
            notional = position.qty * exit_price
            fee_rate = settings.fee_bps / 10000
            slippage_rate = settings.slippage_bps / 10000
            
            exit_fee = notional * fee_rate
            
            # Apply fees and slippage
            exit_price_adjusted = risk_mgr.apply_fees_and_slippage(exit_price, "SELL")
            
            # Calculate PnL (gross)
            gross_pnl = (exit_price - position.entry_price) * position.qty
            
            # Calculate total fees (entry was already applied, estimate it)
            entry_notional = position.entry_price * position.qty
            entry_fee = entry_notional * fee_rate
            total_fees = entry_fee + exit_fee
            total_slippage = (entry_notional + notional) * slippage_rate
            
            # Net PnL after fees and slippage
            net_pnl = gross_pnl - total_fees - total_slippage
            pnl_pct = (net_pnl / entry_notional) * 100 if entry_notional > 0 else 0
            
            # Update account
            cash_returned = position.qty * exit_price_adjusted
            account.cash += cash_returned
            account.equity = account.cash + sum(
                p.qty * exit_price for p in account.open_positions if p.symbol != position.symbol
            )
            
            # Remove position
            account.open_positions = [
                p for p in account.open_positions if p.symbol != position.symbol
            ]
            
            # Log trade with enhanced info
            trade = Trade(
                user_id=user_id,
                ts=datetime.now(timezone.utc),
                symbol=position.symbol,
                side="SELL",
                qty=position.qty,
                entry=position.entry_price,
                exit=exit_price_adjusted,
                pnl=net_pnl,
                pnl_pct=pnl_pct,
                fees_paid=total_fees,
                slippage_cost=total_slippage,
                mode=settings.mode,
                reason=reason,
                notional=notional
            )
            await self.db.add_trade(trade)
            
            # AUDIT LOG for trade close
            await self.db.audit_log(
                user_id=user_id,
                action="TRADE_EXECUTED",
                details={
                    'symbol': position.symbol,
                    'side': 'SELL',
                    'qty': round(position.qty, 4),
                    'exit_price': round(exit_price_adjusted, 4),
                    'gross_pnl': round(gross_pnl, 2),
                    'net_pnl': round(net_pnl, 2),
                    'pnl_pct': round(pnl_pct, 2),
                    'total_fees': round(total_fees, 4),
                    'reason': reason,
                    'mode': settings.mode
                }
            )
            
            # Check for consecutive losses and pause symbol if needed
            if net_pnl < 0:
                recent_losses = await self.db.get_recent_symbol_losses(user_id, position.symbol, hours=12)
                if recent_losses >= 3:
                    await self.db.set_symbol_pause(
                        user_id=user_id,
                        symbol=position.symbol,
                        pause_hours=24,
                        reason="3 consecutive losses in 12h",
                        consecutive_losses=recent_losses
                    )
                    await self.db.log(user_id, "WARNING", f"{position.symbol} paused for 24h due to {recent_losses} losses in 12h")
            
            await self.db.log(
                user_id,
                "INFO" if net_pnl > 0 else "WARNING",
                f"CLOSE {position.symbol} @ {exit_price_adjusted:.4f}",
                {
                    'entry': round(position.entry_price, 4),
                    'gross_pnl': round(gross_pnl, 2),
                    'net_pnl': round(net_pnl, 2),
                    'pnl_pct': round(pnl_pct, 2),
                    'fees': round(total_fees, 4),
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
