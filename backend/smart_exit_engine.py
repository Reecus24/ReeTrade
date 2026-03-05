"""
Smart Exit Engine - Intelligente Verkaufsentscheidungen
========================================================
- Überwacht offene Positionen kontinuierlich
- Analysiert Charts in Echtzeit
- Kann FRÜHER verkaufen wenn sich Markt ändert
- Kann LÄNGER halten wenn Trade gut läuft
- Lernt aus vergangenen Exit-Entscheidungen
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExitSignal:
    """Signal für Exit-Entscheidung"""
    should_exit: bool
    exit_type: str  # 'early_exit', 'trail_stop', 'momentum_loss', 'trend_reversal', 'hold', 'tp', 'sl'
    confidence: float  # 0-100
    reasoning: List[str]
    suggested_exit_price: Optional[float] = None
    urgency: str = "normal"  # 'low', 'normal', 'high', 'critical'


@dataclass
class PositionContext:
    """Vollständiger Kontext einer offenen Position"""
    symbol: str
    entry_price: float
    current_price: float
    quantity: float
    entry_time: datetime
    unrealized_pnl_pct: float
    stop_loss: float
    take_profit: float
    
    # Marktdaten
    rsi: float = 50
    adx: float = 25
    macd_histogram: float = 0
    volume_ratio: float = 1.0  # Aktuelles Volumen vs Durchschnitt
    price_vs_ema20: float = 0  # % über/unter EMA20
    price_vs_ema50: float = 0  # % über/unter EMA50
    
    # Momentum
    momentum_1h: float = 0  # % Änderung letzte Stunde
    momentum_4h: float = 0  # % Änderung letzte 4 Stunden
    momentum_24h: float = 0  # % Änderung letzte 24 Stunden
    
    # Candlestick Patterns
    last_candle_type: str = "neutral"  # 'bullish', 'bearish', 'doji', 'neutral'
    consecutive_red_candles: int = 0
    consecutive_green_candles: int = 0


class SmartExitEngine:
    """Intelligente Exit-Engine mit Lernfähigkeit"""
    
    def __init__(self, db=None):
        self.db = db
        
        # Gelernte Parameter (werden durch Erfahrung angepasst)
        self.early_exit_threshold = -2.0  # % Verlust für frühen Ausstieg
        self.momentum_loss_threshold = -1.5  # Momentum-Verlust Schwelle
        self.trailing_activation = 1.5  # % Gewinn für Trailing Start
        self.trailing_distance = 0.8  # % Trailing Abstand
        
        # Exit-Statistiken für Lernen
        self.exit_history: List[Dict] = []
    
    async def analyze_position(self, ctx: PositionContext, ki_state=None) -> ExitSignal:
        """
        Hauptanalyse: Soll die Position geschlossen werden?
        
        Diese Methode prüft verschiedene Szenarien und entscheidet
        intelligent ob ein Exit sinnvoll ist.
        """
        reasons = []
        exit_type = "hold"
        confidence = 50
        should_exit = False
        urgency = "normal"
        
        time_in_trade = datetime.now(timezone.utc) - ctx.entry_time
        hours_in_trade = time_in_trade.total_seconds() / 3600
        
        # ========== KRITISCHE EXITS (sofort) ==========
        
        # 1. Stop Loss erreicht
        if ctx.current_price <= ctx.stop_loss:
            return ExitSignal(
                should_exit=True,
                exit_type="sl",
                confidence=100,
                reasoning=["Stop-Loss erreicht"],
                suggested_exit_price=ctx.current_price,
                urgency="critical"
            )
        
        # 2. Take Profit erreicht
        if ctx.current_price >= ctx.take_profit:
            return ExitSignal(
                should_exit=True,
                exit_type="tp",
                confidence=100,
                reasoning=["Take-Profit erreicht"],
                suggested_exit_price=ctx.current_price,
                urgency="critical"
            )
        
        # ========== INTELLIGENTE FRÜHE EXITS ==========
        
        # 3. Trend-Umkehr erkannt
        trend_reversal = self._detect_trend_reversal(ctx)
        if trend_reversal['detected']:
            reasons.extend(trend_reversal['reasons'])
            confidence = max(confidence, trend_reversal['confidence'])
            if trend_reversal['confidence'] > 70:
                should_exit = True
                exit_type = "trend_reversal"
                urgency = "high"
        
        # 4. Momentum-Verlust
        momentum_loss = self._detect_momentum_loss(ctx)
        if momentum_loss['detected']:
            reasons.extend(momentum_loss['reasons'])
            confidence = max(confidence, momentum_loss['confidence'])
            if momentum_loss['confidence'] > 65 and ctx.unrealized_pnl_pct < 0.5:
                should_exit = True
                exit_type = "momentum_loss"
                urgency = "normal"
        
        # 5. Volumen-Warnung (Liquidität sinkt)
        if ctx.volume_ratio < 0.3:
            reasons.append(f"Volumen stark gefallen ({ctx.volume_ratio:.1%} vom Durchschnitt)")
            if ctx.unrealized_pnl_pct > 0:
                reasons.append("Empfehle Gewinnmitnahme bei niedriger Liquidität")
                should_exit = True
                exit_type = "early_exit"
                confidence = 60
        
        # 6. Lange Zeit ohne Bewegung + negative Entwicklung
        if hours_in_trade > 12 and abs(ctx.unrealized_pnl_pct) < 1:
            reasons.append(f"Trade seit {hours_in_trade:.0f}h stagniert")
            if ctx.adx < 15:
                reasons.append("Kein Trend erkennbar (ADX < 15)")
                should_exit = True
                exit_type = "early_exit"
                confidence = 55
        
        # ========== TRAILING STOP LOGIK ==========
        
        # 7. Trailing Stop aktivieren/anpassen wenn im Gewinn
        if ctx.unrealized_pnl_pct >= self.trailing_activation:
            trailing = self._calculate_trailing_stop(ctx)
            if trailing['triggered']:
                reasons.extend(trailing['reasons'])
                should_exit = True
                exit_type = "trail_stop"
                confidence = 75
                urgency = "high"
        
        # ========== HOLD LOGIK (nicht verkaufen) ==========
        
        # 8. Trade läuft gut - weiterlaufen lassen
        if not should_exit and ctx.unrealized_pnl_pct > 0:
            if ctx.momentum_1h > 0.3 and ctx.rsi < 75:
                reasons.append(f"Trade läuft gut (+{ctx.unrealized_pnl_pct:.1f}%), Momentum positiv")
                confidence = 30  # Niedrige Confidence = nicht verkaufen
            
            # Prüfe ob wir über TP hinaus halten sollten
            if ctx.unrealized_pnl_pct > (ctx.take_profit / ctx.entry_price - 1) * 100 * 0.8:
                if ctx.rsi < 80 and ctx.momentum_1h > 0:
                    reasons.append("Nahe TP aber Momentum noch positiv - halte weiter")
                    should_exit = False
        
        # ========== LERNENDE ANPASSUNG ==========
        
        # 9. Berücksichtige KI-Lernzustand falls verfügbar
        if ki_state and hasattr(ki_state, 'learned_patterns'):
            self._apply_learned_patterns(ctx, ki_state, reasons)
        
        return ExitSignal(
            should_exit=should_exit,
            exit_type=exit_type,
            confidence=confidence,
            reasoning=reasons,
            suggested_exit_price=ctx.current_price if should_exit else None,
            urgency=urgency
        )
    
    def _detect_trend_reversal(self, ctx: PositionContext) -> Dict:
        """Erkennt Trendumkehr anhand mehrerer Indikatoren"""
        signals = []
        confidence = 0
        
        # RSI Divergenz
        if ctx.rsi > 70 and ctx.momentum_1h < 0:
            signals.append("RSI überkauft + Momentum negativ = Reversal wahrscheinlich")
            confidence += 25
        
        # Preis unter EMA20 gefallen
        if ctx.price_vs_ema20 < -1.5 and ctx.unrealized_pnl_pct > 0:
            signals.append(f"Preis unter EMA20 gefallen ({ctx.price_vs_ema20:.1f}%)")
            confidence += 20
        
        # Mehrere rote Kerzen
        if ctx.consecutive_red_candles >= 3:
            signals.append(f"{ctx.consecutive_red_candles} rote Kerzen in Folge")
            confidence += 15
        
        # MACD wird negativ
        if ctx.macd_histogram < -0.5:
            signals.append("MACD Histogram stark negativ")
            confidence += 20
        
        # Bearish Candlestick Pattern
        if ctx.last_candle_type == "bearish":
            signals.append("Letzte Kerze bearish")
            confidence += 10
        
        return {
            'detected': confidence > 50,
            'confidence': min(confidence, 95),
            'reasons': signals
        }
    
    def _detect_momentum_loss(self, ctx: PositionContext) -> Dict:
        """Erkennt Momentum-Verlust"""
        signals = []
        confidence = 0
        
        # Kurzfristiges Momentum negativ
        if ctx.momentum_1h < -0.5:
            signals.append(f"1h Momentum negativ ({ctx.momentum_1h:.1f}%)")
            confidence += 20
        
        # Momentum-Umkehr (war positiv, jetzt negativ)
        if ctx.momentum_4h > 0 and ctx.momentum_1h < 0:
            signals.append("Momentum dreht von positiv zu negativ")
            confidence += 25
        
        # ADX fällt (Trend verliert Stärke)
        if ctx.adx < 20 and ctx.unrealized_pnl_pct < 1:
            signals.append(f"ADX niedrig ({ctx.adx:.0f}) - Trend schwach")
            confidence += 15
        
        # Volumen sinkt
        if ctx.volume_ratio < 0.5:
            signals.append(f"Volumen nur {ctx.volume_ratio:.0%} vom Durchschnitt")
            confidence += 15
        
        return {
            'detected': confidence > 40,
            'confidence': min(confidence, 85),
            'reasons': signals
        }
    
    def _calculate_trailing_stop(self, ctx: PositionContext) -> Dict:
        """Berechnet dynamischen Trailing Stop"""
        # Trailing Stop Preis
        trailing_stop_pct = ctx.unrealized_pnl_pct - self.trailing_distance
        trailing_stop_price = ctx.entry_price * (1 + trailing_stop_pct / 100)
        
        # Wurde der Trailing Stop unterschritten?
        triggered = ctx.current_price < trailing_stop_price and ctx.unrealized_pnl_pct > 0.5
        
        reasons = []
        if triggered:
            reasons.append(f"Trailing Stop ausgelöst bei +{trailing_stop_pct:.1f}%")
            reasons.append(f"Max Gewinn war +{ctx.unrealized_pnl_pct + self.trailing_distance:.1f}%")
        
        return {
            'triggered': triggered,
            'trailing_price': trailing_stop_price,
            'reasons': reasons
        }
    
    def _apply_learned_patterns(self, ctx: PositionContext, ki_state, reasons: List[str]):
        """Wendet gelernte Muster aus der KI an"""
        # Prüfe ob ähnliche Situationen in der Vergangenheit schlecht liefen
        for pattern in ki_state.learned_patterns[-20:]:  # Letzte 20 Patterns
            if self._pattern_matches(ctx, pattern):
                if pattern.get('outcome') == 'loss':
                    reasons.append(f"KI-Warnung: Ähnliche Situation führte zu Verlust")
    
    def _pattern_matches(self, ctx: PositionContext, pattern: Dict) -> bool:
        """Prüft ob aktueller Kontext zu einem gelernten Pattern passt"""
        if not pattern:
            return False
        
        # Einfacher Musterabgleich
        rsi_match = abs(ctx.rsi - pattern.get('rsi', 50)) < 10
        adx_match = abs(ctx.adx - pattern.get('adx', 25)) < 10
        
        return rsi_match and adx_match
    
    async def record_exit_result(self, symbol: str, exit_signal: ExitSignal, 
                                  final_pnl_pct: float, ctx: PositionContext):
        """Speichert Exit-Ergebnis für zukünftiges Lernen"""
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'symbol': symbol,
            'exit_type': exit_signal.exit_type,
            'confidence': exit_signal.confidence,
            'pnl_pct': final_pnl_pct,
            'was_good_decision': final_pnl_pct > -1 or exit_signal.exit_type in ['tp', 'trail_stop'],
            'context': {
                'rsi': ctx.rsi,
                'adx': ctx.adx,
                'momentum_1h': ctx.momentum_1h,
                'volume_ratio': ctx.volume_ratio
            }
        }
        
        self.exit_history.append(record)
        
        # Lerne aus schlechten Entscheidungen
        if not record['was_good_decision']:
            await self._learn_from_bad_exit(record)
        
        # Halte nur letzte 100 Exits
        self.exit_history = self.exit_history[-100:]
    
    async def _learn_from_bad_exit(self, record: Dict):
        """Passt Parameter basierend auf schlechten Exits an"""
        exit_type = record['exit_type']
        pnl = record['pnl_pct']
        
        # Wenn früher Exit zu Verlust führte
        if exit_type == 'early_exit' and pnl < -2:
            self.early_exit_threshold -= 0.5  # Strenger werden
            logger.info(f"[SmartExit] Lerne: Früher Exit war schlecht, threshold jetzt {self.early_exit_threshold}%")
        
        # Wenn Trailing zu früh ausgelöst wurde
        if exit_type == 'trail_stop' and pnl < 1:
            self.trailing_distance += 0.2  # Mehr Spielraum
            logger.info(f"[SmartExit] Lerne: Trailing zu eng, distance jetzt {self.trailing_distance}%")


# Hilfsfunktion für Worker-Integration
async def check_position_exit(
    position: Dict,
    market_data: Dict,
    db=None,
    ki_state=None
) -> ExitSignal:
    """
    Wrapper-Funktion für einfache Integration im Worker
    
    Args:
        position: Dict mit Position-Details (aus DB oder MEXC)
        market_data: Aktuelle Marktdaten (Preis, RSI, etc.)
        db: Datenbank-Instanz
        ki_state: KI-Lernzustand (optional)
    
    Returns:
        ExitSignal mit Empfehlung
    """
    engine = SmartExitEngine(db)
    
    # Kontext aufbauen
    ctx = PositionContext(
        symbol=position.get('symbol', ''),
        entry_price=float(position.get('entry_price', 0)),
        current_price=float(market_data.get('price', 0)),
        quantity=float(position.get('quantity', 0)),
        entry_time=position.get('entry_time', datetime.now(timezone.utc)),
        unrealized_pnl_pct=float(market_data.get('pnl_pct', 0)),
        stop_loss=float(position.get('stop_loss', 0)),
        take_profit=float(position.get('take_profit', 0)),
        rsi=float(market_data.get('rsi', 50)),
        adx=float(market_data.get('adx', 25)),
        macd_histogram=float(market_data.get('macd_histogram', 0)),
        volume_ratio=float(market_data.get('volume_ratio', 1.0)),
        price_vs_ema20=float(market_data.get('price_vs_ema20', 0)),
        price_vs_ema50=float(market_data.get('price_vs_ema50', 0)),
        momentum_1h=float(market_data.get('momentum_1h', 0)),
        momentum_4h=float(market_data.get('momentum_4h', 0)),
        momentum_24h=float(market_data.get('momentum_24h', 0)),
        last_candle_type=market_data.get('last_candle_type', 'neutral'),
        consecutive_red_candles=int(market_data.get('consecutive_red_candles', 0)),
        consecutive_green_candles=int(market_data.get('consecutive_green_candles', 0))
    )
    
    return await engine.analyze_position(ctx, ki_state)
