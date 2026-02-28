import logging
from typing import Optional, Tuple
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)

class OrderSizer:
    # Handle order sizing with exchange filters (minQty, stepSize, minNotional)
    
    def __init__(self):
        self.symbol_filters = {}  # Cache for exchange info
    
    def update_symbol_filters(self, exchange_info: dict):
        # Extract filters from MEXC exchangeInfo
        for symbol_data in exchange_info.get('symbols', []):
            symbol = symbol_data['symbol']
            filters = {}
            
            for f in symbol_data.get('filters', []):
                if f['filterType'] == 'LOT_SIZE':
                    filters['minQty'] = float(f['minQty'])
                    filters['maxQty'] = float(f['maxQty'])
                    filters['stepSize'] = float(f['stepSize'])
                elif f['filterType'] == 'MIN_NOTIONAL':
                    filters['minNotional'] = float(f['minNotional'])
            
            self.symbol_filters[symbol] = filters
    
    def round_quantity(self, symbol: str, qty: float) -> float:
        # Round quantity to exchange stepSize
        if symbol not in self.symbol_filters:
            logger.warning(f"No filters for {symbol}, returning original qty")
            return qty
        
        filters = self.symbol_filters[symbol]
        step_size = filters.get('stepSize', 1)
        min_qty = filters.get('minQty', 0)
        max_qty = filters.get('maxQty', float('inf'))
        
        # Round down to stepSize
        qty_decimal = Decimal(str(qty))
        step_decimal = Decimal(str(step_size))
        
        rounded_qty = float((qty_decimal // step_decimal) * step_decimal)
        
        # Clamp to min/max
        if rounded_qty < min_qty:
            return 0  # Below minimum
        if rounded_qty > max_qty:
            rounded_qty = max_qty
        
        return rounded_qty
    
    def validate_notional(
        self, 
        symbol: str, 
        qty: float, 
        price: float, 
        user_min_notional: float = 10.0
    ) -> Tuple[bool, str]:
        # Validate order notional value
        
        notional = qty * price
        
        # Check user-configured minimum
        if notional < user_min_notional:
            return False, f"Notional ${notional:.2f} < user min ${user_min_notional:.2f}"
        
        # Check exchange minimum
        if symbol in self.symbol_filters:
            exchange_min = self.symbol_filters[symbol].get('minNotional', 0)
            if notional < exchange_min:
                return False, f"Notional ${notional:.2f} < exchange min ${exchange_min:.2f}"
        
        return True, "OK"

# Global instance
order_sizer = OrderSizer()
