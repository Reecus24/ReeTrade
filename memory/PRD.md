# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Vollautomatischer SPOT Trading**
- **Reinforcement Learning AI** (Echte Lern-KI)
- **Telegram Benachrichtigungen**
- **Cyberpunk UI Design**

## Aktueller Stand (2025-12)
Der Bot verwendet jetzt **ausschließlich Reinforcement Learning (RL-AI)** für alle Trading-Entscheidungen. Alle alten, regelbasierten AI-Modi wurden entfernt.

## Implementierte Features

### Reinforcement Learning AI ✅
- **Q-Learning basierte KI** die aus jedem Trade lernt
- **Exploration/Exploitation Balance** - startet mit 100% Exploration
- **22 Market Features** werden analysiert (RSI, EMA, Volume, etc.)
- **Aktionen:** BUY, SELL, HOLD
- **Reward System:** Profit = positive Belohnung, Verlust = negative
- **Memory System:** Speichert vergangene Trades für Training
- **Status Endpoint:** `/api/rl/status` zeigt Lernfortschritt

### Cyberpunk UI Design ✅
- **Neon-Farbschema:** Cyan (#00f0ff), Magenta (#ff00ff), Gelb (#ffff00)
- **Orbitron Font** für Überschriften
- **Share Tech Mono** für Terminal-Stil
- **Glow-Effekte** für aktive Elemente
- **Scanlines** und Grid-Hintergrund
- **Terminal-Style Logs**
- **Cyberpunk-Panels** mit Neon-Borders

### Telegram Integration ✅
**Bot:** @ReeTrade_Bot

**Automatische Benachrichtigungen:**
- 🟢 Trade geöffnet
- 🔴 Trade geschlossen  
- 🛑 Stop-Loss ausgelöst
- 🎯 Take-Profit erreicht
- 🧠 RL-KI Exit Entscheidung
- 📊 Tägliche Zusammenfassung um 21:00 Uhr

**Befehle:**
- `/status` - Offene Positionen
- `/profit` - Heutiger Profit
- `/balance` - Wallet-Stand
- `/trades` - Letzte 5 Trades
- `/ki` - KI Status & Lernfortschritt
- `/link` - Telegram Account verknüpfen
- `/help` - Hilfe

### ENTFERNTE Features (Cleanup)
- ❌ **KI Explorer Mode** - entfernt
- ❌ **KI Hyper Mode** - entfernt
- ❌ **AI Conservative/Moderate/Aggressive** - entfernt
- ❌ **ML Model (GradientBoostingClassifier)** - entfernt
- ❌ **KI Learning Engine** - entfernt
- ❌ **ML Data Collector** - entfernt
- ❌ **FUTURES Trading** - deaktiviert wegen MEXC IP-Block

## Technischer Stack
- **Frontend:** React + TailwindCSS + shadcn/ui
- **Backend:** FastAPI + Python
- **Datenbank:** MongoDB
- **ML:** RL-AI mit Q-Learning (eigene Implementierung)
- **Deployment:** Hetzner VPS + systemd

## API Endpoints

**Auth:**
- `POST /api/auth/login`
- `POST /api/auth/register`

**RL-AI:**
- `GET /api/rl/status` - RL-KI Status & Metriken
- `GET /api/ki/stats` - Gelernte Parameter

**Trading:**
- `GET /api/status` - Bot Status
- `POST /api/live/start` - Trading starten
- `POST /api/live/stop` - Trading stoppen
- `GET /api/account/balance` - Wallet
- `POST /api/positions/sell` - Position verkaufen
- `POST /api/positions/sync` - Mit MEXC sync

**Telegram:**
- `GET /api/telegram/link-code` - Link Code generieren
- `GET /api/telegram/link-status` - Link Status
- `POST /api/telegram/test` - Test Nachricht

## Deployment auf Hetzner

```bash
# Wichtig: Nur reetrade-backend verwenden!
sudo systemctl stop reetrade-worker && sudo systemctl disable reetrade-worker

cd /opt/reetrade
git pull
cd backend
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl restart reetrade-backend

# Logs prüfen:
sudo journalctl -u reetrade-backend -f --since "1 minute ago"
```

## Bekannte Issues

### P1 - Wichtig
- **`_buying_positions` Bug** - muss auf Server verifiziert werden
- **Dueling Worker Services** - User muss `reetrade-worker` deaktivieren

## Offene Aufgaben

### P1
- [ ] Code auf Hetzner Server deployen
- [ ] RL-KI mit echten Trades testen
- [ ] Telegram Befehle verifizieren

### P2 (Zukunft)
- [ ] Paper Trading Modus für risikofreies KI-Training
- [ ] RL-Modelle pro User in DB speichern
- [ ] FUTURES Trading wieder aktivieren
- [ ] History Reset Script ausführen

## Code Cleanup Summary

### Entfernte Imports
- `ki_learning_engine.get_ki_engine`
- `ml_data_collector.get_ml_collector`
- `ml_trading_model.get_ml_model, MLTradingModel, TradeFeatures`
- `ai_engine_v2.AITradingEngineV2, ai_engine_v2`
- `smart_exit_engine.check_position_exit, PositionContext`

### Entfernte Objekte
- `self.ai_engine` - Alter AI Engine
- `self.ml_collector` - ML Data Collector
- `self.ki_engine` - KI Learning Engine
- `self.ml_model` - ML Trading Model
- `ai_decision` - Alte AI Decision Variable

### Vereinfachte Logik
- TradingMode: Nur noch `RL_AI` und `MANUAL`
- Entry Decision: Nur noch RL-AI
- Exit Decision: Nur noch RL-AI + SL/TP Fallback
- Alle alten "KI Learning" und "ML Model" Checks entfernt

## Changelog

### 2025-12 - Cleanup & RL-AI Only
- ✅ Alle alten AI-Modi entfernt
- ✅ Worker auf reine RL-AI Logik umgestellt
- ✅ Unbenutzte Imports entfernt
- ✅ ML Collector und KI Learning Engine entfernt
- ✅ Code-Linting durchgeführt
- ✅ Backend startet ohne Fehler

### 2025-12 - Cyberpunk UI
- ✅ Neon-Farbschema implementiert
- ✅ Orbitron + Share Tech Mono Fonts
- ✅ Glow-Effekte und Scanlines
- ✅ Alle Komponenten im Cyberpunk-Stil
