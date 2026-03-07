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
                                      min_preferred_coins: int = 10) -> List[Dict]:
        """Get momentum-scored universe with TWO-TIER liquidity filter
        
        ZWEISTUFIGES SYSTEM für 10-Minuten-Trading:
        
        1. PREFERRED COINS (höchste Qualität):
           - Volume > 5M USDT
           - Spread < 0.20%
           
        2. FALLBACK UNIVERSE (wenn zu wenig Preferred):
           - Volume > 2M USDT
           - Spread < 0.35%
        
        Der Scanner nutzt zuerst Preferred Coins. Nur wenn dort zu wenige 
        verfügbar sind (< min_preferred_coins), wird das Fallback Universe hinzugefügt.
        
        Returns list of dicts with: symbol, score, return_24h, return_4h, quoteVolume, spread_pct, tier
        """
        # ═══════════════════════════════════════════════════════════════════════════
        # FILTER THRESHOLDS
        # ═══════════════════════════════════════════════════════════════════════════
        PREFERRED_MIN_VOLUME = 5_000_000   # 5M USDT
        PREFERRED_MAX_SPREAD = 0.20        # 0.20%
        
        FALLBACK_MIN_VOLUME = 2_000_000    # 2M USDT
        FALLBACK_MAX_SPREAD = 0.35         # 0.35%
        
        # Get all tickers
        tickers = await self.get_ticker_24h()
        
        usdt_pairs = [
            t for t in tickers 
            if isinstance(t, dict) and t.get('symbol', '').endswith(quote)
        ]
        
        # ═══════════════════════════════════════════════════════════════════════════
        # ERWEITERTES TRADING UNIVERSE (~200 Coins)
        # Nur verifizierte MEXC USDT Paare
        # ═══════════════════════════════════════════════════════════════════════════
        if curated_list is None:
            curated_list = [
                # ══════════════════════════════════════════════════════════════════
                # ORIGINAL LISTE (51 Coins - DIE FUNKTIONIERT HABEN!)
                # ══════════════════════════════════════════════════════════════════
                # Tier 1: High Liquidity Mid-Caps (15)
                "SOLUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT",
                "ATOMUSDT", "TRXUSDT", "NEARUSDT", "FILUSDT", "APTUSDT",
                "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT", "SEIUSDT",
                
                # Tier 2: DeFi & Layer 1 (10)
                "AAVEUSDT", "UNIUSDT", "RUNEUSDT", "STXUSDT", "TIAUSDT",
                "IMXUSDT", "FTMUSDT", "FLOWUSDT", "MINAUSDT", "RNDRUSDT",
                
                # Tier 3: Gaming & Metaverse (5)
                "GALAUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "CHZUSDT",
                
                # Tier 4: Infrastructure & DeFi (12)
                "ZILUSDT", "IOTAUSDT", "XLMUSDT", "ALGOUSDT",
                "DYDXUSDT", "GMXUSDT", "LDOUSDT", "CRVUSDT",
                "SNXUSDT", "COMPUSDT", "BALUSDT", "ANKRUSDT",
                
                # Tier 5: Volatile Coins (9)
                "WIFUSDT", "BONKUSDT", "FLOKIUSDT", "DOGEUSDT",
                "SHIBUSDT", "ORDIUSDT", "KASUSDT", "FETUSDT", "AGIXUSDT"
            ]
            
            # Duplikate entfernen
            curated_list = list(dict.fromkeys(curated_list))
        
        # Erstelle Lookup für schnellen Zugriff
        ticker_lookup = {t.get('symbol'): t for t in usdt_pairs}
        
        # Hole nur die Coins aus dem Universe
        filtered_pairs = []
        missing_coins = []
        for symbol in curated_list:
            if symbol in ticker_lookup:
                filtered_pairs.append(ticker_lookup[symbol])
            else:
                missing_coins.append(symbol)
        
        if missing_coins:
            logger.warning(f"[UNIVERSE] {len(missing_coins)} Coins nicht auf MEXC: {missing_coins[:5]}...")
        
        # ═══════════════════════════════════════════════════════════════════════════
        # ZWEISTUFIGE FILTERUNG
        # ═══════════════════════════════════════════════════════════════════════════
        preferred_pairs = []
        fallback_pairs = []
        rejected_coins = []
        
        for ticker in filtered_pairs:
            try:
                symbol = ticker.get('symbol', 'UNKNOWN')
                volume_24h = float(ticker.get('quoteVolume', 0))
                
                # Calculate spread from bid/ask
                bid = float(ticker.get('bidPrice', 0))
                ask = float(ticker.get('askPrice', 0))
                last_price = float(ticker.get('lastPrice', 1))
                
                if bid > 0 and ask > 0 and last_price > 0:
                    spread_pct = ((ask - bid) / last_price) * 100
                else:
                    spread_pct = max(0.05, 1.0 / (volume_24h / 1_000_000 + 1))
                
                ticker['spread_pct'] = spread_pct
                ticker['volume_24h'] = volume_24h
                
                # TIER 1: PREFERRED (beste Qualität)
                if volume_24h >= PREFERRED_MIN_VOLUME and spread_pct <= PREFERRED_MAX_SPREAD:
                    ticker['tier'] = 'preferred'
                    preferred_pairs.append(ticker)
                    
                # TIER 2: FALLBACK (immer noch gut)
                elif volume_24h >= FALLBACK_MIN_VOLUME and spread_pct <= FALLBACK_MAX_SPREAD:
                    ticker['tier'] = 'fallback'
                    fallback_pairs.append(ticker)
                    
                else:
                    rejected_coins.append(f"{symbol}(Vol:{volume_24h/1e6:.1f}M,Spr:{spread_pct:.2f}%)")
                    
            except Exception as e:
                logger.warning(f"Error filtering {ticker.get('symbol')}: {e}")
                continue
        
        # ═══════════════════════════════════════════════════════════════════════════
        # INTELLIGENTE AUSWAHL: Preferred first, Fallback nur wenn nötig
        # ═══════════════════════════════════════════════════════════════════════════
        if len(preferred_pairs) >= min_preferred_coins:
            liquid_pairs = preferred_pairs
            logger.info(f"[UNIVERSE] ✅ {len(preferred_pairs)} PREFERRED Coins (Vol>5M, Spread<0.20%)")
        else:
            liquid_pairs = preferred_pairs + fallback_pairs
            logger.info(f"[UNIVERSE] ⚠️ Nur {len(preferred_pairs)} Preferred → +{len(fallback_pairs)} Fallback")
            logger.info(f"[UNIVERSE] Total: {len(liquid_pairs)} (Preferred: Vol>5M/Spr<0.20%, Fallback: Vol>2M/Spr<0.35%)")
        
        if rejected_coins:
            logger.debug(f"[UNIVERSE] Rejected: {rejected_coins[:5]}...")
        
        # Sort by volume
        liquid_pairs.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
        base_universe = liquid_pairs[:base_limit]
        
        # Calculate momentum scores
        momentum_pairs = []
        for ticker in base_universe:
            try:
                symbol = ticker['symbol']
                price_change_pct = float(ticker.get('priceChangePercent', 0))
                
                klines_4h = await self.get_klines(symbol, interval="4h", limit=2)
                if len(klines_4h) >= 2:
                    price_4h_ago = float(klines_4h[-2][4])
                    current_price = float(klines_4h[-1][4])
                    return_4h = ((current_price - price_4h_ago) / price_4h_ago) * 100
                else:
                    return_4h = 0
                
                momentum_score = (0.6 * price_change_pct) + (0.4 * return_4h)
                
                momentum_pairs.append({
                    'symbol': symbol,
                    'score': momentum_score,
                    'return_24h': price_change_pct,
                    'return_4h': return_4h,
                    'quoteVolume': float(ticker.get('quoteVolume', 0)),
                    'spread_pct': ticker.get('spread_pct', 0),
                    'price': current_price if len(klines_4h) >= 2 else float(ticker.get('lastPrice', 0)),
                    'tier': ticker.get('tier', 'unknown')
                })
            except Exception as e:
                logger.warning(f"Error calculating momentum for {symbol}: {e}")
                continue
        
        momentum_pairs.sort(key=lambda x: x['score'], reverse=True)
        
        preferred_count = sum(1 for p in momentum_pairs if p.get('tier') == 'preferred')
        fallback_count = sum(1 for p in momentum_pairs if p.get('tier') == 'fallback')
        logger.info(f"[UNIVERSE] Final: {len(momentum_pairs)} tradable ({preferred_count} preferred, {fallback_count} fallback)")
        
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
