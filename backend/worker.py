import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from db_operations import Database
from mexc_client import MexcClient
from strategy import TradingStrategy
from risk_manager import RiskManager
from regime_detector import RegimeDetector
from order_sizer import order_sizer
from models import Position, Trade, UserSettings, PaperAccount
from ai_engine_v2 import (
    AITradingEngineV2, TradingMode, MarketConditions, AccountState, MarketRegime,
    RISK_PROFILES_V2, ai_engine_v2
)

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
        # Coin rotation: track which batch of coins to scan next
        self.user_coin_batch: Dict[str, int] = {}  # {user_id: batch_index}
        self.user_all_coins: Dict[str, list] = {}  # {user_id: [all coins]}
        self.COINS_PER_BATCH = 20
        self.MAX_BATCHES = 5  # 5 batches x 20 = 100 coins before refresh
    
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
        
        for position in account.open_positions[:]:
            try:
                ticker = await mexc.get_ticker_24h(position.symbol)
                current_price = float(ticker['lastPrice'])
                
                # Calculate current PnL for logging
                pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                
                should_exit = False
                exit_reason = ""
                
                if current_price <= position.stop_loss:
                    should_exit = True
                    exit_reason = f"🛑 STOP LOSS @ {current_price:.4f}"
                
                elif current_price >= position.take_profit:
                    should_exit = True
                    exit_reason = f"🎯 TAKE PROFIT @ {current_price:.4f}"
                
                if should_exit:
                    await self.db.log(user_id, "WARNING", f"[EXIT] {position.symbol} - {exit_reason} | PnL: {pnl_pct:.1f}%")
                    await self.close_position(user_id, position, current_price, account, settings, exit_reason, mexc)
                    await self.db.update_live_account(account)
                else:
                    # Log check every 5 minutes (10 checks)
                    if not hasattr(self, '_exit_log_counter'):
                        self._exit_log_counter = {}
                    counter_key = f"{user_id}_{position.symbol}"
                    self._exit_log_counter[counter_key] = self._exit_log_counter.get(counter_key, 0) + 1
                    if self._exit_log_counter[counter_key] >= 10:
                        await self.db.log(user_id, "INFO", 
                            f"[EXIT CHECK] {position.symbol}: Preis={current_price:.4f} | SL={position.stop_loss:.4f} | PnL={pnl_pct:.1f}%")
                        self._exit_log_counter[counter_key] = 0
                    
            except Exception as e:
                logger.error(f"Exit check error for {position.symbol}: {e}")
                await self.db.log(user_id, "ERROR", f"[EXIT] {position.symbol} Check Fehler: {str(e)[:50]}")
    
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
            'ai_min_position': ai_decision.min_position_usdt if ai_decision else ai_min_position,
            'ai_max_position': ai_decision.max_position_usdt if ai_decision else ai_max_position,
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
        
        # Check cooldown
        if self.is_in_cooldown(user_id, settings.cooldown_candles):
            cooldown_mins = settings.cooldown_candles * 15
            await self.db.log(user_id, "INFO", f"[LIVE] ⏸️ SKIPPED: Cooldown active ({cooldown_mins} Min)")
            await self.db.update_settings(user_id, {
                'live_last_decision': f'SKIPPED: Cooldown ({cooldown_mins} Min)',
                'live_last_symbol': 'Warte auf Cooldown-Ende'
            })
            return
        
        # Scan for signals - scan all available pairs (up to 20)
        signal_candidates = []
        symbols_checked = 0
        symbols_already_owned = 0
        
        # Get list of symbols we already own (for diversification)
        owned_symbols = set()
        if account and account.open_positions:
            owned_symbols = {pos.symbol for pos in account.open_positions}
        
        # Calculate effective position size for runtime filtering
        effective_scan_position = effective_position_size if is_ai_mode else settings.live_max_order_usdt
        
        await self.db.log(user_id, "INFO", f"[LIVE] 🔍 Scanne {len(settings.top_pairs[:20])} Coins | Trade-Größe: ${effective_scan_position:.2f} | Bereits im Portfolio: {len(owned_symbols)}")
        
        for symbol in settings.top_pairs[:20]:
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
                    
                    market_conditions = MarketConditions(
                        regime=regime_enum,
                        adx_value=adx_value,
                        atr_value=current_atr,
                        atr_percent=atr_percent,
                        volatility_percentile=volatility_percentile,
                        momentum_score=regime_context.get('momentum', 0),
                        rsi_value=regime_context.get('rsi', 50),
                        current_price=current_price
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
                    
                    # Get AI decision from V2 engine
                    ai_decision = self.ai_engine.make_decision(
                        user_id, trading_mode, market_conditions, account_state, trading_budget_remaining
                    )
                    
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
                
                trade_success = await self.open_live_position(
                    user_id, symbol, candidate, account, settings, strategy, risk_mgr, mexc, 
                    position_budget, is_ai_mode, candidate_ai
                )
                
                if trade_success:
                    self.set_last_trade_time(user_id)
                    decision_text = f'TRADE: {symbol} (Score: {candidate["score"]:.1f})'
                    if is_ai_mode and candidate_ai:
                        decision_text = f'🤖 AI TRADE: {symbol} (Score: {candidate["score"]:.1f})'
                    
                    await self.db.update_settings(user_id, {
                        'live_last_decision': decision_text,
                        'live_last_regime': candidate['regime'],
                        'live_last_symbol': symbol,
                        'ai_confidence': candidate_ai.confidence if candidate_ai else None,
                        'ai_risk_score': candidate_ai.risk_score if candidate_ai else None,
                        'ai_reasoning': candidate_ai.reasoning if candidate_ai else None,
                        'ai_min_position': candidate_ai.min_position_usdt if candidate_ai else None,
                        'ai_max_position': candidate_ai.max_position_usdt if candidate_ai else None,
                        'ai_current_position': candidate_ai.position_size_usdt if candidate_ai else None,
                        'ai_last_override': {
                            'timestamp': scan_time.isoformat(),
                            'symbol': symbol,
                            'position_size': candidate_ai.position_size_usdt if candidate_ai else None,
                            'stop_loss_pct': candidate_ai.stop_loss_pct if candidate_ai else None,
                            'take_profit_pct': candidate_ai.take_profit_pct if candidate_ai else None,
                            'overrides': [{'field': o.field, 'manual': o.manual_value, 'ai': o.ai_value, 'reason': o.reason} for o in (candidate_ai.overrides if candidate_ai else [])]
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
                        'ai_min_position': best_ai_decision.min_position_usdt,
                        'ai_max_position': best_ai_decision.max_position_usdt,
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
            
            await self.db.log(user_id, "WARNING",
                f"[LIVE] ✅ ORDER CONFIRMED: {symbol} | Qty: {executed_qty} | Price: ${avg_price:.4f} | Notional: ${actual_notional:.2f}")
            
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
        """Close a position with real SELL order"""
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
            
            await self.db.log(user_id, "WARNING" if pnl < 0 else "INFO",
                f"[LIVE] ✅ SELL CONFIRMED: {position.symbol} | Exit: ${actual_exit_price:.4f} | PnL: ${pnl:.2f} ({pnl_pct:.1f}%)")
            
            # Check consecutive losses
            if pnl < 0:
                recent_losses = await self.db.get_recent_symbol_losses(user_id, position.symbol, hours=12)
                if recent_losses >= 3:
                    await self.db.set_symbol_pause(user_id, position.symbol, 24, "3 losses in 12h", recent_losses)
                    
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
