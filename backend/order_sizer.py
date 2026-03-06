import logging
from typing import Optional, Tuple, Dict
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)

class OrderSizer:
    """
    Handle order sizing with exchange filters (minQty, stepSize, minNotional, tickSize)
    
    CRITICAL for avoiding 400 Bad Request errors on MEXC!
    - All quantities MUST be rounded DOWN to stepSize
    - All quantities MUST be >= minQty
    - All notionals MUST be >= minNotional
    - All prices MUST be rounded to tickSize
    """
    
    def __init__(self):
        self.symbol_filters: Dict[str, Dict] = {}  # Cache for exchange info
        self._last_update = None
    
    def update_symbol_filters(self, exchange_info: dict):
        """Extract filters from MEXC exchangeInfo response
        
        Note: MEXC doesn't always have LOT_SIZE/MIN_NOTIONAL filters.
        We use basePrecision/quotePrecision as fallback for step sizes.
        """
        count = 0
        for symbol_data in exchange_info.get('symbols', []):
            symbol = symbol_data['symbol']
            
            # Get precision from symbol data (MEXC primary method)
            base_precision = symbol_data.get('baseAssetPrecision', 8)
            quote_precision = symbol_data.get('quoteAssetPrecision', 8)
            
            # Calculate step size from precision: 10^(-precision)
            step_size_from_precision = 10 ** (-base_precision)
            tick_size_from_precision = 10 ** (-quote_precision)
            
            filters = {
                'minQty': step_size_from_precision,  # Minimum = 1 step
                'maxQty': float('inf'),
                'stepSize': step_size_from_precision,
                'minNotional': 1,  # MEXC default ~1 USDT minimum
                'tickSize': tick_size_from_precision,
                'basePrecision': base_precision,
                'quotePrecision': quote_precision
            }
            
            # Override with explicit filters if present
            for f in symbol_data.get('filters', []):
                if f['filterType'] == 'LOT_SIZE':
                    filters['minQty'] = float(f.get('minQty', filters['minQty']))
                    filters['maxQty'] = float(f.get('maxQty', float('inf')))
                    filters['stepSize'] = float(f.get('stepSize', filters['stepSize']))
                elif f['filterType'] == 'MIN_NOTIONAL':
                    filters['minNotional'] = float(f.get('minNotional', 1))
                elif f['filterType'] == 'PRICE_FILTER':
                    filters['tickSize'] = float(f.get('tickSize', filters['tickSize']))
            
            self.symbol_filters[symbol] = filters
            count += 1
        
        logger.info(f"[OrderSizer] Updated filters for {count} symbols")
        self._last_update = count
    
    def get_filters(self, symbol: str) -> Optional[Dict]:
        """Get filters for a symbol"""
        return self.symbol_filters.get(symbol)
    
    def round_quantity(self, symbol: str, qty: float) -> Optional[float]:
        """
        Round quantity DOWN to exchange stepSize
        
        Returns:
            float: Rounded quantity, or None if below minQty
        """
        if symbol not in self.symbol_filters:
            logger.warning(f"[OrderSizer] No filters for {symbol}, using raw qty {qty}")
            return qty
        
        filters = self.symbol_filters[symbol]
        step_size = filters.get('stepSize', 1)
        min_qty = filters.get('minQty', 0)
        max_qty = filters.get('maxQty', float('inf'))
        
        # Round DOWN to stepSize using Decimal for precision
        try:
            qty_decimal = Decimal(str(qty))
            step_decimal = Decimal(str(step_size))
            
            # floor(qty / stepSize) * stepSize
            if step_decimal > 0:
                rounded_qty = float((qty_decimal // step_decimal) * step_decimal)
            else:
                rounded_qty = qty
            
            # Check minimum
            if rounded_qty < min_qty:
                logger.warning(f"[OrderSizer] {symbol}: qty {rounded_qty} < minQty {min_qty} - INVALID")
                return None
            
            # Check maximum
            if rounded_qty > max_qty:
                rounded_qty = float((Decimal(str(max_qty)) // step_decimal) * step_decimal)
                logger.info(f"[OrderSizer] {symbol}: qty clamped to maxQty {rounded_qty}")
            
            return rounded_qty
            
        except Exception as e:
            logger.error(f"[OrderSizer] {symbol}: rounding error - {e}")
            return qty
    
    def round_price(self, symbol: str, price: float) -> float:
        """Round price to exchange tickSize"""
        if symbol not in self.symbol_filters:
            return price
        
        filters = self.symbol_filters[symbol]
        tick_size = filters.get('tickSize', 0.00000001)
        
        try:
            price_decimal = Decimal(str(price))
            tick_decimal = Decimal(str(tick_size))
            
            if tick_decimal > 0:
                return float((price_decimal // tick_decimal) * tick_decimal)
            return price
        except Exception:
            return price
    
    def validate_order(
        self, 
        symbol: str, 
        qty: float, 
        price: float,
        side: str = "BUY"
    ) -> Tuple[bool, str, Optional[float]]:
        """
        Validate and prepare order quantity
        
        Returns:
            Tuple[is_valid, message, rounded_qty]
        """
        if symbol not in self.symbol_filters:
            logger.warning(f"[OrderSizer] {symbol}: No filters cached, allowing order")
            return True, "No filters (allowed)", qty
        
        filters = self.symbol_filters[symbol]
        min_qty = filters.get('minQty', 0)
        min_notional = filters.get('minNotional', 5)
        step_size = filters.get('stepSize', 1)
        
        # Round quantity
        rounded_qty = self.round_quantity(symbol, qty)
        
        if rounded_qty is None or rounded_qty <= 0:
            return False, f"Qty {qty} rounds to {rounded_qty} < minQty {min_qty}", None
        
        # Calculate notional
        notional = rounded_qty * price
        
        if notional < min_notional:
            return False, f"Notional ${notional:.4f} < minNotional ${min_notional}", None
        
        # Log validation result
        logger.info(
            f"[OrderSizer] {side} {symbol}: qty={qty:.8f} → {rounded_qty:.8f} | "
            f"price=${price:.8f} | notional=${notional:.4f} | "
            f"minQty={min_qty}, stepSize={step_size}, minNotional={min_notional}"
        )
        
        return True, "OK", rounded_qty
    
    def prepare_sell_quantity(
        self, 
        symbol: str, 
        available_qty: float, 
        current_price: float
    ) -> Tuple[bool, str, Optional[float]]:
        """
        Prepare sell quantity from available balance
        
        Rounds DOWN and validates against exchange minimums.
        Critical for avoiding SELL FAILED 400 errors!
        
        Returns:
            Tuple[is_valid, message, sell_qty]
        """
        if available_qty <= 0:
            return False, "No available quantity", None
        
        # Round to stepSize
        rounded_qty = self.round_quantity(symbol, available_qty)
        
        if rounded_qty is None or rounded_qty <= 0:
            filters = self.symbol_filters.get(symbol, {})
            return False, f"Qty {available_qty} → {rounded_qty} below minQty {filters.get('minQty', 0)}", None
        
        # Validate notional
        is_valid, msg, final_qty = self.validate_order(symbol, rounded_qty, current_price, "SELL")
        
        if not is_valid:
            logger.warning(f"[OrderSizer] SELL {symbol} BLOCKED: {msg}")
        
        return is_valid, msg, final_qty
    
    def log_filters(self, symbol: str):
        """Log filters for a symbol (debugging)"""
        if symbol in self.symbol_filters:
            f = self.symbol_filters[symbol]
            logger.info(
                f"[OrderSizer] {symbol} Filters: "
                f"minQty={f.get('minQty')}, maxQty={f.get('maxQty')}, "
                f"stepSize={f.get('stepSize')}, minNotional={f.get('minNotional')}, "
                f"tickSize={f.get('tickSize')}"
            )
        else:
            logger.warning(f"[OrderSizer] {symbol}: No filters cached!")
    
    def is_dust_position(
        self, 
        symbol: str, 
        qty: float, 
        current_price: float
    ) -> Tuple[bool, Dict]:
        """
        Check if a position is "dust" (too small to sell)
        
        A position is dust if:
        - qty < minQty (exchange minimum)
        - qty rounds to 0 after stepSize
        - notional < minNotional (typically 1-5 USDT)
        
        Returns:
            Tuple[is_dust, details_dict]
            
        details_dict contains:
            - reason: str (why it's dust)
            - qty: float
            - estimated_notional: float
            - min_qty: float
            - min_notional: float
            - step_size: float
        """
        # Default filters if not cached
        filters = self.symbol_filters.get(symbol, {})
        min_qty = filters.get('minQty', 0.0001)
        min_notional = filters.get('minNotional', 1.0)  # MEXC default
        step_size = filters.get('stepSize', 0.0001)
        
        details = {
            'symbol': symbol,
            'qty': qty,
            'estimated_notional': qty * current_price if current_price > 0 else 0,
            'current_price': current_price,
            'min_qty': min_qty,
            'min_notional': min_notional,
            'step_size': step_size,
            'reason': None
        }
        
        # Check 1: Quantity below minimum
        if qty < min_qty:
            details['reason'] = f"qty ({qty:.8f}) < minQty ({min_qty})"
            logger.debug(f"[DUST] {symbol}: {details['reason']}")
            return True, details
        
        # Check 2: Quantity rounds to zero after stepSize
        rounded_qty = self.round_quantity(symbol, qty)
        if rounded_qty is None or rounded_qty <= 0:
            details['reason'] = f"qty ({qty:.8f}) rounds to 0 with stepSize ({step_size})"
            details['rounded_qty'] = rounded_qty
            logger.debug(f"[DUST] {symbol}: {details['reason']}")
            return True, details
        
        # Check 3: Notional below minimum
        notional = qty * current_price
        if notional < min_notional:
            details['reason'] = f"notional (${notional:.4f}) < minNotional (${min_notional})"
            logger.debug(f"[DUST] {symbol}: {details['reason']}")
            return True, details
        
        # Not dust - can be sold
        return False, details
    
    def get_dust_status(
        self, 
        symbol: str, 
        qty: float, 
        current_price: float
    ) -> Dict:
        """
        Get complete dust status for UI display
        
        Returns dict with:
            - is_dust: bool
            - can_sell: bool
            - reason: str (only if dust)
            - details: dict
        """
        is_dust, details = self.is_dust_position(symbol, qty, current_price)
        
        return {
            'is_dust': is_dust,
            'can_sell': not is_dust,
            'reason': details.get('reason') if is_dust else None,
            'estimated_notional': details.get('estimated_notional', 0),
            'min_notional': details.get('min_notional', 1),
            'min_qty': details.get('min_qty', 0),
            'qty': qty,
            'current_price': current_price
        }


# Global instance
order_sizer = OrderSizer()
