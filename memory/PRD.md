# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
Ein Full-Stack Trading-Bot für die MEXC Kryptobörse mit:
- Multi-User-System mit Registrierung/Login
- Adaptive Trading-Strategie (Market Regime Detection, Momentum Rotation)
- **NUR Live-Trading-Modus** (Paper Mode wurde entfernt)
- MEXC Trade History Sync
- Verschlüsselte API-Key-Speicherung
- Dark-Theme Dashboard

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), Pydantic
- **Frontend:** React, Tailwind CSS, Axios
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

### Trading Engine
- [x] ECHTE BUY und SELL Orders auf MEXC Exchange
- [x] High-Frequency Exit Loop (30 Sekunden) für Stop Loss/Take Profit
- [x] Signal Scan Loop (5 Minuten) für neue Entries
- [x] **NEU:** MEXC History Sync (90 Sekunden) - erkennt externe Verkäufe
- [x] "Best-of-N" Trading Strategie - nur bester Signal wird ausgeführt
- [x] Dynamisches Coin-Universum (alle USDT-Paare von MEXC)
- [x] Adaptive Market Regime Detection (Bullish/Bearish/Sideways)
- [x] Momentum Rotation Universe-Selektion
- [x] EMA Crossover + RSI Strategie

### Dashboard
- [x] Echtes MEXC Wallet (USDT Free/Locked/Total)
- [x] Budget System (Reserve, Budget, Available)
- [x] Daily Trading Cap mit Progress Bar
- [x] Bot Status Panel (Letzter Scan, Entscheidung, Regime)
- [x] Positionen-Panel mit manuellem Sell-Button
- [x] Trades Tab mit Historie und Charts
- [x] Logs Tab (Live-gefiltert)
- [x] Settings Tab (vereinfacht für nur Live)

### Safety Features
- [x] Reserve-System für Wallet-Schutz
- [x] Daily Trading Cap
- [x] Max Order Limit
- [x] Min Notional Check
- [x] Rate Limiting für Login und Live-Mode Endpoints

## MEXC History Sync Feature (NEU)
Der Bot synchronisiert jetzt automatisch alle 90 Sekunden mit deiner MEXC Trade History:
- Wenn du einen Coin direkt auf MEXC verkaufst, wird das automatisch erkannt
- Die Position wird im Bot als "geschlossen" markiert
- PnL wird korrekt berechnet und in der Historie gespeichert

## Budget System

**Reserve System (Hauptschutz):**
- `reserve_usdt`: Sicherheitsreserve - Bot tastet diesen Betrag nie an
- `available_to_bot = max(0, usdt_free - reserve_usdt)`

**Budget Limits:**
- `trading_budget_usdt`: Absolute Obergrenze für Gesamt-Exposure
- `live_max_order_usdt`: Max Größe pro einzelnem Trade
- `live_min_notional_usdt`: Minimale Order-Größe

**Daily Trading Cap:**
- `live_daily_cap_usdt`: Max Handelsvolumen pro Tag
- Reset erfolgt täglich um 00:00 UTC
- Bot stoppt neue Trades wenn Tageslimit erreicht

## API Endpoints

### Live Mode Control
- `POST /api/live/start` - Live Bot starten
- `POST /api/live/stop` - Live Bot stoppen
- `POST /api/live/request` - Live Mode anfordern
- `POST /api/live/confirm` - Live Mode bestätigen
- `POST /api/live/revoke` - Live Mode widerrufen

### Auth & Status
- `POST /api/auth/register` - Benutzer registrieren
- `POST /api/auth/login` - Einloggen
- `GET /api/status` - Bot-Status

### Trades & Metrics
- `GET /api/metrics/daily_pnl?days=30` - Daily PnL
- `GET /api/trades` - Trade History
- `GET /api/trades/symbols` - Gehandelte Symbols

### Account & Keys
- `GET /api/account/balance` - Live Balance + Budget Info
- `POST /api/keys/mexc` - MEXC API-Keys setzen
- `GET /api/keys/mexc/status` - Key-Status

### Positions
- `POST /api/positions/sell` - Position manuell verkaufen

### Settings
- `GET /api/settings` - Einstellungen abrufen
- `PUT /api/settings` - Einstellungen aktualisieren

## Test-Credentials
- **Email:** test@example.com
- **Password:** testpass123

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

## Changelog
- **01.03.2026:** MEXC History Sync implementiert (erkennt externe Verkäufe)
- **01.03.2026:** Paper Mode komplett entfernt - nur noch Live Trading
- **01.03.2026:** Dashboard vereinfacht auf nur Live-Modus
- **01.03.2026:** SettingsTab vereinfacht (nur Live-Einstellungen)
- **01.03.2026:** Paper Trades und Accounts aus DB gelöscht
- **01.03.2026:** Manueller Sell-Button erfolgreich getestet
- **28.02.2026:** Vollständige Transparenz für Trading-Entscheidungen implementiert
- **28.02.2026:** ECHTE BUY und SELL Orders auf MEXC implementiert
