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
- **FUTURES TRADING mit Hebel (Long & Short)** - NEU!
- Verschlüsselte API-Key-Speicherung
- Dark-Theme Dashboard

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), Pydantic
- **Frontend:** React, Tailwind CSS, Axios, shadcn/ui
- **Database:** MongoDB
- **Auth:** JWT mit bcrypt Password-Hashing
- **Verschlüsselung:** Fernet für API-Keys
- **Rate Limiting:** slowapi
- **Futures API:** MEXC Contract API

## Implementierte Features

### Core Features
- [x] Multi-User-System (Registrierung, Login, JWT-Auth)
- [x] Per-User Daten-Isolation
- [x] **NUR Live-Trading-Modus** (Paper Mode komplett entfernt)
- [x] Verschlüsselte MEXC API-Key-Speicherung
- [x] **ECHTE MEXC API-Verifizierung** für Connection Status

### AI V2 - Dynamisches Position Sizing
- [x] **Position Size = % vom verfügbaren USDT**
- [x] **Trading Budget fungiert nur noch als Cap/Exposure-Limit**
- [x] **Confidence-basierte Skalierung:** Hohe Confidence (>85%) → obere Range
- [x] **Exposure Tracking:** Mehrere offene Positionen = % nur auf Rest-USDT

### FUTURES TRADING - NEU (05.03.2026)
- [x] **MEXC Futures API Client** (`mexc_futures_client.py`)
- [x] **Unterstützung für Hebel 2x-20x**
- [x] **Long & Short Positionen**
- [x] **Isolated Margin Modus**
- [x] **1-2% Risiko pro Trade (konservativ)**
- [x] **AI entscheidet automatisch zwischen SPOT und FUTURES**
  - BULLISH → SPOT Long oder Futures Long (low leverage)
  - SIDEWAYS → SPOT (safer)
  - BEARISH → Futures Short (Profit von fallenden Kursen!)
- [x] **Futures Tab in der UI** mit:
  - Konto-Übersicht (Balance, PnL)
  - Offene Futures-Positionen
  - Hebel-Einstellungen (Default, Max)
  - Risiko pro Trade (%)
  - Short-Erlaubnis Toggle
  - Risiko-Warnung

**Futures Profile Einstellungen:**
| Profil | Hebel Min | Hebel Max | Hebel Default | Shorts erlaubt | Risk Reduction |
|--------|-----------|-----------|---------------|----------------|----------------|
| 🔴 Aggressiv | 3x | 10x | 5x | Ja | 50% |
| 🟡 Moderat | 2x | 5x | 3x | Ja | 60% |
| 🟢 Konservativ | 2x | 3x | 2x | Nein | 40% |
| 🔬 KI Explorer | 2x | 10x | 5x | Ja | 50% |

### KI Explorer Mode
- [x] Experimenteller Modus für ML-Datensammlung
- [x] Variiert Trading-Parameter (RSI, ADX, SL, TP)
- [x] Sammelt diverse Daten für zukünftiges ML-Modell
- [x] Auch für Futures-Experimente aktiviert

### ML Datensammlung
- [x] `ml_data_collector.py` für Training-Snapshots
- [x] Speichert Marktbedingungen bei Kauf/Verkauf
- [x] Erweitert für Futures-Daten (Funding Rate, OI, Direction)
- [x] KI Training Tab in der UI

### Trading Engine
- [x] ECHTE BUY und SELL Orders auf MEXC Exchange (SPOT)
- [x] ECHTE Futures Long/Short Orders auf MEXC
- [x] High-Frequency Exit Loop (1 Sekunde) für Stop Loss/Take Profit
- [x] Signal Scan Loop (1 Minute) für neue Entries
- [x] MEXC History Sync (90 Sekunden)
- [x] "Best-of-N" Trading Strategie
- [x] Adaptive Market Regime Detection
- [x] Automatische SPOT/FUTURES Entscheidung basierend auf Markt-Regime

### Dashboard
- [x] Echtes MEXC Wallet (USDT Free/Locked/Total)
- [x] Budget System (Reserve, Budget als Cap, Available)
- [x] Daily Trading Cap mit Progress Bar
- [x] Bot Status Panel (Letzter Scan, Entscheidung, Regime)
- [x] **Futures Tab** mit Konto-Status, Positionen, Einstellungen
- [x] AI V2 Status Panel mit Position Size %, ATR SL, R:R TP
- [x] Positionen-Panel mit Live PnL und manuellem Sell
- [x] KI Training Tab für ML-Statistiken

## API Endpoints

### Futures Endpoints (NEU)
- `GET /api/futures/status` - Futures Konto-Status und Balance
- `POST /api/futures/enable` - Futures Trading aktivieren
- `POST /api/futures/disable` - Futures Trading deaktivieren
- `GET /api/futures/pairs` - Verfügbare Futures-Paare
- `POST /api/futures/close-position` - Einzelne Position schließen
- `POST /api/futures/close-all` - Alle Positionen schließen
- `PUT /api/futures/settings` - Futures-Einstellungen ändern

### AI V2 Endpoints
- `GET /api/ai/profiles` - Alle AI Profile mit dynamischer Position-Berechnung
- `GET /api/ai/preview/{mode}` - Detaillierte Vorschau eines Profils
- `GET /api/ai/status` - Aktueller AI Entscheidungsstatus

### ML Endpoints
- `GET /api/ml/stats` - ML Training Statistiken
- `GET /api/ml/training-data` - Export für ML Training

### Live Mode Control
- `POST /api/live/start` - Live Bot starten
- `POST /api/live/stop` - Live Bot stoppen
- `POST /api/live/confirm` - Live Mode bestätigen

## Offene Aufgaben

### P0 - Aktuelle Priorität
- [ ] **Verifizierung auf Hetzner Server** - User muss die neuesten Änderungen deployen

### P1 - Nächste Priorität
- [ ] **Erstes ML-Modell trainieren** (nach ~100-500 Trades)
- [ ] **ML-Modell in Bot integrieren** (als "Final Check" vor Trades)
- [ ] User Management Tab für Admin-Rolle

### P2 - Zukünftig
- [ ] E-Mail-Verifizierung bei Registrierung
- [ ] Passwort-Zurücksetzen-Funktion
- [ ] Performance-Dashboard (Sharpe Ratio, Win Rate, Equity Curve)

### P3 - Backlog
- [ ] Telegram/E-Mail Benachrichtigungen
- [ ] Erweiterte Audit-Log UI
- [ ] Adaptive Risk Scaling (Pause nach 3 Verlusten)

## Changelog
- **05.03.2026:** ✅ FUTURES TRADING implementiert - Long & Short mit Hebel 2x-20x
- **05.03.2026:** ✅ `mexc_futures_client.py` erstellt für MEXC Contract API
- **05.03.2026:** ✅ Futures Tab in UI mit Konto, Positionen, Einstellungen
- **05.03.2026:** ✅ AI entscheidet automatisch zwischen SPOT und FUTURES
- **05.03.2026:** ✅ BEARISH Märkte → Futures Short (Profit von fallenden Kursen)
- **05.03.2026:** ✅ Isolated Margin, 1-2% Risiko, Liquidationspreis-Berechnung
- **04.03.2026:** ✅ KI Explorer Mode für ML-Datensammlung
- **04.03.2026:** ✅ ML Data Collection Framework
- **01.03.2026:** ✅ AI V2 Position Sizing implementiert
- **01.03.2026:** ✅ ATR-basiertes Stop Loss (1.5x-2.5x ATR je nach Profil)

## Architektur

```
/app
├── backend/
│   ├── mexc_futures_client.py  # NEU: Futures API Client
│   ├── ai_engine_v2.py         # AI V2 Engine mit Futures-Entscheidung
│   ├── ml_data_collector.py    # ML Training Datensammlung
│   ├── worker.py               # Trading Worker mit SPOT & FUTURES
│   ├── server.py               # FastAPI Server mit Futures Endpoints
│   └── models.py               # Erweiterte Models für Futures
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── FuturesTab.js          # NEU: Futures UI
│       │   ├── TradingModeSelector.js
│       │   └── MLStatsTab.js          # KI Training Tab
│       └── pages/
│           └── DashboardPage.js
└── memory/
    └── PRD.md
```

## Deployment
- **Hetzner Cloud VPS:** 178.104.19.199
- **Services:** systemd (reetrade-backend, reetrade-worker)
- **Webserver:** Nginx als Reverse Proxy
- **Repository:** GitHub (Reecus24/ReeTrade)
