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
from ai_engine import (
    AITradingEngine, TradingMode, MarketConditions, AccountState, MarketRegime
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
        self.ai_engine = AITradingEngine()  # AI Trading Engine
    
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
        """Fast loop to check exits every 30 seconds"""
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
            
            await asyncio.sleep(30)
    
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
        """Sync open positions with MEXC trade history to detect external sells"""
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
        
        # Check each open position
        positions_to_close = []
        
        for position in account.open_positions:
            try:
                # Get recent trades for this symbol
                # Look back 2 hours for any sells
                start_time = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp() * 1000)
                trades = await mexc.get_my_trades(position.symbol, limit=50, start_time=start_time)
                
                if not trades:
                    continue
                
                # Look for SELL trades after our entry
                entry_time_ms = int(position.entry_time.timestamp() * 1000)
                
                for trade in trades:
                    # Check if this is a sell trade after our entry
                    trade_time = trade.get('time', 0)
                    is_buyer = trade.get('isBuyerMaker', True)  # If buyer is maker, we sold
                    
                    # A trade where we're NOT the buyer is a sell
                    if trade_time > entry_time_ms and not is_buyer:
                        trade_qty = float(trade.get('qty', 0))
                        trade_price = float(trade.get('price', 0))
                        
                        # Check if qty matches our position (allow small difference for partial fills)
                        if abs(trade_qty - position.qty) / position.qty < 0.1:  # Within 10%
                            positions_to_close.append({
                                'position': position,
                                'exit_price': trade_price,
                                'exit_time': trade_time,
                                'reason': 'MEXC_SYNC: External sell detected'
                            })
                            await self.db.log(user_id, "INFO", 
                                f"[LIVE] MEXC SYNC: Erkenne externen Verkauf von {position.symbol} @ {trade_price:.4f}")
                            break
                
            except Exception as e:
                logger.warning(f"Error checking MEXC trades for {position.symbol}: {e}")
        
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
        mexc = await self.get_user_mexc_client(user_id, settings)
        
        for position in account.open_positions[:]:
            try:
                ticker = await mexc.get_ticker_24h(position.symbol)
                current_price = float(ticker['lastPrice'])
                
                should_exit = False
                exit_reason = ""
                
                if current_price <= position.stop_loss:
                    should_exit = True
                    exit_reason = f"🛑 STOP LOSS @ {current_price:.4f}"
                
                elif current_price >= position.take_profit:
                    should_exit = True
                    exit_reason = f"🎯 TAKE PROFIT @ {current_price:.4f}"
                
                if should_exit:
                    await self.db.log(user_id, "INFO", f"[LIVE] EXIT: {position.symbol} - {exit_reason}")
                    await self.close_position(user_id, position, current_price, account, settings, exit_reason, mexc)
                    await self.db.update_live_account(account)
                    
            except Exception as e:
                logger.error(f"Exit check error for {position.symbol}: {e}")
    
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
            
            # Calculate expected position size for filtering
            trading_budget = settings.trading_budget_usdt or 500
            if is_ai_mode:
                from ai_engine import RISK_PROFILES
                profile = RISK_PROFILES.get(trading_mode, {})
                base_pct = profile.get('base_position_pct', 3.0)
                expected_position_size = trading_budget * base_pct / 100
            else:
                expected_position_size = settings.live_max_order_usdt or 50
            
            await self.db.log(user_id, "INFO", 
                f"🔍 Intelligente Coin-Suche gestartet | Modus: {trading_mode.value} | Erwartete Order: ${expected_position_size:.2f}")
            
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
                        
                        # AI Aggressive: Accept BULLISH and SIDEWAYS
                        # Other modes: Only BULLISH
                        acceptable_regimes = ["BULLISH"]
                        if trading_mode == TradingMode.AI_AGGRESSIVE:
                            acceptable_regimes = ["BULLISH", "SIDEWAYS"]
                        
                        if regime in acceptable_regimes:
                            filtered_pairs.append({
                                **pair_data,
                                'regime': regime,
                                'adx': regime_ctx.get('adx', 0),
                                'potential_qty': potential_qty,
                                'is_optimal': is_optimal
                            })
                            
                            # Get up to 25 coins for better selection
                            if len(filtered_pairs) >= 25:
                                break
                        else:
                            skipped_bearish += 1
                except Exception as e:
                    logger.warning(f"Error checking regime for {symbol}: {e}")
                    continue
            
            # Sort: Prioritize optimal coins, then by ADX strength
            filtered_pairs.sort(key=lambda x: (x.get('is_optimal', False), x.get('adx', 0)), reverse=True)
            
            # Take top 20 for trading
            tradable_symbols = [p['symbol'] for p in filtered_pairs[:20]]
            
            await self.db.update_settings(user_id, {
                'top_pairs': tradable_symbols,
                'last_pairs_refresh': datetime.now(timezone.utc)
            })
            
            # Detailed logging
            optimal_count = sum(1 for p in filtered_pairs[:20] if p.get('is_optimal', False))
            
            await self.db.log(
                user_id, "INFO", 
                f"✅ Momentum Rotation abgeschlossen:\n"
                f"   • {len(tradable_symbols)} BULLISH Coins ausgewählt ({optimal_count} optimal für Trade-Größe)\n"
                f"   • {skipped_price_too_high} übersprungen (Preis zu hoch für ${expected_position_size:.2f} Order)\n"
                f"   • {skipped_bearish} übersprungen (nicht BULLISH)",
                {'symbols': tradable_symbols[:10]}
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
        
        # Get AI profile limits and calculate expected position sizes
        if is_ai_mode:
            from ai_engine import RISK_PROFILES
            profile = RISK_PROFILES.get(trading_mode, {})
            effective_max_positions = profile.get('max_positions', settings.max_positions)
            
            # Calculate AI position size based on trading budget
            trading_budget = settings.trading_budget_usdt or 500
            base_pct = profile.get('base_position_pct', 3.0)
            max_pct = profile.get('max_position_pct', 5.0)
            
            # AI position range
            ai_min_position = round(trading_budget * (base_pct * 0.5) / 100, 2)
            ai_max_position = round(trading_budget * max_pct / 100, 2)
            effective_position_size = round(trading_budget * base_pct / 100, 2)
            
            await self.db.log(user_id, "INFO", 
                f"[LIVE] 🤖 AI Mode: {trading_mode.value} | Position: ${ai_min_position:.0f}-${ai_max_position:.0f} | Max Pos: {effective_max_positions}")
        
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
            f"[LIVE] ═══ SCAN START ({mode_label}) ═══ Budget: ${available_budget:.2f} | Trade: {trade_size_label} | Positions: {positions_count}/{effective_max_positions}")
        
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
        
        # Calculate effective position size for runtime filtering
        effective_scan_position = effective_position_size if is_ai_mode else settings.live_max_order_usdt
        
        await self.db.log(user_id, "INFO", f"[LIVE] 🔍 Scanne {len(settings.top_pairs[:20])} Coins | Trade-Größe: ${effective_scan_position:.2f}")
        
        for symbol in settings.top_pairs[:20]:
            symbols_checked += 1
            try:
                # Check if symbol is paused
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
                
                # AI Mode: Get AI decision with REAL market data
                if is_ai_mode:
                    market_conditions = MarketConditions(
                        regime=MarketRegime(regime),
                        volatility_percentile=volatility_percentile,
                        momentum_score=regime_context.get('momentum', 0),
                        adx_value=adx_value,
                        rsi_value=regime_context.get('rsi', 50)
                    )
                    
                    account_state = AccountState(
                        total_equity=current_equity,
                        available_budget=available_budget,
                        current_drawdown_pct=drawdown_pct,
                        open_positions_count=positions_count,
                        today_pnl=today_pnl,
                        today_trades_count=today_trades
                    )
                    
                    manual_settings_dict = {
                        'live_max_order_usdt': settings.live_max_order_usdt,
                        'max_positions': settings.max_positions
                    }
                    
                    # Get AI decision for this symbol with REAL market data
                    ai_decision = self.ai_engine.make_decision(
                        trading_mode, market_conditions, account_state, manual_settings_dict
                    )
                    
                    if not ai_decision.should_trade:
                        await self.db.log(user_id, "INFO", f"[LIVE] 🤖 {symbol}: AI SKIP - {ai_decision.reasoning[-1] if ai_decision.reasoning else 'Unbekannt'}")
                        continue  # AI says skip this symbol
                    
                    # Update effective position size from AI
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
                    continue
                
                # SIGNAL FOUND!
                current_price = float(klines_15m[-1][4])
                ema_fast_val = context.get('ema_fast', 0)
                ema_slow_val = context.get('ema_slow', 0)
                rsi_val = context.get('rsi', 0)
                
                # Calculate stop/take profit (AI or manual)
                atr = strategy.calculate_atr(klines_15m, 14)
                if is_ai_mode and ai_decision:
                    # Use AI-determined TP/SL percentages
                    stop_loss = current_price * (1 - ai_decision.stop_loss_pct / 100)
                    take_profit = current_price * (1 + ai_decision.take_profit_pct / 100)
                elif atr:
                    stop_loss = current_price - (atr * 2.5)
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
            await self.db.update_settings(user_id, {
                'live_last_decision': f'KEIN SIGNAL bei {symbols_checked} Coins',
                'live_last_symbol': '-'
            })
        
        await self.db.log(user_id, "INFO", f"[LIVE] ═══ SCAN COMPLETE ═══ {symbols_checked} Coins, {len(signal_candidates)} Signale")
    
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
            
            # Calculate position size (AI or manual)
            if is_ai_mode and ai_decision and ai_decision.position_size_usdt > 0:
                # Use AI-determined position size
                notional = min(ai_decision.position_size_usdt, available_budget * 0.95)
                await self.db.log(user_id, "INFO", f"[LIVE] 🤖 AI Position Size: ${notional:.2f}")
            else:
                # Manual position sizing
                max_order = min(settings.live_max_order_usdt, available_budget)
                notional = min(max_order, available_budget * 0.95)
            
            if notional < settings.live_min_notional_usdt:
                await self.db.log(user_id, "WARNING", f"[LIVE] Notional ${notional:.2f} below minimum ${settings.live_min_notional_usdt}")
                return False
            
            qty = notional / current_price
            
            # Apply exchange filters
            formatted_qty = order_sizer.get_formatted_quantity(symbol, qty)
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
            
            # Parse order result
            executed_qty = float(order_result.get('executedQty', formatted_qty))
            avg_price = float(order_result.get('price', current_price))
            
            if avg_price == 0:
                fills = order_result.get('fills', [])
                if fills:
                    total_qty = sum(float(f.get('qty', 0)) for f in fills)
                    total_cost = sum(float(f.get('qty', 0)) * float(f.get('price', 0)) for f in fills)
                    avg_price = total_cost / total_qty if total_qty > 0 else current_price
                else:
                    avg_price = current_price
            
            actual_notional = executed_qty * avg_price
            
            # Create position record
            position = Position(
                symbol=symbol,
                side="LONG",
                entry_price=avg_price,
                qty=executed_qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
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
            
            formatted_qty = order_sizer.get_formatted_quantity(position.symbol, position.qty)
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
