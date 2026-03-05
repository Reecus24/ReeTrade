"""
MEXC Futures API Client
========================
Supports USDT-margined perpetual futures trading with:
- Isolated margin mode
- Leverage 2x-20x
- Long and Short positions
- Stop Loss and Take Profit orders
"""

import hmac
import hashlib
import time
import logging
import httpx
from typing import Optional, Dict, Any, List
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json

logger = logging.getLogger(__name__)


class MexcFuturesClient:
    """MEXC Futures API Client for USDT-margined perpetual contracts"""
    
    # MEXC Futures API Base URL - Updated 2026
    BASE_URL = "https://contract.mexc.com"
    
    # Side constants
    SIDE_OPEN_LONG = 1      # Open long position
    SIDE_CLOSE_SHORT = 2    # Close short position (buy to close)
    SIDE_OPEN_SHORT = 3     # Open short position
    SIDE_CLOSE_LONG = 4     # Close long position (sell to close)
    
    # Order types
    ORDER_TYPE_LIMIT = 1
    ORDER_TYPE_POST_ONLY = 2
    ORDER_TYPE_IOC = 3
    ORDER_TYPE_FOK = 4
    ORDER_TYPE_MARKET = 5   # Market order
    ORDER_TYPE_MARKET_IOC = 6
    
    # Position types
    POSITION_LONG = 1
    POSITION_SHORT = 2
    
    # Open types (margin mode)
    OPEN_TYPE_ISOLATED = 1
    OPEN_TYPE_CROSS = 2
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or os.environ.get('MEXC_API_KEY', '')
        self.api_secret = api_secret or os.environ.get('MEXC_API_SECRET', '')
        self.timeout = httpx.Timeout(10.0, read=30.0)
        self.recv_window = 5000
    
    def _generate_signature(self, timestamp: str, params_str: str) -> str:
        """
        Generate HMAC-SHA256 signature for MEXC Futures API
        Signature = HMAC-SHA256(api_secret, api_key + timestamp + params_string)
        """
        if not self.api_secret:
            raise ValueError("MEXC_API_SECRET not configured")
        
        # Build sign string: accessKey + timestamp + parameterString
        sign_str = self.api_key + timestamp + (params_str if params_str else "")
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _prepare_headers(self, timestamp: str, params_str: str) -> Dict[str, str]:
        """Prepare request headers with authentication"""
        signature = self._generate_signature(timestamp, params_str)
        
        return {
            "Content-Type": "application/json",
            "ApiKey": self.api_key,
            "Request-Time": timestamp,
            "Signature": signature,
            "Recv-Window": str(self.recv_window)
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make HTTP request to MEXC Futures API"""
        url = f"{self.BASE_URL}{endpoint}"
        timestamp = str(int(time.time() * 1000))
        headers = {"Content-Type": "application/json"}
        
        # Build params string
        if method == "GET":
            if params:
                # Sort params and build query string
                query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
            else:
                query_string = ""
            params_str = query_string
        else:
            # For POST, use JSON body
            params_str = json.dumps(params, separators=(',', ':')) if params else ""
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API keys not configured for signed requests")
            headers = self._prepare_headers(timestamp, params_str)
        
        # DEBUG: Log full request details
        logger.info(f"[FUTURES API] {method} {endpoint}")
        logger.info(f"[FUTURES API] URL: {url}")
        logger.info(f"[FUTURES API] Params string: '{params_str[:100] if params_str else ''}'")
        if signed:
            logger.info(f"[FUTURES API] Headers: ApiKey={self.api_key[:8]}..., Request-Time={timestamp}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    if params:
                        url = f"{url}?{params_str}"
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, content=params_str, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                # DEBUG: Log full response
                logger.info(f"[FUTURES API] Status: {response.status_code}")
                logger.info(f"[FUTURES API] Response: {response.text[:500] if response.text else 'EMPTY'}")
                
                # Check if response is empty
                if not response.text or response.text.strip() == "":
                    logger.error(f"[FUTURES API] EMPTY response from: {endpoint}")
                    return {"error": "Leere Antwort von MEXC Futures API - prüfe API-Key Futures Berechtigung"}
                
                try:
                    result = response.json()
                except Exception as json_err:
                    logger.error(f"[FUTURES API] JSON parse error: {json_err}")
                    # Check for common HTML error responses
                    if "Access Denied" in response.text or "403" in response.text:
                        return {"error": "Access Denied - API Key hat keine Futures Berechtigung oder IP nicht whitelisted"}
                    if "<html" in response.text.lower():
                        return {"error": "MEXC returned HTML error page - Server möglicherweise nicht erreichbar"}
                    return {"error": f"Invalid JSON: {response.text[:100]}"}
                
                # Check for API errors
                if isinstance(result, dict):
                    if result.get("success") is False:
                        error_code = result.get("code", "unknown")
                        error_msg = result.get("message", result.get("msg", "Unknown error"))
                        logger.error(f"[FUTURES API] Error: [{error_code}] {error_msg}")
                        return {"error": f"[{error_code}]: {error_msg}"}
                    
                    # Return data field if exists
                    return result.get("data", result)
                
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error(f"[FUTURES API] HTTP error {e.response.status_code}: {e.response.text}")
            return {"error": f"HTTP {e.response.status_code}"}
        except httpx.ConnectError as e:
            logger.error(f"[FUTURES API] Connection error: {e}")
            return {"error": "Verbindung zu MEXC Futures fehlgeschlagen - Server nicht erreichbar"}
        except Exception as e:
            logger.error(f"[FUTURES API] Request error: {e}")
            return {"error": str(e)}
    
    # ============ PUBLIC ENDPOINTS ============
    
    async def test_connectivity(self) -> Dict[str, Any]:
        """Test if MEXC Futures API is reachable (no authentication needed)"""
        try:
            result = await self._request("GET", "/api/v1/contract/ping")
            if isinstance(result, dict) and result.get("error"):
                return {"reachable": False, "error": result.get("error")}
            return {"reachable": True, "server_time": result.get("serverTime")}
        except Exception as e:
            return {"reachable": False, "error": str(e)}
    
    async def get_server_time(self) -> int:
        """Get MEXC server time"""
        result = await self._request("GET", "/api/v1/contract/ping")
        return result.get("serverTime", int(time.time() * 1000))
    
    async def get_contract_detail(self, symbol: str) -> Dict[str, Any]:
        """Get contract details for a symbol"""
        result = await self._request("GET", "/api/v1/contract/detail", {"symbol": symbol})
        return result
    
    async def get_all_contracts(self) -> List[Dict]:
        """Get all available futures contracts"""
        try:
            result = await self._request("GET", "/api/v1/contract/detail")
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # Sometimes the API returns {data: [...]}
                return result.get('data', [])
            return []
        except Exception as e:
            logger.error(f"get_all_contracts error: {e}")
            return []
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker data for a symbol"""
        result = await self._request("GET", "/api/v1/contract/ticker", {"symbol": symbol})
        return result
    
    async def get_index_price(self, symbol: str) -> Dict[str, Any]:
        """Get index price for a symbol"""
        result = await self._request("GET", f"/api/v1/contract/index_price/{symbol}")
        return result
    
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get current funding rate for a symbol"""
        result = await self._request("GET", f"/api/v1/contract/funding_rate/{symbol}")
        return result
    
    async def get_klines(self, symbol: str, interval: str = "Min15", limit: int = 500) -> List[List]:
        """
        Get kline/candlestick data for futures
        Intervals: Min1, Min5, Min15, Min30, Min60, Hour4, Hour8, Day1, Week1, Month1
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 2000)
        }
        result = await self._request("GET", "/api/v1/contract/kline", params)
        return result.get("data", []) if isinstance(result, dict) else result
    
    # ============ PRIVATE ENDPOINTS (Account) ============
    
    async def get_account_assets(self) -> Dict[str, Any]:
        """Get futures account assets (USDT balance, etc.)"""
        result = await self._request("GET", "/api/v1/private/account/assets", signed=True)
        if isinstance(result, dict) and result.get('error'):
            return result
        return result if result else {}
    
    async def get_account_asset(self, currency: str = "USDT") -> Dict[str, Any]:
        """Get specific asset balance"""
        result = await self._request(
            "GET", 
            "/api/v1/private/account/asset",
            {"currency": currency},
            signed=True
        )
        
        # Check for error in result
        if isinstance(result, dict) and result.get('error'):
            return {"availableBalance": 0, "frozenBalance": 0, "equity": 0, "error": result.get('error')}
        
        # Handle different response formats
        if isinstance(result, dict):
            return result
        
        return {"availableBalance": 0, "frozenBalance": 0, "equity": 0}
    
    # ============ PRIVATE ENDPOINTS (Positions) ============
    
    async def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open positions or positions for a specific symbol"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        result = await self._request(
            "GET",
            "/api/v1/private/position/open_positions",
            params if params else None,
            signed=True
        )
        
        # Check for error
        if isinstance(result, dict) and result.get('error'):
            logger.warning(f"get_open_positions error: {result.get('error')}")
            return []
        
        return result if isinstance(result, list) else []
    
    async def get_position_leverage(self, symbol: str) -> Dict[str, Any]:
        """Get leverage settings for a symbol"""
        result = await self._request(
            "GET",
            "/api/v1/private/position/leverage",
            {"symbol": symbol},
            signed=True
        )
        return result
    
    async def set_leverage(
        self,
        symbol: str,
        leverage: int,
        open_type: int = OPEN_TYPE_ISOLATED,
        position_type: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Set leverage for a symbol
        
        Args:
            symbol: Trading pair (e.g., BTC_USDT)
            leverage: Leverage multiplier (1-125 depending on symbol)
            open_type: 1=isolated, 2=cross
            position_type: 1=long, 2=short (optional, sets both if not specified)
        """
        params = {
            "symbol": symbol,
            "leverage": leverage,
            "openType": open_type
        }
        if position_type:
            params["positionType"] = position_type
        
        result = await self._request(
            "POST",
            "/api/v1/private/position/change_leverage",
            params,
            signed=True
        )
        return result
    
    # ============ PRIVATE ENDPOINTS (Orders) ============
    
    async def place_order(
        self,
        symbol: str,
        side: int,
        vol: float,
        leverage: int,
        order_type: int = ORDER_TYPE_MARKET,
        price: Optional[float] = None,
        open_type: int = OPEN_TYPE_ISOLATED,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        external_oid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a futures order
        
        Args:
            symbol: Trading pair (e.g., BTC_USDT)
            side: 1=open_long, 2=close_short, 3=open_short, 4=close_long
            vol: Order quantity (number of contracts)
            leverage: Leverage multiplier
            order_type: 1=limit, 5=market, etc.
            price: Limit price (required for limit orders)
            open_type: 1=isolated, 2=cross
            stop_loss_price: Stop loss trigger price
            take_profit_price: Take profit trigger price
            external_oid: External order ID for tracking
        """
        params = {
            "symbol": symbol,
            "side": side,
            "vol": vol,
            "leverage": leverage,
            "type": order_type,
            "openType": open_type
        }
        
        if price and order_type != self.ORDER_TYPE_MARKET:
            params["price"] = price
        
        if stop_loss_price:
            params["stopLossPrice"] = stop_loss_price
        
        if take_profit_price:
            params["takeProfitPrice"] = take_profit_price
        
        if external_oid:
            params["externalOid"] = external_oid
        
        result = await self._request(
            "POST",
            "/api/v1/private/order/submit",
            params,
            signed=True
        )
        return result
    
    async def open_long(
        self,
        symbol: str,
        quantity: float,
        leverage: int,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Convenience method to open a long position"""
        return await self.place_order(
            symbol=symbol,
            side=self.SIDE_OPEN_LONG,
            vol=quantity,
            leverage=leverage,
            order_type=self.ORDER_TYPE_MARKET,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price
        )
    
    async def open_short(
        self,
        symbol: str,
        quantity: float,
        leverage: int,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Convenience method to open a short position"""
        return await self.place_order(
            symbol=symbol,
            side=self.SIDE_OPEN_SHORT,
            vol=quantity,
            leverage=leverage,
            order_type=self.ORDER_TYPE_MARKET,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price
        )
    
    async def close_long(
        self,
        symbol: str,
        quantity: float
    ) -> Dict[str, Any]:
        """Convenience method to close a long position"""
        # Get current leverage from position
        positions = await self.get_open_positions(symbol)
        leverage = 10  # Default
        for pos in positions:
            if pos.get("positionType") == self.POSITION_LONG:
                leverage = pos.get("leverage", 10)
                break
        
        return await self.place_order(
            symbol=symbol,
            side=self.SIDE_CLOSE_LONG,
            vol=quantity,
            leverage=leverage,
            order_type=self.ORDER_TYPE_MARKET
        )
    
    async def close_short(
        self,
        symbol: str,
        quantity: float
    ) -> Dict[str, Any]:
        """Convenience method to close a short position"""
        # Get current leverage from position
        positions = await self.get_open_positions(symbol)
        leverage = 10  # Default
        for pos in positions:
            if pos.get("positionType") == self.POSITION_SHORT:
                leverage = pos.get("leverage", 10)
                break
        
        return await self.place_order(
            symbol=symbol,
            side=self.SIDE_CLOSE_SHORT,
            vol=quantity,
            leverage=leverage,
            order_type=self.ORDER_TYPE_MARKET
        )
    
    async def close_all_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Close all open positions for a symbol or all symbols"""
        positions = await self.get_open_positions(symbol)
        results = []
        
        for pos in positions:
            pos_symbol = pos.get("symbol")
            pos_type = pos.get("positionType")
            quantity = pos.get("holdVol", 0)
            
            if quantity > 0:
                try:
                    if pos_type == self.POSITION_LONG:
                        result = await self.close_long(pos_symbol, quantity)
                    else:
                        result = await self.close_short(pos_symbol, quantity)
                    results.append({"symbol": pos_symbol, "success": True, "result": result})
                except Exception as e:
                    results.append({"symbol": pos_symbol, "success": False, "error": str(e)})
        
        return results
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an open order"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request(
            "POST",
            "/api/v1/private/order/cancel",
            params,
            signed=True
        )
    
    async def cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel all open orders for a symbol"""
        params = {"symbol": symbol}
        return await self._request(
            "POST",
            "/api/v1/private/order/cancel_all",
            params,
            signed=True
        )
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        result = await self._request(
            "GET",
            "/api/v1/private/order/open_orders",
            params if params else None,
            signed=True
        )
        return result if isinstance(result, list) else []
    
    async def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order details"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request(
            "GET",
            "/api/v1/private/order/get",
            params,
            signed=True
        )
    
    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        page_num: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Get order history"""
        params = {
            "page_num": page_num,
            "page_size": min(page_size, 100)
        }
        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        
        return await self._request(
            "GET",
            "/api/v1/private/order/history_orders",
            params,
            signed=True
        )
    
    # ============ HELPER METHODS ============
    
    def convert_spot_symbol_to_futures(self, spot_symbol: str) -> str:
        """Convert SPOT symbol format to Futures format (BTCUSDT -> BTC_USDT)"""
        if "_" in spot_symbol:
            return spot_symbol
        
        # Handle common quote currencies
        for quote in ["USDT", "USDC", "BTC", "ETH"]:
            if spot_symbol.endswith(quote):
                base = spot_symbol[:-len(quote)]
                return f"{base}_{quote}"
        
        return spot_symbol
    
    def convert_futures_symbol_to_spot(self, futures_symbol: str) -> str:
        """Convert Futures symbol format to SPOT format (BTC_USDT -> BTCUSDT)"""
        return futures_symbol.replace("_", "")
    
    async def get_available_futures_pairs(self, quote: str = "USDT") -> List[str]:
        """Get list of available futures pairs for a quote currency"""
        contracts = await self.get_all_contracts()
        pairs = []
        
        for contract in contracts:
            symbol = contract.get("symbol", "")
            if symbol.endswith(f"_{quote}"):
                pairs.append(symbol)
        
        return sorted(pairs)
    
    def calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: int,
        is_long: bool,
        maintenance_margin_rate: float = 0.005  # 0.5% default
    ) -> float:
        """
        Calculate estimated liquidation price
        
        For Long: Liquidation = Entry * (1 - 1/Leverage + maintenance_margin_rate)
        For Short: Liquidation = Entry * (1 + 1/Leverage - maintenance_margin_rate)
        """
        if is_long:
            liq_price = entry_price * (1 - 1/leverage + maintenance_margin_rate)
        else:
            liq_price = entry_price * (1 + 1/leverage - maintenance_margin_rate)
        
        return round(liq_price, 8)
    
    def calculate_position_size(
        self,
        usdt_amount: float,
        entry_price: float,
        leverage: int
    ) -> float:
        """Calculate position size (contracts) based on USDT amount and leverage"""
        # Position value = USDT * leverage
        # Contracts = Position value / entry_price
        position_value = usdt_amount * leverage
        contracts = position_value / entry_price
        return round(contracts, 8)
    
    def calculate_margin_required(
        self,
        quantity: float,
        entry_price: float,
        leverage: int
    ) -> float:
        """Calculate required margin for a position"""
        position_value = quantity * entry_price
        margin = position_value / leverage
        return round(margin, 4)
    
    def calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        quantity: float,
        is_long: bool
    ) -> float:
        """Calculate PnL for a futures position"""
        if is_long:
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        return round(pnl, 4)
    
    def calculate_roe(
        self,
        entry_price: float,
        current_price: float,
        leverage: int,
        is_long: bool
    ) -> float:
        """
        Calculate Return on Equity (ROE) percentage
        ROE = PnL% * Leverage
        """
        if is_long:
            price_change_pct = (current_price - entry_price) / entry_price
        else:
            price_change_pct = (entry_price - current_price) / entry_price
        
        roe = price_change_pct * leverage * 100
        return round(roe, 2)
