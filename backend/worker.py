import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from db_operations import Database
from mexc_client import MexcClient
from strategy import TradingStrategy
from risk_manager import RiskManager
from models import Position, Trade, BotSettings, PaperAccount

logger = logging.getLogger(__name__)

class TradingWorker:
    """Background worker for automated trading"""
    
    def __init__(self, db: Database):
        self.db = db
        self.mexc = MexcClient()
        self.running = False
        self.initial_equity = 10000.0  # Track for daily loss limit
    
    async def heartbeat(self):
        """Update heartbeat every 60 seconds"""
        while self.running:
            await self.db.update_settings({
                'last_heartbeat': datetime.now(timezone.utc)
            })
            await asyncio.sleep(60)
    
    async def trading_loop(self):
        """Main trading loop - runs every 15 minutes"""
        while self.running:
            try:
                settings = await self.db.get_settings()
                
                if not settings.bot_running:
                    await asyncio.sleep(60)
                    continue
                
                await self.db.log("INFO", "Starting trading cycle")
                
                # Refresh top pairs daily
                should_refresh = (
                    not settings.last_pairs_refresh or
                    (datetime.now(timezone.utc) - settings.last_pairs_refresh) > timedelta(hours=24)
                )
                
                if should_refresh:
                    await self.refresh_top_pairs()
                    settings = await self.db.get_settings()  # Reload
                
                if not settings.top_pairs:
                    await self.db.log("WARNING", "No top pairs available")
                    await asyncio.sleep(900)  # 15 min
                    continue
                
                # Scan symbols for signals
                await self.scan_and_trade(settings)
                
            except Exception as e:
                await self.db.log("ERROR", f"Trading loop error: {str(e)}")
                logger.exception(e)
            
            # Wait 15 minutes
            await asyncio.sleep(900)
    
    async def refresh_top_pairs(self):
        """Refresh top 20 USDT pairs by volume"""
        try:
            await self.db.log("INFO", "Refreshing top pairs...")
            top_pairs = await self.mexc.get_top_pairs(quote="USDT", limit=20)
            
            await self.db.update_settings({
                'top_pairs': top_pairs,
                'last_pairs_refresh': datetime.now(timezone.utc)
            })
            
            await self.db.log("INFO", f"Top pairs updated: {len(top_pairs)} symbols", 
                            {'pairs': top_pairs[:5]})
        except Exception as e:
            await self.db.log("ERROR", f"Failed to refresh top pairs: {str(e)}")
    
    async def scan_and_trade(self, settings: BotSettings):
        """Scan symbols and execute trades"""
        account = await self.db.get_paper_account()
        strategy = TradingStrategy(
            ema_fast=settings.ema_fast,
            ema_slow=settings.ema_slow,
            rsi_period=settings.rsi_period,
            rsi_min=settings.rsi_min,
            rsi_overbought=settings.rsi_overbought
        )
        risk_mgr = RiskManager(settings)
        
        # Check daily loss limit
        if risk_mgr.check_daily_loss_limit(account, self.initial_equity):
            await self.db.log("ERROR", "Daily loss limit hit - stopping bot")
            await self.db.update_settings({'bot_running': False})
            return
        
        # Check existing positions for exits
        for pos in account.open_positions[:]:
            await self.check_position_exit(pos, account, settings)
        
        # Look for new entries
        if risk_mgr.can_open_position(account):
            for symbol in settings.top_pairs[:10]:  # Check top 10
                try:
                    # Get 15m klines
                    klines = await self.mexc.get_klines(symbol, interval="15m", limit=500)
                    
                    if len(klines) < settings.ema_slow:
                        continue
                    
                    signal, context = strategy.generate_signal(klines)
                    
                    if signal == "LONG":
                        await self.open_position(symbol, klines, account, settings, strategy, risk_mgr, context)
                        break  # One entry per cycle
                    
                except Exception as e:
                    await self.db.log("ERROR", f"Error scanning {symbol}: {str(e)}")
        
        # Save updated account
        await self.db.update_paper_account(account)
    
    async def open_position(
        self,
        symbol: str,
        klines: list,
        account: PaperAccount,
        settings: BotSettings,
        strategy: TradingStrategy,
        risk_mgr: RiskManager,
        context: dict
    ):
        """Open new position"""
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
                await self.db.log("WARNING", f"Cannot size position for {symbol}: {reason}")
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
            await self.db.log("ERROR", f"Failed to open position {symbol}: {str(e)}")
    
    async def check_position_exit(
        self,
        position: Position,
        account: PaperAccount,
        settings: BotSettings
    ):
        """Check if position should be closed"""
        try:
            # Get current price
            ticker = await self.mexc.get_ticker_24h(position.symbol)
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
                await self.close_position(position, current_price, account, settings, exit_reason)
            
        except Exception as e:
            await self.db.log("ERROR", f"Error checking position {position.symbol}: {str(e)}")
    
    async def close_position(
        self,
        position: Position,
        exit_price: float,
        account: PaperAccount,
        settings: BotSettings,
        reason: str
    ):
        """Close position"""
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
            await self.db.log("ERROR", f"Failed to close position {position.symbol}: {str(e)}")
    
    async def start(self):
        """Start worker"""
        if self.running:
            return
        
        self.running = True
        await self.db.log("INFO", "Trading worker started")
        
        # Start both tasks
        await asyncio.gather(
            self.heartbeat(),
            self.trading_loop()
        )
    
    async def stop(self):
        """Stop worker"""
        self.running = False
        await self.db.log("INFO", "Trading worker stopped")
