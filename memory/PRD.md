# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
Ein Full-Stack Trading-Bot für die MEXC Kryptobörse mit:
- Multi-User-System mit Registrierung/Login
- Adaptive Trading-Strategie (Market Regime Detection, Momentum Rotation)
- **NUR Live-Trading-Modus** (Paper Mode wurde entfernt)
- MEXC Trade History Sync
- **NEU: Dual Mode System (Manual + AI)**
- Verschlüsselte API-Key-Speicherung
- Dark-Theme Dashboard

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), Pydantic
- **Frontend:** React, Tailwind CSS, Axios, shadcn/ui
- **Database:** MongoDB
- **Auth:** JWT mit bcrypt Password-Hashing
- **Verschlüsselung:** Fernet für API-Keys
- **Rate Limiting:** slowapi

## Implementierte Features (Stand: 1. März 2026)

### Core Features
- [x] Multi-User-System (Registrierung, Login, JWT-Auth)
- [x] Per-User Daten-Isolation
- [x] **NUR Live-Trading-Modus** (Paper Mode komplett entfernt)
- [x] Verschlüsselte MEXC API-Key-Speicherung

### 🤖 NEU: Dual Mode System (Manual + AI)
- [x] **4 Trading-Modi:**
  - **Manual:** Volle Kontrolle mit eigenen Settings
  - **AI Konservativ:** Kleine Positionen, enge Stops, max 2 Positionen
  - **AI Moderat:** Ausgewogener Ansatz, max 3 Positionen
  - **AI Aggressiv:** Größere Positionen, weitere Stops, max 5 Positionen

- [x] **AI überschreibt manuelle Settings basierend auf:**
  - Markt-Regime (Bullish/Bearish/Sideways)
  - Volatilität (ATR Percentile)
  - Momentum Score
  - Account Drawdown

- [x] **AI entscheidet:**
  - Entry (wann einsteigen - Regime + ADX Check)
  - Position Size (% vom Budget, angepasst an Volatilität)
  - TP/SL (dynamisch basierend auf Volatilität)
  - Max Positions (reduziert bei Drawdown)

- [x] **AI Status Panel zeigt:**
  - Confidence Score (0-100%)
  - Risiko Score (0-100)
  - AI Reasoning (Entscheidungsgründe)
  - Override Liste (was wurde von AI geändert)

### Trading Engine
- [x] ECHTE BUY und SELL Orders auf MEXC Exchange
- [x] High-Frequency Exit Loop (30 Sekunden) für Stop Loss/Take Profit
- [x] Signal Scan Loop (5 Minuten) für neue Entries
- [x] MEXC History Sync (90 Sekunden) - erkennt externe Verkäufe
- [x] "Best-of-N" Trading Strategie - nur bester Signal wird ausgeführt
- [x] Dynamisches Coin-Universum (alle USDT-Paare von MEXC)
- [x] Adaptive Market Regime Detection (Bullish/Bearish/Sideways)
- [x] Momentum Rotation Universe-Selektion

### Dashboard
- [x] Echtes MEXC Wallet (USDT Free/Locked/Total)
- [x] Budget System (Reserve, Budget, Available)
- [x] Daily Trading Cap mit Progress Bar
- [x] Bot Status Panel (Letzter Scan, Entscheidung, Regime)
- [x] **NEU: Trading Mode Selector (Manual/AI)**
- [x] **NEU: AI Status Panel mit Confidence & Overrides**
- [x] Positionen-Panel mit manuellem Sell-Button
- [x] Trades Tab mit Historie und Charts
- [x] Logs Tab (Live-gefiltert)
- [x] Settings Tab (vereinfacht für nur Live)

### Safety Features
- [x] Reserve-System für Wallet-Schutz
- [x] Daily Trading Cap
- [x] Max Order Limit
- [x] Min Notional Check
- [x] **NEU: AI Drawdown Protection** (Trading stoppt bei Max Drawdown)
- [x] **NEU: AI Daily Trade Limit** (pro Risikoprofil)
- [x] Rate Limiting für Login und Live-Mode Endpoints

## AI Risk Profile Details

### Konservativ
- Position: 1.5-2.5% vom Budget
- Max Positions: 2
- Stop Loss: 1.5%
- Take Profit: 3% (2:1 R:R)
- Nur bei BULLISH Regime
- Max Drawdown: 5% (dann Trading stopp)
- Max 3 Trades pro Tag

### Moderat
- Position: 3-4.5% vom Budget
- Max Positions: 3
- Stop Loss: 2.5%
- Take Profit: 6.25% (2.5:1 R:R)
- Bei BULLISH und SIDEWAYS Regime
- Max Drawdown: 10%
- Max 5 Trades pro Tag

### Aggressiv
- Position: 5-7% vom Budget
- Max Positions: 5
- Stop Loss: 3.5%
- Take Profit: 10.5% (3:1 R:R)
- Bei BULLISH und SIDEWAYS Regime
- Max Drawdown: 15%
- Max 8 Trades pro Tag

## API Endpoints

### AI Endpoints (NEU)
- `GET /api/ai/profiles` - Alle AI Profile mit Details
- `GET /api/ai/status` - Aktueller AI Entscheidungsstatus

### Live Mode Control
- `POST /api/live/start` - Live Bot starten
- `POST /api/live/stop` - Live Bot stoppen
- `POST /api/live/request` - Live Mode anfordern
- `POST /api/live/confirm` - Live Mode bestätigen
- `POST /api/live/revoke` - Live Mode widerrufen

### Trades & Metrics
- `GET /api/metrics/daily_pnl?days=30` - Daily PnL
- `GET /api/trades` - Trade History

### Settings (mit trading_mode)
- `GET /api/settings` - Einstellungen abrufen
- `PUT /api/settings` - Einstellungen aktualisieren (inkl. trading_mode)

## Test-Credentials
- **Email:** test@example.com
- **Password:** testpass123

## Offene Aufgaben

### P1 - Nächste Priorität
- [ ] MEXC API Keys neu eingeben (alte sind ungültig)
- [ ] AI System live testen mit echten Trades

### P2 - Zukünftig
- [ ] User Management Tab für Admin-Rolle
- [ ] E-Mail-Verifizierung bei Registrierung
- [ ] Passwort-Zurücksetzen-Funktion
- [ ] Performance-Dashboard mit Charts (Sharpe Ratio, Win Rate)

### P3 - Backlog
- [ ] Telegram/E-Mail Benachrichtigungen
- [ ] Erweiterte Audit-Log UI

## Changelog
- **01.03.2026:** Dual Mode System implementiert (Manual + AI)
- **01.03.2026:** 3 AI Risikoprofile: Konservativ, Moderat, Aggressiv
- **01.03.2026:** AI Override Tracking mit UI Anzeige
- **01.03.2026:** MEXC History Sync implementiert
- **01.03.2026:** Paper Mode komplett entfernt - nur noch Live Trading
- **28.02.2026:** Vollständige Transparenz für Trading-Entscheidungen
- **28.02.2026:** ECHTE BUY und SELL Orders auf MEXC implementiert

## Architektur

```
/app
├── backend/
│   ├── ai_engine.py        # NEU: AI Trading Engine mit 3 Profilen
│   ├── worker.py           # Trading Worker mit AI Integration
│   ├── server.py           # FastAPI Server mit AI Endpoints
│   ├── models.py           # Extended mit trading_mode
│   └── ...
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── TradingModeSelector.js  # NEU: Manual/AI Dropdown
│       │   ├── AIStatusPanel.js        # NEU: Confidence/Risk Display
│       │   └── ...
│       └── pages/
│           └── DashboardPage.js
└── memory/
    └── PRD.md
```
