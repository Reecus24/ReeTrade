# New version of scan_and_trade with regime detection - to be integrated

async def scan_and_trade_with_regime(self, user_id: str, settings: UserSettings):
    account = await self.db.get_paper_account(user_id)
    
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
    if self.is_in_cooldown(user_id, 5):  # 5 candles cooldown
        await self.db.log(user_id, "DEBUG", "In cooldown period, skipping new entries")
        return
    
    # Look for new entries with regime detection
    if risk_mgr.can_open_position(account):
        for symbol in settings.top_pairs[:10]:
            try:
                # Check symbol pause
                if await self.db.is_symbol_paused(user_id, symbol):
                    continue
                
                # Get 4H klines for regime
                klines_4h = await mexc.get_klines(symbol, interval="4h", limit=250)
                regime, regime_ctx = self.regime_detector.detect_regime(klines_4h)
                
                await self.db.log(user_id, "INFO", f"{symbol} Regime: {regime}", regime_ctx)
                
                # Skip based on regime
                if regime == "BEARISH":
                    continue
                if regime == "SIDEWAYS":
                    continue
                if regime != "BULLISH":
                    continue
                
                # Bullish regime - proceed with entry check
                klines_15m = await mexc.get_klines(symbol, interval="15m", limit=500)
                
                if len(klines_15m) < settings.ema_slow:
                    continue
                
                signal, context = strategy.generate_signal(klines_15m)
                
                if signal == "LONG":
                    # Adjust risk for bullish regime (0.5%)
                    original_risk = settings.risk_per_trade
                    settings.risk_per_trade = 0.005
                    
                    # Calculate ATR stop (mult 2.5)
                    atr = strategy.calculate_atr(klines_15m, 14)
                    if atr:
                        stop_loss = float(klines_15m[-1][4]) - (atr * 2.5)
                        take_profit = float(klines_15m[-1][4]) + (atr * 2.5 * 2.5)  # 1:2.5 RR
                    else:
                        stop_loss = risk_mgr.calculate_stop_loss(float(klines_15m[-1][4]), atr)
                        take_profit = risk_mgr.calculate_take_profit(float(klines_15m[-1][4]), stop_loss)
                    
                    # Open position
                    await self.open_position_regime_aware(
                        user_id, symbol, klines_15m, account, settings,
                        strategy, risk_mgr, context, mexc, stop_loss, take_profit
                    )
                    
                    settings.risk_per_trade = original_risk
                    self.user_last_trade_time[user_id] = datetime.now(timezone.utc)
                    break
                    
            except Exception as e:
                await self.db.log(user_id, "ERROR", f"Error scanning {symbol}: {str(e)}")
    
    await self.db.update_paper_account(account)
