import httpx
import hmac
import hashlib
import time
import logging
from typing import Optional, Dict, Any, List
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class MexcClient:
    """MEXC API Client for Public and Private endpoints"""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.base_url = "https://api.mexc.com"
        # Use provided keys or fall back to env vars
        self.api_key = api_key or os.environ.get('MEXC_API_KEY', '')
        self.api_secret = api_secret or os.environ.get('MEXC_API_SECRET', '')
        self.timeout = httpx.Timeout(10.0, read=30.0)
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for private endpoints
        
        MEXC requires the signature to be calculated from the query string
        in the SAME ORDER as the parameters will be sent.
        """
        if not self.api_secret:
            raise ValueError("MEXC_API_SECRET not configured")
        
        # Build query string in the order parameters were added (NOT sorted)
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        
        # Create signature (lowercase hexdigest)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API keys not configured for signed requests")
            
            params = params or {}
            params['timestamp'] = int(time.time() * 1000)
            
            # Calculate signature from params WITHOUT signature field
            signature = self._generate_signature(params)
            params['signature'] = signature
            
            headers['X-MEXC-APIKEY'] = self.api_key
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    response = await client.get(url, params=params, headers=headers)
                elif method == "POST":
                    # MEXC requires params as query string for signed POST requests
                    if signed:
                        response = await client.post(url, params=params, headers=headers)
                    else:
                        headers["Content-Type"] = "application/json"
                        response = await client.post(url, json=params, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, params=params, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    # PUBLIC ENDPOINTS
    
    async def get_server_time(self) -> int:
        """Get MEXC server time in milliseconds"""
        result = await self._request("GET", "/api/v3/time")
        return result.get('serverTime', 0)
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange trading rules and symbol information"""
        return await self._request("GET", "/api/v3/exchangeInfo")
    
    async def get_ticker_24h(self, symbol: Optional[str] = None) -> Any:
        """Get 24h ticker price change statistics"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return await self._request("GET", "/api/v3/ticker/24hr", params=params)
    
    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 500) -> List[List]:
        """Get kline/candlestick data"""
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000)
        }
        return await self._request("GET", "/api/v3/klines", params=params)
    
    async def get_top_pairs(self, quote: str = "USDT", limit: int = 20) -> List[str]:
        """Get top trading pairs by 24h volume"""
        tickers = await self.get_ticker_24h()
        
        # Filter USDT pairs
        usdt_pairs = [
            t for t in tickers 
            if isinstance(t, dict) and t.get('symbol', '').endswith(quote)
        ]
        
        # Sort by quoteVolume
        usdt_pairs.sort(
            key=lambda x: float(x.get('quoteVolume', 0)), 
            reverse=True
        )
        
        # Return top N symbols
        return [p['symbol'] for p in usdt_pairs[:limit]]
    
    async def get_momentum_universe(self, quote: str = "USDT", base_limit: int = 50) -> List[Dict]:
        """Get momentum-scored universe
        
        Returns list of dicts with: symbol, score, return_24h, return_4h, quoteVolume
        """
        # Get top 50 by volume as base universe
        tickers = await self.get_ticker_24h()
        
        usdt_pairs = [
            t for t in tickers 
            if isinstance(t, dict) and t.get('symbol', '').endswith(quote)
        ]
        
        # Sort by volume and take top 50
        usdt_pairs.sort(
            key=lambda x: float(x.get('quoteVolume', 0)), 
            reverse=True
        )
        base_universe = usdt_pairs[:base_limit]
        
        # Calculate momentum scores
        momentum_pairs = []
        for ticker in base_universe:
            try:
                symbol = ticker['symbol']
                
                # Get 24h and 4h returns from ticker
                price_change_pct = float(ticker.get('priceChangePercent', 0))
                
                # Get 4H candles for 4h return
                klines_4h = await self.get_klines(symbol, interval="4h", limit=2)
                if len(klines_4h) >= 2:
                    price_4h_ago = float(klines_4h[-2][4])  # Close price 4h ago
                    current_price = float(klines_4h[-1][4])  # Current close
                    return_4h = ((current_price - price_4h_ago) / price_4h_ago) * 100
                else:
                    return_4h = 0
                
                # Momentum score: 0.6 * return_24h + 0.4 * return_4h
                momentum_score = (0.6 * price_change_pct) + (0.4 * return_4h)
                
                momentum_pairs.append({
                    'symbol': symbol,
                    'score': momentum_score,
                    'return_24h': price_change_pct,
                    'return_4h': return_4h,
                    'quoteVolume': float(ticker.get('quoteVolume', 0)),
                    'price': current_price if len(klines_4h) >= 2 else float(ticker.get('lastPrice', 0))
                })
            except Exception as e:
                logger.warning(f"Error calculating momentum for {symbol}: {e}")
                continue
        
        # Sort by momentum score descending
        momentum_pairs.sort(key=lambda x: x['score'], reverse=True)
        
        return momentum_pairs
    
    # PRIVATE ENDPOINTS (for Live mode)
    
    async def get_account(self) -> Dict[str, Any]:
        """Get account information (requires API keys)"""
        return await self._request("GET", "/api/v3/account", signed=True)
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        quote_order_qty: Optional[float] = None
    ) -> Dict[str, Any]:
        """Place a new order (requires API keys)
        
        Order of parameters matters for MEXC signature!
        For MARKET orders, we query the order status to get actual execution price.
        """
        # Use ordered dict to maintain parameter order
        from collections import OrderedDict
        params = OrderedDict()
        
        params["symbol"] = symbol
        params["side"] = side
        params["type"] = order_type
        
        if quantity:
            params['quantity'] = str(quantity)
        if price:
            params['price'] = str(price)
        if quote_order_qty:
            params['quoteOrderQty'] = str(quote_order_qty)
        
        result = await self._request("POST", "/api/v3/order", params=dict(params), signed=True)
        
        # For MARKET orders, query the order to get actual execution details
        if order_type == "MARKET" and result.get('orderId'):
            try:
                import asyncio
                await asyncio.sleep(0.5)  # Wait for order to fully execute
                order_details = await self.get_order(symbol, str(result['orderId']))
                
                # Merge execution details into result
                if order_details.get('cummulativeQuoteQty'):
                    result['cummulativeQuoteQty'] = order_details['cummulativeQuoteQty']
                if order_details.get('executedQty'):
                    result['executedQty'] = order_details['executedQty']
                if order_details.get('price') and order_details.get('price') != '0':
                    result['price'] = order_details['price']
                    
                logger.info(f"[MEXC] Order {result['orderId']} details: qty={result.get('executedQty')}, quoteQty={result.get('cummulativeQuoteQty')}")
            except Exception as e:
                logger.warning(f"[MEXC] Could not fetch order details: {e}")
        
        return result
    
    async def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Query order status (requires API keys)"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request("GET", "/api/v3/order", params=params, signed=True)
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an active order (requires API keys)"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request("DELETE", "/api/v3/order", params=params, signed=True)
    
    async def get_my_trades(self, symbol: str, limit: int = 500, start_time: int = None, end_time: int = None) -> List[Dict[str, Any]]:
        """Get recent trades for a symbol (requires API keys)
        
        Returns list of executed trades (fills) for the symbol.
        Used for syncing positions with MEXC trade history.
        """
        params = {
            "symbol": symbol,
            "limit": min(limit, 1000)
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        return await self._request("GET", "/api/v3/myTrades", params=params, signed=True)
    
    async def get_all_my_recent_trades(self, symbols: List[str], limit_per_symbol: int = 50) -> Dict[str, List[Dict]]:
        """Get recent trades for multiple symbols
        
        Returns dict: {symbol: [trades]}
        """
        all_trades = {}
        for symbol in symbols:
            try:
                trades = await self.get_my_trades(symbol, limit=limit_per_symbol)
                all_trades[symbol] = trades
            except Exception as e:
                logger.warning(f"Could not fetch trades for {symbol}: {e}")
                all_trades[symbol] = []
        return all_trades
