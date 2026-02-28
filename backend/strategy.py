import numpy as np
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class TradingStrategy:
    """EMA Crossover + RSI Filter Strategy"""
    
    def __init__(self, ema_fast: int = 50, ema_slow: int = 200, rsi_period: int = 14, 
                 rsi_min: int = 50, rsi_overbought: int = 75):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_min = rsi_min
        self.rsi_overbought = rsi_overbought
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
        
        prices_array = np.array(prices)
        ema = prices_array[:period].mean()  # Start with SMA
        
        multiplier = 2 / (period + 1)
        for price in prices_array[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return float(ema)
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return None
        
        prices_array = np.array(prices)
        deltas = np.diff(prices_array)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = gains[-period:].mean()
        avg_loss = losses[-period:].mean()
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def generate_signal(self, klines: List[List]) -> Tuple[str, dict]:
        """Generate trading signal from kline data
        
        Returns:
            Tuple of (signal, context)
            signal: 'LONG', 'FLAT', 'CLOSE'
            context: dict with indicator values
        """
        if len(klines) < self.ema_slow:
            return 'FLAT', {'error': 'Not enough data'}
        
        # Extract close prices (index 4 in kline array)
        close_prices = [float(k[4]) for k in klines]
        
        # Calculate indicators
        ema_fast_val = self.calculate_ema(close_prices, self.ema_fast)
        ema_slow_val = self.calculate_ema(close_prices, self.ema_slow)
        rsi_val = self.calculate_rsi(close_prices, self.rsi_period)
        
        if ema_fast_val is None or ema_slow_val is None or rsi_val is None:
            return 'FLAT', {'error': 'Indicator calculation failed'}
        
        context = {
            'ema_fast': round(ema_fast_val, 2),
            'ema_slow': round(ema_slow_val, 2),
            'rsi': round(rsi_val, 2),
            'current_price': close_prices[-1]
        }
        
        # Signal logic:
        # LONG: EMA fast > EMA slow AND RSI > rsi_min AND RSI < rsi_overbought
        if ema_fast_val > ema_slow_val:
            if rsi_val > self.rsi_min and rsi_val < self.rsi_overbought:
                return 'LONG', context
            elif rsi_val >= self.rsi_overbought:
                context['reason'] = 'RSI overbought'
                return 'FLAT', context
        
        # CLOSE: EMA fast crosses below EMA slow (bearish)
        if ema_fast_val < ema_slow_val:
            context['reason'] = 'Bearish crossover'
            return 'CLOSE', context
        
        return 'FLAT', context
    
    def calculate_atr(self, klines: List[List], period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        if len(klines) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(klines)):
            high = float(klines[i][2])
            low = float(klines[i][3])
            prev_close = float(klines[i-1][4])
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        atr = np.array(true_ranges[-period:]).mean()
        return float(atr)
