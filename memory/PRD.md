# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Vollautomatischer SPOT Trading**
- **Reinforcement Learning AI** (Echte Lern-KI)
- **Telegram Benachrichtigungen**
- **Cyberpunk UI Design**

## Implementierte Features

### Reinforcement Learning AI (NEU - 2025-12)
- **Q-Learning basierte KI** die aus jedem Trade lernt
- **Exploration/Exploitation Balance** - startet mit 100% Exploration
- **22 Market Features** werden analysiert (RSI, EMA, Volume, etc.)
- **Aktionen:** BUY, SELL, HOLD
- **Reward System:** Profit = positive Belohnung, Verlust = negative
- **Memory System:** Speichert vergangene Trades für Training
- **Status Endpoint:** `/api/rl/status` zeigt Lernfortschritt

### Cyberpunk UI Design (NEU - 2025-12)
- **Neon-Farbschema:** Cyan, Magenta, Gelb
- **Orbitron Font** für Überschriften
- **Share Tech Mono** für Terminal-Stil
- **Glow-Effekte** für aktive Elemente
- **Scanlines** und Grid-Hintergrund
- **Terminal-Style Logs**
- **Cyberpunk-Panels** mit Neon-Borders

### Telegram Integration (Komplett)
**Bot:** @ReeTrade_Bot

**Automatische Benachrichtigungen:**
- 🟢 Trade geöffnet
- 🔴 Trade geschlossen  
- 🛑 Stop-Loss ausgelöst
- 🎯 Take-Profit erreicht
- 🧠 KI Smart Exit Entscheidung
- 📊 Tägliche Zusammenfassung um 21:00 Uhr

**Befehle:**
- `/status` - Offene Positionen
- `/profit` - Heutiger Profit
- `/balance` - Wallet-Stand
- `/trades` - Letzte 5 Trades
- `/ki` - KI Status & Lernfortschritt
- `/link` - Telegram Account verknüpfen
- `/help` - Hilfe

### Smart Exit Engine (Aktiv)
- Intelligente Verkaufsentscheidungen
- Analysiert RSI, Momentum, EMA, Candlestick-Patterns
- Dient jetzt als **Data Provider** für die RL-KI

### Deaktivierte Features
- **FUTURES Trading** - deaktiviert wegen MEXC IP-Block
- **Alte KI-Modi** (KI Explorer, KI Hyper) - ersetzt durch RL-KI

## Technischer Stack
- **Frontend:** React + TailwindCSS + shadcn/ui
- **Backend:** FastAPI + Python
- **Datenbank:** MongoDB
- **ML:** scikit-learn (GradientBoostingClassifier)
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
```

## Bekannte Issues

### P0 - Kritisch
- **`_buying_positions` AttributeError** - Bug im Worker, muss auf Server verifiziert werden
- **Dueling Worker Services** - User muss `reetrade-worker` deaktivieren

### P1 - Wichtig
- Telegram Befehle (`/balance`, `/status`) zeigen manchmal falsche Daten

## Offene Aufgaben

### P1
- [ ] `_buying_positions` Bug beheben und verifizieren
- [ ] RL-KI mit echten Trades testen
- [ ] Telegram Befehle verifizieren

### P2 (Zukunft)
- [ ] Paper Trading Modus für risikofreies KI-Training
- [ ] RL-Modelle pro User in DB speichern
- [ ] FUTURES Trading wieder aktivieren
- [ ] History Reset Script ausführen

## Changelog

### 2025-12 - Cyberpunk & RL-KI Update
- ✅ Reinforcement Learning KI implementiert
- ✅ Alte KI-Modi deaktiviert und versteckt
- ✅ Cyberpunk UI Design für alle Komponenten
- ✅ Login/Register Pages im Cyberpunk-Stil
- ✅ Dashboard mit Neon-Glow Effekten
- ✅ Terminal-Style Logs
- ✅ RL-Status Panel mit Lernfortschritt
- ✅ Deutsche UI-Texte
