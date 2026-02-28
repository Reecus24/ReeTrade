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
    
    def __init__(self):
        self.base_url = "https://api.mexc.com"
        self.api_key = os.environ.get('MEXC_API_KEY', '')
        self.api_secret = os.environ.get('MEXC_API_SECRET', '')
        self.timeout = httpx.Timeout(10.0, read=30.0)
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for private endpoints"""
        if not self.api_secret:
            raise ValueError("MEXC_API_SECRET not configured")
        
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        
        # Create signature
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
        headers = {"Content-Type": "application/json"}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API keys not configured for signed requests")
            
            params = params or {}
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
            headers['X-MEXC-APIKEY'] = self.api_key
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    response = await client.get(url, params=params, headers=headers)
                elif method == "POST":
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
        """Place a new order (requires API keys)"""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type
        }
        
        if quantity:
            params['quantity'] = str(quantity)
        if price:
            params['price'] = str(price)
        if quote_order_qty:
            params['quoteOrderQty'] = str(quote_order_qty)
        
        return await self._request("POST", "/api/v3/order", params=params, signed=True)
    
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
