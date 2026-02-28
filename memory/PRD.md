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
- [x] **NEU:** Trading Budget Limits (pro User)
- [x] **NEU:** Paper Start Balance konfigurierbar
- [x] **NEU:** Max Order Notional Limit
- [x] **NEU:** Fees & Slippage Simulation für Paper Trades
- [x] **NEU:** Budget-Anzeige im Dashboard (Budget/Used/Available)

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
- `POST /api/auth/register` - Benutzer registrieren
- `POST /api/auth/login` - Einloggen (Rate Limited: 5/min)
- `GET /api/status` - Bot-Status abrufen
- `POST /api/bot/start` - Bot starten
- `POST /api/bot/stop` - Bot stoppen
- `POST /api/bot/live/request` - Live-Modus anfordern
- `POST /api/bot/live/confirm` - Live-Modus bestätigen (Rate Limited: 3/min)
- `POST /api/keys/mexc` - MEXC API-Keys setzen
- `GET /api/keys/mexc/status` - Key-Status prüfen
- `GET /api/account/balance` - Balance + Budget Info abrufen
