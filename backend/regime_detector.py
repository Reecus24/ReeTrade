import numpy as np
from typing import Tuple, Optional, List
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RegimeDetector:
    # Market regime detection using EMA, ADX
    
    def __init__(self):
        pass
    
    def calculate_adx(self, klines: List[List], period: int = 14) -> Optional[float]:
        # Calculate Average Directional Index
        if len(klines) < period + 1:
            return None
        
        # Extract OHLC
        highs = np.array([float(k[2]) for k in klines])
        lows = np.array([float(k[3]) for k in klines])
        closes = np.array([float(k[4]) for k in klines])
        
        # True Range
        tr_list = []
        for i in range(1, len(klines)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr = max(high_low, high_close, low_close)
            tr_list.append(tr)
        
        tr_array = np.array(tr_list)
        
        # +DM and -DM
        plus_dm = []
        minus_dm = []
        for i in range(1, len(highs)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        plus_dm = np.array(plus_dm)
        minus_dm = np.array(minus_dm)
        
        # Smoothed TR, +DM, -DM
        atr = tr_array[-period:].mean()
        plus_di = (plus_dm[-period:].mean() / atr) * 100 if atr > 0 else 0
        minus_di = (minus_dm[-period:].mean() / atr) * 100 if atr > 0 else 0
        
        # ADX calculation
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
        
        # Simple ADX (not smoothed for simplicity)
        adx = dx
        
        return float(adx)
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        # Calculate Exponential Moving Average
        if len(prices) < period:
            return None
        
        prices_array = np.array(prices)
        ema = prices_array[:period].mean()
        
        multiplier = 2 / (period + 1)
        for price in prices_array[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return float(ema)
    
    def detect_regime(self, klines_4h: List[List]) -> Tuple[str, dict]:
        # Detect market regime from 4H candles
        # Returns: (regime, context)
        # regime: BULLISH, SIDEWAYS, BEARISH
        
        if len(klines_4h) < 200:
            return 'UNKNOWN', {'error': 'Not enough 4H data'}
        
        close_prices = [float(k[4]) for k in klines_4h]
        current_price = close_prices[-1]
        
        # Calculate EMAs
        ema50 = self.calculate_ema(close_prices, 50)
        ema200 = self.calculate_ema(close_prices, 200)
        
        # Calculate ADX
        adx = self.calculate_adx(klines_4h, 14)
        
        if ema50 is None or ema200 is None or adx is None:
            return 'UNKNOWN', {'error': 'Indicator calculation failed'}
        
        context = {
            'ema50': round(ema50, 2),
            'ema200': round(ema200, 2),
            'adx': round(adx, 2),
            'price': round(current_price, 2)
        }
        
        # Regime detection logic
        if ema50 > ema200 and current_price > ema200 and adx > 22:
            return 'BULLISH', context
        elif adx < 20:
            return 'SIDEWAYS', context
        elif ema50 < ema200 and current_price < ema200:
            return 'BEARISH', context
        else:
            return 'SIDEWAYS', context  # Default to sideways if ambiguous
