"""
KI Learning Engine - Learning by Doing
=======================================
- Erste 10 Trades: Bot handelt alleine (Datensammlung)
- Ab Trade 11: KI übernimmt komplett und lernt aus Fehlern
- Kontinuierlicher Feedback-Loop
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field, asdict
import json
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class KILearning:
    """KI Lernzustand für einen User"""
    user_id: str
    total_trades: int = 0
    ki_active: bool = False  # KI übernimmt ab Trade 11
    ki_takeover_time: Optional[str] = None
    
    # Gelernte Erkenntnisse
    learned_patterns: List[Dict] = field(default_factory=list)
    
    # Performance Tracking
    ki_trades: int = 0  # Trades von KI gemacht
    ki_wins: int = 0
    ki_losses: int = 0
    ki_confidence: float = 0.5  # Startet bei 50%
    
    # Fehler-Tracking für Feedback-Loop
    recent_mistakes: List[Dict] = field(default_factory=list)
    
    # Gelernte Schwellenwerte (werden durch Erfahrung angepasst)
    learned_rsi_min: float = 45
    learned_rsi_max: float = 70
    learned_adx_min: float = 20
    learned_volume_threshold: float = 500000
    learned_atr_multiplier: float = 2.0
    
    # Was die KI gelernt hat (für Log)
    learning_log: List[Dict] = field(default_factory=list)


class KILearningEngine:
    """KI Learning Engine mit Feedback-Loop"""
    
    MIN_TRADES_FOR_TAKEOVER = 10
    
    def __init__(self, db):
        self.db = db
        self.collection_name = "ki_learning"
    
    async def get_ki_state(self, user_id: str) -> KILearning:
        """Hole KI-Lernzustand für User"""
        collection = self.db.db[self.collection_name]
        doc = await collection.find_one({"user_id": user_id})
        
        if doc:
            doc.pop('_id', None)
            return KILearning(**doc)
        
        return KILearning(user_id=user_id)
    
    async def save_ki_state(self, state: KILearning):
        """Speichere KI-Lernzustand"""
        collection = self.db.db[self.collection_name]
        data = asdict(state)
        
        await collection.update_one(
            {"user_id": state.user_id},
            {"$set": data},
            upsert=True
        )
    
    async def record_trade(self, user_id: str, trade_data: Dict):
        """Zeichne Trade auf und prüfe ob KI übernehmen soll"""
        state = await self.get_ki_state(user_id)
        state.total_trades += 1
        
        # Prüfe ob KI übernehmen soll
        if state.total_trades >= self.MIN_TRADES_FOR_TAKEOVER and not state.ki_active:
            state.ki_active = True
            state.ki_takeover_time = datetime.now(timezone.utc).isoformat()
            
            # Initiales Lernen aus den ersten 10 Trades
            await self._initial_learning(user_id, state)
            
            state.learning_log.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "event": "KI_TAKEOVER",
                "message": f"KI übernimmt nach {state.total_trades} Trades!",
                "confidence": state.ki_confidence
            })
            
            logger.info(f"[KI] 🧠 KI übernimmt für User {user_id} nach {state.total_trades} Trades!")
        
        await self.save_ki_state(state)
        return state
    
    async def record_trade_result(
        self, 
        user_id: str, 
        symbol: str,
        entry_data: Dict,
        pnl_percent: float,
        was_ki_trade: bool = False
    ):
        """Zeichne Trade-Ergebnis auf und lerne daraus"""
        state = await self.get_ki_state(user_id)
        
        is_win = pnl_percent > 0
        
        if was_ki_trade:
            state.ki_trades += 1
            if is_win:
                state.ki_wins += 1
                # Confidence steigt bei Gewinn
                state.ki_confidence = min(0.95, state.ki_confidence + 0.02)
            else:
                state.ki_losses += 1
                # Confidence sinkt bei Verlust
                state.ki_confidence = max(0.3, state.ki_confidence - 0.03)
                
                # Fehler dokumentieren für Feedback-Loop
                mistake = {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "symbol": symbol,
                    "pnl_percent": pnl_percent,
                    "entry_data": entry_data,
                    "lesson_learned": self._analyze_mistake(entry_data, pnl_percent)
                }
                state.recent_mistakes.append(mistake)
                
                # Nur letzte 10 Fehler behalten
                state.recent_mistakes = state.recent_mistakes[-10:]
                
                # SOFORT aus Fehler lernen
                await self._learn_from_mistake(state, entry_data, pnl_percent)
        
        await self.save_ki_state(state)
        return state
    
    def _analyze_mistake(self, entry_data: Dict, pnl_percent: float) -> str:
        """Analysiere was bei einem Verlust-Trade falsch war"""
        lessons = []
        
        rsi = entry_data.get('rsi', 50)
        adx = entry_data.get('adx', 20)
        volume = entry_data.get('volume_24h', 0)
        regime = entry_data.get('regime', 'UNKNOWN')
        
        if rsi > 65:
            lessons.append(f"RSI war zu hoch ({rsi:.0f}) - überkauft")
        if rsi < 35:
            lessons.append(f"RSI war zu niedrig ({rsi:.0f}) - überverkauft ohne Reversal")
        if adx < 15:
            lessons.append(f"ADX war zu niedrig ({adx:.0f}) - kein klarer Trend")
        if volume < 200000:
            lessons.append(f"Volumen zu gering (${volume:,.0f}) - illiquider Markt")
        if regime == "BEARISH":
            lessons.append("Markt war BEARISH - hätte shorten oder warten sollen")
        
        if not lessons:
            lessons.append("Markt hat sich unerwartet bewegt - externes Ereignis")
        
        return " | ".join(lessons)
    
    async def _learn_from_mistake(self, state: KILearning, entry_data: Dict, pnl_percent: float):
        """Sofortiges Lernen aus einem Fehler (Feedback-Loop)"""
        rsi = entry_data.get('rsi', 50)
        adx = entry_data.get('adx', 20)
        volume = entry_data.get('volume_24h', 0)
        
        learning = {
            "time": datetime.now(timezone.utc).isoformat(),
            "type": "MISTAKE_LEARNING",
            "adjustments": []
        }
        
        # RSI Anpassung
        if rsi > 65 and pnl_percent < -2:
            old_max = state.learned_rsi_max
            state.learned_rsi_max = max(55, state.learned_rsi_max - 2)
            learning["adjustments"].append(f"RSI Max: {old_max:.0f} → {state.learned_rsi_max:.0f}")
        
        if rsi < 40 and pnl_percent < -2:
            old_min = state.learned_rsi_min
            state.learned_rsi_min = min(50, state.learned_rsi_min + 2)
            learning["adjustments"].append(f"RSI Min: {old_min:.0f} → {state.learned_rsi_min:.0f}")
        
        # ADX Anpassung
        if adx < 20 and pnl_percent < -3:
            old_adx = state.learned_adx_min
            state.learned_adx_min = min(30, state.learned_adx_min + 2)
            learning["adjustments"].append(f"ADX Min: {old_adx:.0f} → {state.learned_adx_min:.0f}")
        
        # Volumen Anpassung
        if volume < 300000 and pnl_percent < -2:
            old_vol = state.learned_volume_threshold
            state.learned_volume_threshold = min(1000000, state.learned_volume_threshold * 1.2)
            learning["adjustments"].append(f"Volume Min: ${old_vol:,.0f} → ${state.learned_volume_threshold:,.0f}")
        
        # ATR Multiplier Anpassung (für SL)
        if pnl_percent < -5:  # Großer Verlust = SL zu eng
            old_atr = state.learned_atr_multiplier
            state.learned_atr_multiplier = min(3.0, state.learned_atr_multiplier + 0.1)
            learning["adjustments"].append(f"ATR Mult: {old_atr:.1f} → {state.learned_atr_multiplier:.1f}")
        
        if learning["adjustments"]:
            state.learning_log.append(learning)
            logger.info(f"[KI] 📚 Gelernt: {learning['adjustments']}")
    
    async def _initial_learning(self, user_id: str, state: KILearning):
        """Initiales Lernen aus den ersten 10 Trades"""
        # Hole Trades aus der Datenbank
        trades_collection = self.db.db["trades"]
        trades = await trades_collection.find(
            {"user_id": user_id, "mode": "live"}
        ).sort("ts", -1).limit(10).to_list(10)
        
        if not trades:
            return
        
        wins = [t for t in trades if t.get('pnl', 0) > 0]
        losses = [t for t in trades if t.get('pnl', 0) < 0]
        
        win_rate = len(wins) / len(trades) * 100 if trades else 50
        
        # Analyse der Gewinner
        if wins:
            avg_win_pnl = np.mean([t.get('pnl_pct', 0) for t in wins])
            state.learning_log.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "type": "INITIAL_LEARNING",
                "message": f"Analysiert: {len(trades)} Trades, {win_rate:.0f}% Win Rate",
                "avg_win": f"{avg_win_pnl:.1f}%"
            })
        
        # Analyse der Verlierer - was war gemeinsam?
        if losses:
            avg_loss_pnl = np.mean([t.get('pnl_pct', 0) for t in losses])
            state.learning_log.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "type": "LOSS_ANALYSIS",
                "message": f"Verluste analysiert: Ø {avg_loss_pnl:.1f}%",
                "count": len(losses)
            })
        
        # Setze initiale Confidence basierend auf bisheriger Performance
        state.ki_confidence = min(0.8, max(0.4, win_rate / 100))
    
    def should_ki_trade(self, state: KILearning, market_data: Dict) -> Tuple[bool, str, List[str]]:
        """
        KI-Entscheidung ob gehandelt werden soll
        Returns: (should_trade, reason, warnings)
        """
        if not state.ki_active:
            return (True, "KI noch nicht aktiv - Bot entscheidet", [])
        
        warnings = []
        reasons = []
        
        rsi = market_data.get('rsi', 50)
        adx = market_data.get('adx', 20)
        volume = market_data.get('volume_24h', 0)
        regime = market_data.get('regime', 'SIDEWAYS')
        
        # RSI Check mit gelernten Werten
        if rsi < state.learned_rsi_min:
            warnings.append(f"RSI zu niedrig ({rsi:.0f} < {state.learned_rsi_min:.0f})")
        elif rsi > state.learned_rsi_max:
            warnings.append(f"RSI zu hoch ({rsi:.0f} > {state.learned_rsi_max:.0f})")
        else:
            reasons.append(f"RSI OK ({rsi:.0f})")
        
        # ADX Check
        if adx < state.learned_adx_min:
            warnings.append(f"ADX zu schwach ({adx:.0f} < {state.learned_adx_min:.0f})")
        else:
            reasons.append(f"ADX OK ({adx:.0f})")
        
        # Volumen Check
        if volume < state.learned_volume_threshold:
            warnings.append(f"Volumen zu gering (${volume:,.0f})")
        else:
            reasons.append(f"Volumen OK (${volume:,.0f})")
        
        # Regime Check
        if regime == "BEARISH" and market_data.get('direction', 'long') == 'long':
            warnings.append("BEARISH Markt für Long nicht geeignet")
        
        # Entscheidung basierend auf Confidence und Warnungen
        if len(warnings) >= 2:
            return (False, "Zu viele Warnungen", warnings)
        
        if len(warnings) == 1 and state.ki_confidence < 0.6:
            return (False, "Warnung + niedrige Confidence", warnings)
        
        return (True, "KI genehmigt Trade", reasons)
    
    def get_ki_adjusted_params(self, state: KILearning) -> Dict:
        """Hole von KI gelernte/angepasste Parameter"""
        return {
            "rsi_min": state.learned_rsi_min,
            "rsi_max": state.learned_rsi_max,
            "adx_min": state.learned_adx_min,
            "volume_threshold": state.learned_volume_threshold,
            "atr_multiplier": state.learned_atr_multiplier,
            "confidence": state.ki_confidence
        }
    
    async def get_ki_log(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Hole KI Learning Log"""
        state = await self.get_ki_state(user_id)
        return state.learning_log[-limit:]
    
    async def get_ki_stats(self, user_id: str) -> Dict:
        """Hole KI Statistiken"""
        state = await self.get_ki_state(user_id)
        
        ki_win_rate = 0
        if state.ki_trades > 0:
            ki_win_rate = (state.ki_wins / state.ki_trades) * 100
        
        return {
            "total_trades": state.total_trades,
            "ki_active": state.ki_active,
            "ki_takeover_time": state.ki_takeover_time,
            "trades_until_takeover": max(0, self.MIN_TRADES_FOR_TAKEOVER - state.total_trades),
            "ki_trades": state.ki_trades,
            "ki_wins": state.ki_wins,
            "ki_losses": state.ki_losses,
            "ki_win_rate": ki_win_rate,
            "ki_confidence": state.ki_confidence * 100,
            "learned_params": self.get_ki_adjusted_params(state),
            "recent_lessons": state.learning_log[-5:] if state.learning_log else [],
            "recent_mistakes": state.recent_mistakes[-3:] if state.recent_mistakes else []
        }


# Global instance
_ki_engine = None

def get_ki_engine(db):
    global _ki_engine
    if _ki_engine is None:
        _ki_engine = KILearningEngine(db)
    return _ki_engine
