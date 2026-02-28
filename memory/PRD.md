# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
Ein Full-Stack Trading-Bot für die MEXC Kryptobörse mit:
- Multi-User-System mit Registrierung/Login
- Adaptive Trading-Strategie (Market Regime Detection, Momentum Rotation)
- Paper- und Live-Trading-Modi
- Verschlüsselte API-Key-Speicherung
- Dark-Theme Dashboard

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), Pydantic
- **Frontend:** React, Tailwind CSS, Axios
- **Database:** MongoDB
- **Auth:** JWT mit bcrypt Password-Hashing
- **Verschlüsselung:** Fernet für API-Keys
- **Rate Limiting:** slowapi

## Implementierte Features (Stand: 28. Februar 2026)
- [x] Multi-User-System (Registrierung, Login, JWT-Auth)
- [x] Per-User Daten-Isolation
- [x] Paper-Trading-Modus mit Live-Marktdaten (Simulated Live)
- [x] Live-Trading-Modus
- [x] Verschlüsselte MEXC API-Key-Speicherung
- [x] Adaptive Market Regime Detection (Bullish/Bearish/Sideways)
- [x] Momentum Rotation Universe-Selektion
- [x] EMA Crossover + RSI Strategie
- [x] Rate Limiting für Login und Live-Mode Endpoints
- [x] Audit Logging
- [x] Live Balance von MEXC API (`GET /api/account/balance`)
- [x] Balance Source Indicator (Paper/Live + Timestamp)
- [x] Fehlerbehandlung bei MEXC API Fehlern im UI
- [x] Trading Budget Limits (pro User)
- [x] Paper Start Balance konfigurierbar
- [x] Max Order Notional Limit
- [x] Fees & Slippage Simulation für Paper Trades
- [x] Budget-Anzeige im Dashboard (Budget/Used/Available)
- [x] Reserve-System für Wallet-Schutz
- [x] Daily PnL Chart (Balkendiagramm, 7/30/90 Tage)
- [x] Trade History Tab mit Pagination und Filtern
- [x] Trade Detail Drawer bei Klick auf Trade
- [x] **NEU:** Strikte Trennung Paper/Live Modi
- [x] **NEU:** Getrennte Running-States (paper_running, live_running)
- [x] **NEU:** Separate Endpoints (/api/paper/*, /api/live/*)
- [x] **NEU:** Zwei-Tab UI (PAPER gelb, LIVE rot)
- [x] **NEU:** Live Tab mit echtem MEXC Wallet (USDT Free/Locked/Total)
- [x] **NEU:** Budget System separat angezeigt (Reserve, Budget, Available)
- [x] **NEU:** Wallet-Werte READ-ONLY
- [x] **NEU:** Verbesserte Settings mit Erklärungen und Tooltips
- [x] **NEU:** Daily Trading Cap für Paper und Live Modi
- [x] **NEU:** Getrennte Settings UI (Paper Settings / Live Settings / Strategie Tabs)
- [x] **NEU:** Daily Cap Progress Bar im Dashboard (Paper & Live)

## Neue Features (28. Februar 2026)

### 1. Paper "Simulated Live" (Forward Test)
- Paper-Mode nutzt echte MEXC 15m Candles und Last Price
- Trades werden mit Fees (bps) und Slippage (bps) simuliert
- Equity/PnL wird realistisch berechnet
- Alle Trades in `trades` Collection gespeichert

### 2. Reserve & Budget System (NEU)
**Reserve System (Hauptschutz):**
- `reserve_usdt`: Sicherheitsreserve - Bot tastet diesen Betrag nie an
- `available_to_bot = max(0, usdt_free - reserve_usdt)`

**Budget Limits (Zusatzschutz):**
- `trading_budget_usdt`: Absolute Obergrenze für Gesamt-Exposure
- `max_order_notional_usdt`: Max Größe pro einzelnem Trade
- `paper_start_balance_usdt`: Startkapital für Paper Mode

**Daily Trading Cap (NEU):**
- `paper_daily_cap_usdt`: Max Handelsvolumen pro Tag im Paper Mode
- `live_daily_cap_usdt`: Max Handelsvolumen pro Tag im Live Mode
- Reset erfolgt täglich um 00:00 UTC
- Bot stoppt neue Trades wenn Tageslimit erreicht

**Live Mode Logik:**
```
available_to_bot = max(0, USDT_free - reserve_usdt)
remaining_budget = min(available_to_bot, trading_budget - used_budget)
```

**Dashboard zeigt (Live):**
- USDT Free (MEXC Wallet)
- Reserve (geschützt)
- Available to Bot
- Used Budget
- Remaining Budget

**Dashboard zeigt (Paper):**
- Start Balance
- Used Budget
- Remaining
- Cash

## Bug Fixes (28. Februar 2026)
- [x] **P0:** 500 Internal Server Error beim Live-Modus-Wechsel behoben

## Offene Aufgaben

### P1 - Nächste Priorität
- [ ] User Management Tab für Admin-Rolle
- [ ] Rate Limiting auf weitere Endpoints erweitern

### P2 - Zukünftig
- [ ] E-Mail-Verifizierung bei Registrierung
- [ ] Passwort-Zurücksetzen-Funktion
- [ ] Performance-Dashboard mit Charts (Sharpe Ratio, Win Rate, Equity Curve)

### P3 - Backlog
- [ ] Telegram/E-Mail Benachrichtigungen
- [ ] Erweiterte Audit-Log UI

## Test-Credentials
- **Email:** test@example.com
- **Password:** testpass123

## API Endpoints

### Paper Mode
- `POST /api/paper/start` - Paper Bot starten
- `POST /api/paper/stop` - Paper Bot stoppen

### Live Mode
- `POST /api/live/start` - Live Bot starten (nur wenn confirmed + keys)
- `POST /api/live/stop` - Live Bot stoppen
- `POST /api/live/request` - Live Mode anfordern
- `POST /api/live/confirm` - Live Mode bestätigen (Rate Limited: 3/min)
- `POST /api/live/revoke` - Live Mode widerrufen

### Auth & Status
- `POST /api/auth/register` - Benutzer registrieren
- `POST /api/auth/login` - Einloggen (Rate Limited: 5/min)
- `GET /api/status` - Bot-Status (paper_running, live_running, etc.)
- `GET /api/logs?mode=paper|live` - Logs gefiltert nach Mode

### Trades & Metrics
- `GET /api/metrics/daily_pnl?days=30&mode=paper` - Daily PnL Aggregation
- `GET /api/trades?mode=paper&limit=200&offset=0` - Trade History
- `GET /api/trades/symbols` - Liste aller gehandelten Symbols

### Account & Keys
- `GET /api/account/balance` - Balance + Budget Info
- `POST /api/keys/mexc` - MEXC API-Keys setzen
- `GET /api/keys/mexc/status` - Key-Status prüfen

### Settings
- `GET /api/settings` - Alle Einstellungen abrufen
- `PUT /api/settings` - Einstellungen aktualisieren (inkl. daily caps)

## Settings Model Struktur
```python
# Paper Mode Settings
paper_start_balance_usdt: float = 500.0
paper_daily_cap_usdt: float = 200.0     # Daily Trading Cap
paper_max_order_usdt: float = 50.0
paper_fee_bps: int = 10
paper_slippage_bps: int = 5

# Live Mode Settings
reserve_usdt: float = 0.0               # Sicherheitsreserve
trading_budget_usdt: float = 500.0      # Max Exposure
live_daily_cap_usdt: float = 200.0      # Daily Trading Cap
live_max_order_usdt: float = 50.0
```

## Changelog
- **28.02.2026:** Daily Trading Cap implementiert (Paper & Live)
- **28.02.2026:** Settings UI in drei Tabs aufgeteilt (Paper/Live/Strategie)
- **28.02.2026:** Backend-Modelle für getrennte Paper/Live Settings erweitert
