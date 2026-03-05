"""
ML Data Collector - Sammelt Trainingsdaten für zukünftiges KI-Modell

Speichert bei jedem Trade:
- Marktbedingungen vor dem Kauf (Features)
- Ergebnis nach dem Verkauf (Label)

Nach ~100-500 Trades kann ein ML-Modell trainiert werden,
das den regelbasierten Bot ersetzt.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeSnapshot:
    """Snapshot aller Marktbedingungen bei Kauf"""
    # Identifikation
    snapshot_id: str
    user_id: str
    symbol: str
    entry_time: str
    
    # Preis-Daten
    entry_price: float
    price_change_1h: float  # % Änderung letzte Stunde
    price_change_24h: float  # % Änderung letzte 24h
    
    # Technische Indikatoren - ERWEITERT
    rsi: float
    adx: float
    atr_percent: float  # ATR als % vom Preis
    ema_fast: float
    ema_slow: float
    ema_distance: float  # Abstand zwischen EMAs in %
    
    # Volumen
    volume_24h: float
    volume_change: float  # Volume vs Durchschnitt
    
    # Markt-Regime
    regime: str  # BULLISH, SIDEWAYS, BEARISH
    volatility_percentile: float
    momentum_score: float
    
    # NEU: Weitere Indikatoren (mit defaults)
    macd_value: float = 0
    macd_signal: float = 0
    macd_histogram: float = 0
    bollinger_upper: float = 0
    bollinger_lower: float = 0
    bollinger_position: float = 0  # Wo ist Preis in den Bands (0-100)
    stoch_rsi: float = 0
    
    # BTC/ETH Korrelation
    btc_price: float = 0
    btc_change_24h: float = 0
    eth_price: float = 0
    eth_change_24h: float = 0
    btc_correlation: float = 0  # Korrelation zu BTC (-1 bis 1)
    
    # Futures Daten (für später)
    funding_rate: float = 0
    open_interest: float = 0
    long_short_ratio: float = 0
    
    # Position Details (mit defaults für Rückwärtskompatibilität)
    position_size_usdt: float = 0
    position_percent: float = 0  # % vom Portfolio
    stop_loss_percent: float = 0
    take_profit_percent: float = 0
    
    # Kontext
    hour_of_day: int = 0  # 0-23
    day_of_week: int = 0  # 0-6 (Montag=0)
    open_positions_count: int = 0
    
    # AI Confidence (wenn AI Mode)
    ai_confidence: Optional[float] = None
    ai_profile: Optional[str] = None
    
    # NEU: Explorer Mode Parameter (wenn KI Explorer)
    explorer_mode: bool = False
    explorer_rsi_threshold: Optional[float] = None
    explorer_adx_minimum: Optional[float] = None
    explorer_sl_pct: Optional[float] = None
    explorer_tp_rr: Optional[float] = None
    
    # Ergebnis (wird nach Verkauf ausgefüllt)
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_percent: Optional[float] = None
    pnl_usdt: Optional[float] = None
    exit_reason: Optional[str] = None  # STOP_LOSS, TAKE_PROFIT, PARTIAL, MANUAL
    hold_duration_minutes: Optional[int] = None
    
    # NEU: Erweiterte Trade-Analyse
    max_profit_during_trade: Optional[float] = None  # Höchster Gewinn erreicht
    max_drawdown_during_trade: Optional[float] = None  # Tiefster Punkt
    missed_profit_pct: Optional[float] = None  # Verpasster Gewinn
    
    # Label für ML (wird nach Verkauf gesetzt)
    is_winner: Optional[bool] = None  # True wenn PnL > 0


class MLDataCollector:
    """Sammelt und verwaltet ML-Trainingsdaten"""
    
    def __init__(self, db):
        self.db = db
        self.collection_name = "ml_training_data"
    
    async def save_entry_snapshot(
        self,
        user_id: str,
        symbol: str,
        entry_price: float,
        position_size_usdt: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        market_data: Dict,
        ai_data: Optional[Dict] = None
    ) -> str:
        """Speichert Snapshot bei Kauf - Returns snapshot_id"""
        
        now = datetime.now(timezone.utc)
        snapshot_id = f"{user_id}_{symbol}_{now.strftime('%Y%m%d%H%M%S')}"
        
        snapshot = TradeSnapshot(
            snapshot_id=snapshot_id,
            user_id=user_id,
            symbol=symbol,
            entry_time=now.isoformat(),
            entry_price=entry_price,
            
            # Preis-Daten
            price_change_1h=market_data.get('price_change_1h', 0),
            price_change_24h=market_data.get('price_change_24h', 0),
            
            # Technische Indikatoren
            rsi=market_data.get('rsi', 50),
            adx=market_data.get('adx', 0),
            atr_percent=market_data.get('atr_percent', 0),
            ema_fast=market_data.get('ema_fast', 0),
            ema_slow=market_data.get('ema_slow', 0),
            ema_distance=market_data.get('ema_distance', 0),
            
            # Volumen
            volume_24h=market_data.get('volume_24h', 0),
            volume_change=market_data.get('volume_change', 0),
            
            # Markt-Regime
            regime=market_data.get('regime', 'UNKNOWN'),
            volatility_percentile=market_data.get('volatility_percentile', 50),
            momentum_score=market_data.get('momentum_score', 0),
            
            # Position
            position_size_usdt=position_size_usdt,
            position_percent=market_data.get('position_percent', 0),
            stop_loss_percent=stop_loss_pct,
            take_profit_percent=take_profit_pct,
            
            # Kontext
            hour_of_day=now.hour,
            day_of_week=now.weekday(),
            open_positions_count=market_data.get('open_positions', 0),
            
            # AI Data
            ai_confidence=ai_data.get('confidence') if ai_data else None,
            ai_profile=ai_data.get('profile') if ai_data else None
        )
        
        # In MongoDB speichern
        collection = self.db.db[self.collection_name]
        await collection.insert_one(asdict(snapshot))
        
        logger.info(f"[ML] Snapshot gespeichert: {snapshot_id}")
        return snapshot_id
    
    async def update_exit_result(
        self,
        user_id: str,
        symbol: str,
        exit_price: float,
        pnl_percent: float,
        pnl_usdt: float,
        exit_reason: str
    ) -> bool:
        """Aktualisiert Snapshot mit Verkaufs-Ergebnis"""
        
        collection = self.db.db[self.collection_name]
        
        # Finde den neuesten offenen Snapshot für dieses Symbol
        snapshot = await collection.find_one(
            {
                'user_id': user_id,
                'symbol': symbol,
                'exit_time': None  # Noch nicht verkauft
            },
            sort=[('entry_time', -1)]
        )
        
        if not snapshot:
            logger.warning(f"[ML] Kein offener Snapshot für {symbol}")
            return False
        
        # Berechne Haltezeit
        entry_time = datetime.fromisoformat(snapshot['entry_time'].replace('Z', '+00:00'))
        exit_time = datetime.now(timezone.utc)
        hold_duration = int((exit_time - entry_time).total_seconds() / 60)
        
        # Update mit Ergebnis
        await collection.update_one(
            {'_id': snapshot['_id']},
            {'$set': {
                'exit_time': exit_time.isoformat(),
                'exit_price': exit_price,
                'pnl_percent': pnl_percent,
                'pnl_usdt': pnl_usdt,
                'exit_reason': exit_reason,
                'hold_duration_minutes': hold_duration,
                'is_winner': pnl_percent > 0
            }}
        )
        
        logger.info(f"[ML] Exit gespeichert: {symbol} | PnL: {pnl_percent:.2f}% | Winner: {pnl_percent > 0}")
        return True
    
    async def get_training_stats(self, user_id: str) -> Dict:
        """Statistiken über gesammelte Trainingsdaten"""
        
        collection = self.db.db[self.collection_name]
        
        # Zähle Trades
        total = await collection.count_documents({'user_id': user_id})
        completed = await collection.count_documents({'user_id': user_id, 'exit_time': {'$ne': None}})
        winners = await collection.count_documents({'user_id': user_id, 'is_winner': True})
        
        # Durchschnittlicher PnL
        pipeline = [
            {'$match': {'user_id': user_id, 'pnl_percent': {'$ne': None}}},
            {'$group': {
                '_id': None,
                'avg_pnl': {'$avg': '$pnl_percent'},
                'total_pnl': {'$sum': '$pnl_usdt'},
                'avg_hold_time': {'$avg': '$hold_duration_minutes'}
            }}
        ]
        
        stats_result = await collection.aggregate(pipeline).to_list(length=1)
        stats = stats_result[0] if stats_result else {}
        
        return {
            'total_snapshots': total,
            'completed_trades': completed,
            'open_trades': total - completed,
            'winners': winners,
            'losers': completed - winners,
            'win_rate': (winners / completed * 100) if completed > 0 else 0,
            'avg_pnl_percent': stats.get('avg_pnl', 0),
            'total_pnl_usdt': stats.get('total_pnl', 0),
            'avg_hold_minutes': stats.get('avg_hold_time', 0),
            'ready_for_training': completed >= 100
        }
    
    async def get_training_data(self, user_id: str, min_trades: int = 50) -> List[Dict]:
        """Holt alle abgeschlossenen Trades für ML Training"""
        
        collection = self.db.db[self.collection_name]
        
        trades = await collection.find({
            'user_id': user_id,
            'exit_time': {'$ne': None},
            'pnl_percent': {'$ne': None}
        }).to_list(length=10000)
        
        if len(trades) < min_trades:
            logger.warning(f"[ML] Nur {len(trades)} Trades - brauche mindestens {min_trades}")
            return []
        
        return trades


# Singleton instance
ml_collector = None

def get_ml_collector(db):
    global ml_collector
    if ml_collector is None:
        ml_collector = MLDataCollector(db)
    return ml_collector
