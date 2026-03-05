"""
ML Trading Model - Echte lernende KI für Trading-Entscheidungen
================================================================
- Lernt aus abgeschlossenen Trades
- Passt Strategie basierend auf Erfahrung an
- Kein regelbasiertes System - echtes Machine Learning
"""

import logging
import numpy as np
import pickle
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

# Versuche sklearn zu importieren
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("sklearn nicht installiert - ML-Features deaktiviert")


@dataclass
class TradeFeatures:
    """Features für ML-Modell"""
    # Markt-Indikatoren zum Zeitpunkt der Entscheidung
    rsi: float
    adx: float
    macd_histogram: float
    volume_ratio: float
    price_vs_ema20: float
    price_vs_ema50: float
    
    # Momentum
    momentum_1h: float
    momentum_4h: float
    momentum_24h: float
    
    # Position-Kontext
    pnl_pct: float
    hours_in_trade: float
    distance_to_sl_pct: float
    distance_to_tp_pct: float
    
    # Markt-Kontext
    btc_trend: float  # BTC Momentum als Markt-Indikator
    market_volatility: float
    
    def to_array(self) -> np.ndarray:
        """Konvertiere zu numpy Array für ML"""
        return np.array([
            self.rsi,
            self.adx,
            self.macd_histogram,
            self.volume_ratio,
            self.price_vs_ema20,
            self.price_vs_ema50,
            self.momentum_1h,
            self.momentum_4h,
            self.momentum_24h,
            self.pnl_pct,
            self.hours_in_trade,
            self.distance_to_sl_pct,
            self.distance_to_tp_pct,
            self.btc_trend,
            self.market_volatility
        ])
    
    @staticmethod
    def feature_names() -> List[str]:
        return [
            'rsi', 'adx', 'macd_histogram', 'volume_ratio',
            'price_vs_ema20', 'price_vs_ema50',
            'momentum_1h', 'momentum_4h', 'momentum_24h',
            'pnl_pct', 'hours_in_trade',
            'distance_to_sl_pct', 'distance_to_tp_pct',
            'btc_trend', 'market_volatility'
        ]


class MLTradingModel:
    """
    Echte lernende KI für Trading
    
    - Sammelt Daten von jedem Trade
    - Trainiert ML-Modell aus Erfahrung
    - Entscheidet basierend auf gelernten Mustern
    """
    
    MODEL_PATH = "/tmp/reetrade_ml_model.pkl"
    SCALER_PATH = "/tmp/reetrade_ml_scaler.pkl"
    MIN_SAMPLES_FOR_TRAINING = 20  # Mindestens 20 Trades zum Lernen
    RETRAIN_INTERVAL = 10  # Nach jedem 10. neuen Trade neu trainieren
    
    def __init__(self, db=None):
        self.db = db
        self.model = None
        self.scaler = None
        self.training_data: List[Dict] = []
        self.trades_since_last_train = 0
        self.model_accuracy = 0.0
        self.total_predictions = 0
        self.correct_predictions = 0
        
        # Lade gespeichertes Modell falls vorhanden
        self._load_model()
    
    def _load_model(self):
        """Lade trainiertes Modell von Disk"""
        if not ML_AVAILABLE:
            return
            
        try:
            if os.path.exists(self.MODEL_PATH) and os.path.exists(self.SCALER_PATH):
                with open(self.MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.SCALER_PATH, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("ML-Modell geladen")
        except Exception as e:
            logger.warning(f"Konnte ML-Modell nicht laden: {e}")
    
    def _save_model(self):
        """Speichere trainiertes Modell"""
        if not self.model or not self.scaler:
            return
            
        try:
            with open(self.MODEL_PATH, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.SCALER_PATH, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info("ML-Modell gespeichert")
        except Exception as e:
            logger.error(f"Konnte ML-Modell nicht speichern: {e}")
    
    async def collect_training_data(self, user_id: str):
        """
        Sammle Trainingsdaten aus abgeschlossenen Trades
        """
        if not self.db:
            return
        
        try:
            # Hole abgeschlossene Trades mit allen Daten
            trades = await self.db.trades.find({
                "user_id": user_id,
                "side": "SELL",
                "pnl": {"$exists": True}
            }).sort("ts", -1).limit(500).to_list(500)
            
            for trade in trades:
                # Prüfe ob wir die Feature-Daten haben
                if 'ml_features' not in trade:
                    continue
                
                features = trade['ml_features']
                pnl_pct = trade.get('pnl_pct', 0)
                
                # Label: War der Trade profitabel?
                # 0 = Verlust (hätte anders handeln sollen)
                # 1 = Gewinn (gute Entscheidung)
                label = 1 if pnl_pct > 0 else 0
                
                self.training_data.append({
                    'features': features,
                    'label': label,
                    'pnl_pct': pnl_pct
                })
            
            logger.info(f"ML: {len(self.training_data)} Trainingsdaten gesammelt")
            
        except Exception as e:
            logger.error(f"Fehler beim Sammeln der Trainingsdaten: {e}")
    
    async def record_trade_features(self, trade_id: str, features: TradeFeatures, decision: str):
        """
        Speichere Features zum Trade für späteres Lernen
        """
        if not self.db:
            return
        
        try:
            await self.db.trades.update_one(
                {"_id": trade_id},
                {"$set": {
                    "ml_features": features.to_array().tolist(),
                    "ml_decision": decision,
                    "ml_timestamp": datetime.now(timezone.utc)
                }}
            )
        except Exception as e:
            logger.error(f"Fehler beim Speichern der ML-Features: {e}")
    
    async def train_model(self, user_id: str = None):
        """
        Trainiere das ML-Modell mit gesammelten Daten
        """
        if not ML_AVAILABLE:
            logger.warning("sklearn nicht verfügbar - Training übersprungen")
            return False
        
        # Sammle aktuelle Daten
        if user_id:
            await self.collect_training_data(user_id)
        
        if len(self.training_data) < self.MIN_SAMPLES_FOR_TRAINING:
            logger.info(f"ML: Nur {len(self.training_data)} Samples - brauche mindestens {self.MIN_SAMPLES_FOR_TRAINING}")
            return False
        
        try:
            # Bereite Daten vor
            X = np.array([d['features'] for d in self.training_data])
            y = np.array([d['label'] for d in self.training_data])
            
            # Normalisiere Features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Train/Test Split
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            
            # Trainiere Gradient Boosting Classifier
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            self.model.fit(X_train, y_train)
            
            # Evaluiere
            self.model_accuracy = self.model.score(X_test, y_test)
            
            logger.info(f"ML-Modell trainiert! Accuracy: {self.model_accuracy:.2%}")
            logger.info(f"Feature Importance: {dict(zip(TradeFeatures.feature_names(), self.model.feature_importances_))}")
            
            # Speichere Modell
            self._save_model()
            
            self.trades_since_last_train = 0
            return True
            
        except Exception as e:
            logger.error(f"ML Training fehlgeschlagen: {e}")
            return False
    
    async def predict_exit(self, features: TradeFeatures) -> Dict:
        """
        ML-basierte Exit-Entscheidung
        
        Returns:
            {
                'should_exit': bool,
                'confidence': float (0-100),
                'reasoning': str,
                'model_used': bool
            }
        """
        # Wenn kein Modell trainiert ist, return neutral
        if not self.model or not self.scaler or not ML_AVAILABLE:
            return {
                'should_exit': False,
                'confidence': 50,
                'reasoning': 'ML-Modell noch nicht trainiert - sammle Daten',
                'model_used': False,
                'exploration_mode': True
            }
        
        try:
            # Bereite Features vor
            X = features.to_array().reshape(1, -1)
            X_scaled = self.scaler.transform(X)
            
            # Vorhersage
            prediction = self.model.predict(X_scaled)[0]
            probabilities = self.model.predict_proba(X_scaled)[0]
            
            # Confidence ist die Wahrscheinlichkeit der gewählten Klasse
            confidence = max(probabilities) * 100
            
            # Exit wenn Modell "Verlust" vorhersagt mit hoher Konfidenz
            should_exit = prediction == 0 and confidence > 65
            
            self.total_predictions += 1
            
            reasoning = f"ML-Vorhersage: {'Exit' if prediction == 0 else 'Halten'} (Konfidenz: {confidence:.1f}%)"
            reasoning += f" | Modell-Accuracy: {self.model_accuracy:.1%}"
            
            return {
                'should_exit': should_exit,
                'confidence': confidence,
                'reasoning': reasoning,
                'model_used': True,
                'prediction': int(prediction),
                'probabilities': probabilities.tolist(),
                'exploration_mode': False
            }
            
        except Exception as e:
            logger.error(f"ML Prediction Fehler: {e}")
            return {
                'should_exit': False,
                'confidence': 50,
                'reasoning': f'ML-Fehler: {str(e)[:50]}',
                'model_used': False,
                'exploration_mode': True
            }
    
    async def predict_entry(self, features: TradeFeatures) -> Dict:
        """
        ML-basierte Entry-Entscheidung (soll gekauft werden?)
        """
        if not self.model or not self.scaler or not ML_AVAILABLE:
            return {
                'should_enter': True,  # Im Exploration-Mode: kaufen um Daten zu sammeln
                'confidence': 50,
                'reasoning': 'ML noch im Lernmodus - exploriere',
                'model_used': False,
                'exploration_mode': True
            }
        
        try:
            X = features.to_array().reshape(1, -1)
            X_scaled = self.scaler.transform(X)
            
            prediction = self.model.predict(X_scaled)[0]
            probabilities = self.model.predict_proba(X_scaled)[0]
            confidence = max(probabilities) * 100
            
            # Entry wenn Modell "Gewinn" vorhersagt
            should_enter = prediction == 1 and confidence > 60
            
            return {
                'should_enter': should_enter,
                'confidence': confidence,
                'reasoning': f"ML: {'Kaufen' if prediction == 1 else 'Nicht kaufen'} ({confidence:.1f}%)",
                'model_used': True,
                'exploration_mode': False
            }
            
        except Exception as e:
            logger.error(f"ML Entry Prediction Fehler: {e}")
            return {
                'should_enter': True,
                'confidence': 50,
                'reasoning': 'ML-Fehler - Exploration Mode',
                'model_used': False,
                'exploration_mode': True
            }
    
    async def record_outcome(self, features: TradeFeatures, was_profitable: bool):
        """
        Zeichne Ergebnis eines Trades auf für Lernen
        """
        self.training_data.append({
            'features': features.to_array().tolist(),
            'label': 1 if was_profitable else 0
        })
        
        self.trades_since_last_train += 1
        
        # Re-train wenn genug neue Daten
        if self.trades_since_last_train >= self.RETRAIN_INTERVAL:
            if len(self.training_data) >= self.MIN_SAMPLES_FOR_TRAINING:
                logger.info(f"ML: {self.trades_since_last_train} neue Trades - starte Re-Training")
                await self.train_model()
    
    def get_status(self) -> Dict:
        """Status des ML-Modells"""
        return {
            'ml_available': ML_AVAILABLE,
            'model_trained': self.model is not None,
            'training_samples': len(self.training_data),
            'min_samples_needed': self.MIN_SAMPLES_FOR_TRAINING,
            'model_accuracy': self.model_accuracy,
            'total_predictions': self.total_predictions,
            'trades_since_last_train': self.trades_since_last_train,
            'exploration_mode': self.model is None or len(self.training_data) < self.MIN_SAMPLES_FOR_TRAINING
        }


# Singleton Instance
_ml_model: Optional[MLTradingModel] = None

def get_ml_model(db=None) -> MLTradingModel:
    """Get or create ML Model singleton"""
    global _ml_model
    if _ml_model is None:
        _ml_model = MLTradingModel(db)
    elif db and _ml_model.db is None:
        _ml_model.db = db
    return _ml_model
