from typing import Optional, Tuple
import logging
from models import BotSettings, PaperAccount, Position
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RiskManager:
    """Manage position sizing and risk limits"""
    
    def __init__(self, settings: BotSettings):
        self.settings = settings
    
    def can_open_position(self, account: PaperAccount) -> bool:
        """Check if we can open a new position"""
        if len(account.open_positions) >= self.settings.max_positions:
            logger.warning(f"Max positions reached: {len(account.open_positions)}/{self.settings.max_positions}")
            return False
        return True
    
    def calculate_position_size(
        self,
        account: PaperAccount,
        entry_price: float,
        stop_loss: float
    ) -> Tuple[float, str]:
        """Calculate position size based on risk per trade
        
        Returns:
            Tuple of (quantity, reason)
        """
        if entry_price <= 0 or stop_loss <= 0:
            return 0, "Invalid prices"
        
        # Risk amount in USD
        risk_amount = account.equity * self.settings.risk_per_trade
        
        # Risk per share
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share == 0:
            return 0, "Stop loss too tight"
        
        # Position size
        quantity = risk_amount / risk_per_share
        
        # Position value
        position_value = quantity * entry_price
        
        # Check if we have enough cash
        if position_value > account.cash:
            quantity = account.cash / entry_price
            logger.warning(f"Insufficient cash, adjusted position size to {quantity}")
        
        return quantity, "OK"
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: Optional[float] = None
    ) -> float:
        """Calculate stop loss level
        
        If ATR stop enabled, use ATR * multiplier
        Otherwise, use fixed percentage (1% of risk per trade)
        """
        if self.settings.atr_stop and atr:
            stop_distance = atr * self.settings.atr_mult
        else:
            # Default: 1% stop loss
            stop_distance = entry_price * 0.01
        
        stop_loss = entry_price - stop_distance
        return max(stop_loss, entry_price * 0.95)  # Min 5% stop
    
    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """Calculate take profit level based on risk:reward ratio"""
        risk = abs(entry_price - stop_loss)
        take_profit = entry_price + (risk * self.settings.take_profit_rr)
        return take_profit
    
    def apply_fees_and_slippage(self, price: float, side: str) -> float:
        """Apply fees and slippage to execution price
        
        Args:
            price: Market price
            side: BUY or SELL
        
        Returns:
            Adjusted execution price
        """
        total_bps = self.settings.fee_bps + self.settings.slippage_bps
        adjustment = price * (total_bps / 10000)
        
        if side == "BUY":
            return price + adjustment  # Pay more when buying
        else:
            return price - adjustment  # Receive less when selling
    
    def check_daily_loss_limit(self, account: PaperAccount, initial_equity: float) -> bool:
        """Check if daily loss limit has been hit
        
        Returns:
            True if limit hit (should stop trading)
        """
        current_loss = (initial_equity - account.equity) / initial_equity
        
        if current_loss >= self.settings.max_daily_loss:
            logger.error(f"Daily loss limit hit: {current_loss*100:.2f}%")
            return True
        
        return False
