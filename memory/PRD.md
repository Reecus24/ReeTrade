# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Learning by Doing AI** - KI übernimmt nach 10 Trades
- **SPOT & FUTURES Trading** (komplett getrennt)
- **Alles automatisch** - KI setzt Limits, SL/TP selbst
- Portfolio-basiertes Position Sizing (% vom Wallet, kein festes Budget)

## Implementierte Features (05.03.2026)

### Neue Tab-Struktur
- **Settings Tab** - Oben positioniert
- **SPOT Tab** - Separate History für SPOT Trades
- **FUTURES Tab** - Separate History + Konto + Positionen + API Test
- **KI Log Tab** - Was die KI gelernt hat
- **Logs Tab** - System Logs
- **Info Tab als Default** - Öffnet sich beim Start

### SPOT History
- Eigene History nur für SPOT Trades
- PnL Chart getrennt
- Win Rate nur für SPOT

### FUTURES Tab (komplett)
- **Futures Konto** - Balance, Margin, PnL
- **Offene Positionen** - Live mit Liquidationspreis
- **Futures History** - Alle Long/Short Trades
- **Einstellungen** - Hebel, Short erlauben
- **API Test Button** - Diagnose bei Verbindungsproblemen
- **Hilfreiche Fehlermeldungen** - Mit Lösungsvorschlägen

### KI Learning Engine
- Erste 10 Trades: Datensammlung
- Ab Trade 11: KI übernimmt
- Feedback-Loop: Lernt aus Fehlern
- Gelernte Parameter automatisch angepasst

### Entfernt
- Budget/Reserve System
- Manuelle Limit-Eingabe
- Daily Cap

## Aktuelle Probleme

### Futures API (P0 - auf Benutzer-Server)
- MEXC Futures API gibt "Access Denied" oder leere Antwort
- **Mögliche Ursachen:**
  1. API-Key hat keine Futures-Berechtigung aktiviert
  2. IP-Whitelist blockiert den Server
- **Diagnose:** Neuer "API Test" Button im FUTURES Tab
- **Lösung:** Benutzer muss MEXC API-Key Einstellungen prüfen

## Deployment auf Hetzner

```bash
# 1. Code aktualisieren
cd /opt/reetrade && git pull origin main

# 2. Frontend neu bauen
cd frontend && yarn install && yarn build && cd ..

# 3. Services neustarten
sudo systemctl restart reetrade-backend reetrade-worker
```

## Offene Aufgaben

### P0
- [ ] Futures API Fehler debuggen (auf Hetzner Server)

### P1
- [ ] KI Learning Engine verifizieren (nach API-Fix)
- [ ] Coin-Auswahl im Worker testen

### P2
- [ ] Telegram-Benachrichtigungen
- [ ] User Management Admin Tab
- [ ] Email-Verifizierung

## Architektur

```
/opt/reetrade/
├── backend/
│   ├── ai_engine_v2.py        # AI Trading Logic
│   ├── ki_learning_engine.py  # Learning by Doing AI
│   ├── mexc_futures_client.py # Futures API Client (verbessertes Logging)
│   ├── server.py              # FastAPI Backend (neuer /api/futures/test Endpoint)
│   └── worker.py              # Trading Worker
├── frontend/
│   └── src/
│       ├── pages/DashboardPage.js
│       └── components/
│           ├── FuturesTab.js  # Mit API Test Button
│           ├── TradesTab.js   # SPOT/FUTURES getrennt
│           └── InfoTab.js
└── HETZNER_DEPLOYMENT.md
```

## Wichtige Endpoints

- `GET /api/futures/status` - Futures Konto Status
- `GET /api/futures/test` - API Connectivity Test (NEU)
- `GET /api/trades?market_type=spot|futures` - Getrennte Historie
- `GET /api/ki/log` - KI Learning Log
