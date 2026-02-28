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
- [x] Paper-Trading-Modus
- [x] Live-Trading-Modus
- [x] Verschlüsselte MEXC API-Key-Speicherung
- [x] Adaptive Market Regime Detection (Bullish/Bearish/Sideways)
- [x] Momentum Rotation Universe-Selektion
- [x] EMA Crossover + RSI Strategie
- [x] Rate Limiting für Login und Live-Mode Endpoints
- [x] Audit Logging

## Bug Fixes (28. Februar 2026)
- [x] **P0:** 500 Internal Server Error beim Live-Modus-Wechsel behoben
  - Ursache: `slowapi` Parameter-Naming-Konflikt (`req: Request` vs `request: LiveConfirmRequest`)
  - Fix: Parameter umbenannt zu `request: Request` und `body: LiveConfirmRequest`

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
