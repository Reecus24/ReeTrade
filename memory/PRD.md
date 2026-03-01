# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
Ein Full-Stack Trading-Bot für die MEXC Kryptobörse mit:
- Multi-User-System mit Registrierung/Login
- Adaptive Trading-Strategie (Market Regime Detection, Momentum Rotation)
- **NUR Live-Trading-Modus** (Paper Mode wurde entfernt)
- MEXC Trade History Sync
- **Dual Mode System (Manual + AI V2)**
- **AI V2 mit dynamischer Position-Sizing basierend auf verfügbarem USDT**
- **ATR-basierte Stop Loss / Risk:Reward Take Profit**
- Verschlüsselte API-Key-Speicherung
- Dark-Theme Dashboard

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), Pydantic
- **Frontend:** React, Tailwind CSS, Axios, shadcn/ui
- **Database:** MongoDB
- **Auth:** JWT mit bcrypt Password-Hashing
- **Verschlüsselung:** Fernet für API-Keys
- **Rate Limiting:** slowapi

## Implementierte Features

### Core Features
- [x] Multi-User-System (Registrierung, Login, JWT-Auth)
- [x] Per-User Daten-Isolation
- [x] **NUR Live-Trading-Modus** (Paper Mode komplett entfernt)
- [x] Verschlüsselte MEXC API-Key-Speicherung
- [x] **ECHTE MEXC API-Verifizierung** für Connection Status

### AI V2 - Dynamisches Position Sizing (NEU - 01.03.2026)
- [x] **Position Size = % vom verfügbaren USDT** (nicht mehr vom Trading Budget!)
- [x] **Trading Budget fungiert nur noch als Cap/Exposure-Limit**
- [x] **Confidence-basierte Skalierung:** Hohe Confidence (>85%) → obere Range
- [x] **Exposure Tracking:** Mehrere offene Positionen = % nur auf Rest-USDT

**Profile Definitionen:**
| Profil | Position % | Max Pos | ATR SL | TP R:R | Risk/Trade |
|--------|-----------|---------|--------|--------|------------|
| 🔴 Aggressiv | 15%-35% | 3 | 2.0x-2.5x | 1:2.5-1:3.5 | 3%-7% |
| 🟡 Moderat | 8%-18% | 2 | 1.5x-2.0x | 1:2.0-1:2.5 | 1.5%-3% |
| 🟢 Konservativ | 3%-8% | 2 | 1.2x-1.8x | 1:1.5-1:2.0 | 0.5%-1% |

**Neue UI-Darstellung:**
- "Position Size: 15%-35% vom verfügbaren USDT"
- "Berechnete Order: $125.00 (Range: $75.00 - $175.00)"
- Trading Budget als Cap wird angezeigt
- ATR-basierter Stop Loss (dynamisch)
- Risk:Reward Take Profit

### Intelligentes Coin-Scanning
- [x] **100 Coins** werden gescannt
- [x] **Intelligente Preisfilterung** basierend auf AI Trade-Größe
- [x] **Batch-Rotation:** 20 Coins pro Batch, automatischer Wechsel bei keinem Signal

### Trading Engine
- [x] ECHTE BUY und SELL Orders auf MEXC Exchange
- [x] High-Frequency Exit Loop (1 Sekunde) für Stop Loss/Take Profit
- [x] Signal Scan Loop (1 Minute) für neue Entries
- [x] MEXC History Sync (90 Sekunden) - erkennt externe Verkäufe
- [x] "Best-of-N" Trading Strategie
- [x] Adaptive Market Regime Detection

### Dashboard
- [x] Echtes MEXC Wallet (USDT Free/Locked/Total)
- [x] Budget System (Reserve, Budget als Cap, Available)
- [x] Daily Trading Cap mit Progress Bar
- [x] Bot Status Panel (Letzter Scan, Entscheidung, Regime)
- [x] **AI V2 Status Panel** mit Position Size %, ATR SL, R:R TP
- [x] Positionen-Panel mit Live PnL und manuellem Sell
- [x] Trades Tab mit Historie
- [x] Logs Tab (Live-gefiltert)

## API Endpoints

### AI V2 Endpoints
- `GET /api/ai/profiles` - Alle AI Profile mit dynamischer Position-Berechnung
- `GET /api/ai/preview/{mode}` - Detaillierte Vorschau eines Profils
- `GET /api/ai/status` - Aktueller AI Entscheidungsstatus

### Live Mode Control
- `POST /api/live/start` - Live Bot starten
- `POST /api/live/stop` - Live Bot stoppen
- `POST /api/live/confirm` - Live Mode bestätigen

### Settings
- `GET /api/settings` - Einstellungen abrufen
- `PUT /api/settings` - Einstellungen aktualisieren (inkl. trading_mode)

## Test-Credentials
- **Email:** test@example.com
- **Password:** testpass123
- **MEXC Keys:** Ungültig (für Error-Handling-Tests)

## Offene Aufgaben

### P1 - Nächste Priorität
- [ ] User Management Tab für Admin-Rolle
- [ ] 1-Sekunden Exit-Loop Performance-Monitoring

### P2 - Zukünftig
- [ ] E-Mail-Verifizierung bei Registrierung
- [ ] Passwort-Zurücksetzen-Funktion
- [ ] Performance-Dashboard (Sharpe Ratio, Win Rate, Equity Curve)

### P3 - Backlog
- [ ] Telegram/E-Mail Benachrichtigungen
- [ ] Erweiterte Audit-Log UI
- [ ] Adaptive Risk Scaling (Pause nach 3 Verlusten)

## Changelog
- **01.03.2026:** ✅ AI V2 Position Sizing implementiert - Position als % vom verfügbaren USDT
- **01.03.2026:** ✅ Trading Budget fungiert nur noch als Cap/Exposure-Limit
- **01.03.2026:** ✅ ATR-basiertes Stop Loss (1.5x-2.5x ATR je nach Profil)
- **01.03.2026:** ✅ Risk:Reward basiertes Take Profit (1:1.5 bis 1:3.5)
- **01.03.2026:** ✅ Neue UI: "Position Size: X% vom verfügbaren USDT" statt "Min-Max Order"
- **01.03.2026:** ✅ Confidence-basierte Skalierung der Position Size
- **01.03.2026:** Testing Agent: 100% Backend, 100% Frontend

## Architektur

```
/app
├── backend/
│   ├── ai_engine_v2.py     # NEU: AI V2 Engine mit dynamischem Position Sizing
│   ├── worker.py           # Trading Worker mit AI V2 Integration
│   ├── server.py           # FastAPI Server mit AI V2 Endpoints
│   └── models.py
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── TradingModeSelector.js  # AIStatusPanelV2 mit neuem Layout
│       │   └── ...
│       └── pages/
│           └── DashboardPage.js
└── memory/
    └── PRD.md
```
