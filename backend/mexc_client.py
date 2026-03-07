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
                
                # Check for HTTP errors and include response body in error
                if response.status_code >= 400:
                    error_body = response.text
                    logger.error(f"[MEXC] HTTP {response.status_code} for {endpoint}: {error_body}")
                    # Create custom exception with response body
                    error = httpx.HTTPStatusError(
                        f"{response.status_code}: {error_body}", 
                        request=response.request, 
                        response=response
                    )
                    error.response_body = error_body  # Attach body for caller access
                    raise error
                
                return response.json()
        except httpx.HTTPStatusError as e:
            # Already logged above, just re-raise
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
    
    async def get_orderbook(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Get orderbook depth (Top N levels)
        
        Returns:
            {
                'bids': [[price, qty], ...],  # Sorted descending (best bid first)
                'asks': [[price, qty], ...],  # Sorted ascending (best ask first)
                'lastUpdateId': int
            }
        """
        params = {
            "symbol": symbol,
            "limit": min(limit, 100)  # MEXC supports up to 100
        }
        return await self._request("GET", "/api/v3/depth", params=params)
    
    async def get_orderbook_snapshot(self, symbol: str, levels: int = 5) -> Dict[str, Any]:
        """Get processed orderbook snapshot with aggregated features
        
        Returns:
            {
                'symbol': str,
                'timestamp': int (ms),
                'best_bid_price': float,
                'best_ask_price': float,
                'spread_abs': float,  # Absolute spread
                'spread_pct': float,  # Spread as percentage of mid_price
                'mid_price': float,
                'top5_bids': [{'price': float, 'qty': float}, ...],
                'top5_asks': [{'price': float, 'qty': float}, ...],
                'bid_volume_sum': float,
                'ask_volume_sum': float,
                'orderbook_imbalance': float,  # bid_vol / ask_vol
                'is_valid': bool  # Plausibility check passed
            }
            
        Returns None if orderbook is invalid (ask <= bid, spread <= 0)
        """
        try:
            raw = await self.get_orderbook(symbol, limit=levels)
            
            bids = raw.get('bids', [])
            asks = raw.get('asks', [])
            
            if not bids or not asks:
                logger.warning(f"[Orderbook] {symbol}: Empty bids or asks")
                return None
            
            # Parse bids and asks
            top_bids = [{'price': float(b[0]), 'qty': float(b[1])} for b in bids[:levels]]
            top_asks = [{'price': float(a[0]), 'qty': float(a[1])} for a in asks[:levels]]
            
            best_bid = top_bids[0]['price'] if top_bids else 0
            best_ask = top_asks[0]['price'] if top_asks else 0
            
            # ============ P0 FIX: PLAUSIBILITY CHECKS ============
            # Check 1: Ask must be > Bid
            if best_ask <= best_bid:
                logger.warning(f"[Orderbook] {symbol}: INVALID ask({best_ask}) <= bid({best_bid}) - discarding")
                return None
            
            # Check 2: Both prices must be positive
            if best_bid <= 0 or best_ask <= 0:
                logger.warning(f"[Orderbook] {symbol}: INVALID prices bid={best_bid}, ask={best_ask}")
                return None
            
            # Calculate spread
            spread_abs = best_ask - best_bid
            mid_price = (best_bid + best_ask) / 2
            
            # Check 3: Spread must be positive
            if spread_abs <= 0:
                logger.warning(f"[Orderbook] {symbol}: INVALID spread_abs={spread_abs} <= 0")
                return None
            
            # Calculate spread percentage correctly
            spread_pct = (spread_abs / mid_price) * 100 if mid_price > 0 else 0
            
            bid_volume_sum = sum(b['qty'] for b in top_bids)
            ask_volume_sum = sum(a['qty'] for a in top_asks)
            
            # Orderbook imbalance: > 1 = more buying pressure, < 1 = more selling pressure
            epsilon = 0.0001
            orderbook_imbalance = bid_volume_sum / max(ask_volume_sum, epsilon)
            
            # Log for debugging (every 100th call or on issues)
            logger.debug(
                f"[Orderbook] {symbol}: "
                f"bid={best_bid:.8f}, ask={best_ask:.8f}, "
                f"spread_abs={spread_abs:.8f}, spread_pct={spread_pct:.6f}%, "
                f"mid={mid_price:.8f}, imbalance={orderbook_imbalance:.2f}"
            )
            
            return {
                'symbol': symbol,
                'timestamp': int(time.time() * 1000),
                'best_bid_price': best_bid,
                'best_ask_price': best_ask,
                'spread_abs': spread_abs,
                'spread_pct': spread_pct,
                'mid_price': mid_price,
                'top5_bids': top_bids,
                'top5_asks': top_asks,
                'bid_volume_sum': bid_volume_sum,
                'ask_volume_sum': ask_volume_sum,
                'orderbook_imbalance': orderbook_imbalance,
                'is_valid': True
            }
        except Exception as e:
            logger.warning(f"[Orderbook] {symbol}: Error - {e}")
            return None
    
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
    
    async def get_momentum_universe(self, quote: str = "USDT", base_limit: int = 50, 
                                      curated_list: List[str] = None,
                                      min_preferred_coins: int = 10) -> Dict:
        """Get FULL USDT Universe with dynamic filtering
        
        NEUES SYSTEM - VOLLSTÄNDIGES UNIVERSE:
        
        1. FULL UNIVERSE: Alle verfügbaren MEXC Spot USDT-Paare laden
        
        2. FILTER LAYER:
           - Volume Filter: Min 24h Volume
           - Spread Filter: Max Spread
           - Blacklist: Bekannte Problem-Coins ausschließen
        
        3. TIER SYSTEM:
           - PREFERRED: Volume > 5M, Spread < 0.20%
           - STANDARD: Volume > 2M, Spread < 0.35%
           - FALLBACK: Volume > 500K, Spread < 0.50%
        
        Returns dict with:
          - pairs: List of tradeable pairs with metadata
          - stats: Filtering statistics for transparency
        """
        # ═══════════════════════════════════════════════════════════════════════════
        # FILTER THRESHOLDS - 3 TIER SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════
        PREFERRED_MIN_VOLUME = 5_000_000   # 5M USDT
        PREFERRED_MAX_SPREAD = 0.20        # 0.20%
        
        STANDARD_MIN_VOLUME = 2_000_000    # 2M USDT
        STANDARD_MAX_SPREAD = 0.35         # 0.35%
        
        FALLBACK_MIN_VOLUME = 500_000      # 500K USDT
        FALLBACK_MAX_SPREAD = 0.50         # 0.50%
        
        # ═══════════════════════════════════════════════════════════════════════════
        # BLACKLIST - Bekannte Problem-Coins
        # ═══════════════════════════════════════════════════════════════════════════
        BLACKLIST = {
            # Stablecoins - keine Volatilität
            "USDCUSDT", "TUSDUSDT", "DAIUSDT", "FDUSDUSDT", "USDPUSDT", "EURUSDT", "GBPUSDT",
            # Leveraged Tokens
            "BTCUPUSDT", "BTCDOWNUSDT", "ETHUPUSDT", "ETHDOWNUSDT",
            # Bekannte Problem-Coins (Delisting-Risiko, extreme Spreads)
            "LUNAUSDT", "USTCUSDT", "FTTUSDT",
        }
        
        # Tracking für Statistiken
        filter_stats = {
            'total_usdt_pairs': 0,
            'filtered_blacklist': 0,
            'filtered_volume': 0,
            'filtered_spread': 0,
            'filtered_price_zero': 0,
            'preferred_count': 0,
            'standard_count': 0,
            'fallback_count': 0,
            'final_tradeable': 0,
        }
        
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 1: LADE ALLE USDT PAARE VON MEXC
        # ═══════════════════════════════════════════════════════════════════════════
        tickers = await self.get_ticker_24h()
        
        usdt_pairs = [
            t for t in tickers 
            if isinstance(t, dict) and t.get('symbol', '').endswith(quote)
            and not t.get('symbol', '').endswith('3LUSDT')  # No leveraged 3x
            and not t.get('symbol', '').endswith('3SUSDT')  # No leveraged 3x short
        ]
        
        filter_stats['total_usdt_pairs'] = len(usdt_pairs)
        logger.info(f"[UNIVERSE] 📊 Gesamt USDT-Paare auf MEXC: {len(usdt_pairs)}")
        
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 2: FILTER & TIER ZUORDNUNG
        # ═══════════════════════════════════════════════════════════════════════════
        preferred_pairs = []
        standard_pairs = []
        fallback_pairs = []
        
        for ticker in usdt_pairs:
            try:
                symbol = ticker.get('symbol', 'UNKNOWN')
                
                # Blacklist Check
                if symbol in BLACKLIST:
                    filter_stats['filtered_blacklist'] += 1
                    continue
                
                volume_24h = float(ticker.get('quoteVolume', 0))
                last_price = float(ticker.get('lastPrice', 0))
                
                # Preis-Check (muss > 0 sein)
                if last_price <= 0:
                    filter_stats['filtered_price_zero'] += 1
                    continue
                
                # Volume Check (Minimum für alle Tiers)
                if volume_24h < FALLBACK_MIN_VOLUME:
                    filter_stats['filtered_volume'] += 1
                    continue
                
                # Calculate spread from bid/ask
                bid = float(ticker.get('bidPrice', 0))
                ask = float(ticker.get('askPrice', 0))
                
                if bid > 0 and ask > 0 and last_price > 0:
                    spread_pct = ((ask - bid) / last_price) * 100
                else:
                    # Fallback: Schätze Spread basierend auf Volumen
                    spread_pct = max(0.05, 1.0 / (volume_24h / 1_000_000 + 1))
                
                # Spread Check (Maximum für alle Tiers)
                if spread_pct > FALLBACK_MAX_SPREAD:
                    filter_stats['filtered_spread'] += 1
                    continue
                
                # Füge Metadata hinzu
                ticker['spread_pct'] = spread_pct
                ticker['volume_24h'] = volume_24h
                ticker['price'] = last_price
                
                # TIER ZUORDNUNG
                if volume_24h >= PREFERRED_MIN_VOLUME and spread_pct <= PREFERRED_MAX_SPREAD:
                    ticker['tier'] = 'preferred'
                    preferred_pairs.append(ticker)
                    filter_stats['preferred_count'] += 1
                elif volume_24h >= STANDARD_MIN_VOLUME and spread_pct <= STANDARD_MAX_SPREAD:
                    ticker['tier'] = 'standard'
                    standard_pairs.append(ticker)
                    filter_stats['standard_count'] += 1
                else:
                    ticker['tier'] = 'fallback'
                    fallback_pairs.append(ticker)
                    filter_stats['fallback_count'] += 1
                    
            except Exception as e:
                logger.warning(f"Error filtering {ticker.get('symbol')}: {e}")
                continue
        
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 3: KOMBINIERE TIERS (Preferred > Standard > Fallback)
        # ═══════════════════════════════════════════════════════════════════════════
        # Sortiere jedes Tier nach Volumen
        preferred_pairs.sort(key=lambda x: x.get('volume_24h', 0), reverse=True)
        standard_pairs.sort(key=lambda x: x.get('volume_24h', 0), reverse=True)
        fallback_pairs.sort(key=lambda x: x.get('volume_24h', 0), reverse=True)
        
        # Kombiniere: Preferred zuerst, dann Standard, dann Fallback
        all_tradeable = preferred_pairs + standard_pairs + fallback_pairs
        filter_stats['final_tradeable'] = len(all_tradeable)
        
        # Limit to base_limit
        base_universe = all_tradeable[:base_limit]
        
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 4: BERECHNE MOMENTUM SCORES
        # ═══════════════════════════════════════════════════════════════════════════
        momentum_pairs = []
        for ticker in base_universe:
            try:
                symbol = ticker['symbol']
                price_change_pct = float(ticker.get('priceChangePercent', 0))
                
                # 4H Return berechnen (optional, mit Fallback)
                try:
                    klines_4h = await self.get_klines(symbol, interval="4h", limit=2)
                    if len(klines_4h) >= 2:
                        price_4h_ago = float(klines_4h[-2][4])
                        current_price = float(klines_4h[-1][4])
                        return_4h = ((current_price - price_4h_ago) / price_4h_ago) * 100
                    else:
                        return_4h = 0
                except Exception:
                    return_4h = 0
                
                momentum_score = (0.6 * price_change_pct) + (0.4 * return_4h)
                
                momentum_pairs.append({
                    'symbol': symbol,
                    'score': momentum_score,
                    'return_24h': price_change_pct,
                    'return_4h': return_4h,
                    'quoteVolume': ticker.get('volume_24h', 0),
                    'spread_pct': ticker.get('spread_pct', 0),
                    'price': ticker.get('price', 0),
                    'tier': ticker.get('tier', 'unknown')
                })
            except Exception as e:
                logger.warning(f"Error calculating momentum for {symbol}: {e}")
                continue
        
        momentum_pairs.sort(key=lambda x: x['score'], reverse=True)
        
        # ═══════════════════════════════════════════════════════════════════════════
        # LOGGING - Transparenz
        # ═══════════════════════════════════════════════════════════════════════════
        logger.info(
            f"[UNIVERSE] ═══════════════════════════════════════════════════\n"
            f"   📊 Total USDT pairs:        {filter_stats['total_usdt_pairs']}\n"
            f"   ❌ Filtered (blacklist):    {filter_stats['filtered_blacklist']}\n"
            f"   ❌ Filtered (volume<500K):  {filter_stats['filtered_volume']}\n"
            f"   ❌ Filtered (spread>0.5%):  {filter_stats['filtered_spread']}\n"
            f"   ❌ Filtered (price=0):      {filter_stats['filtered_price_zero']}\n"
            f"   ─────────────────────────────────────────────────────────\n"
            f"   ✅ PREFERRED (Vol>5M, Spr<0.2%):  {filter_stats['preferred_count']}\n"
            f"   ✅ STANDARD (Vol>2M, Spr<0.35%): {filter_stats['standard_count']}\n"
            f"   ✅ FALLBACK (Vol>500K, Spr<0.5%): {filter_stats['fallback_count']}\n"
            f"   ─────────────────────────────────────────────────────────\n"
            f"   🎯 Final Tradeable Pool:    {filter_stats['final_tradeable']}\n"
            f"   🔍 Active Scan (this cycle): {len(momentum_pairs)}\n"
            f"   ═══════════════════════════════════════════════════════"
        )
        
        # Rückgabe als Dict mit pairs und stats für Transparenz
        return {
            'pairs': momentum_pairs,
            'stats': filter_stats,
            'all_tradeable': [p['symbol'] for p in all_tradeable],  # Vollständige Liste für Rotation
        }
    
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
