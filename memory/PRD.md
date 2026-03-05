# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
Ein Full-Stack Trading-Bot für die MEXC Kryptobörse mit:
- Multi-User-System mit Registrierung/Login
- **KI Learning by Doing** - KI übernimmt nach 10 Trades und lernt aus Fehlern
- **SPOT & FUTURES Trading** mit Hebel (Long & Short)
- **Portfolio-basiertes Position Sizing** (% vom Gesamt-Portfolio, nicht Budget)
- **Coin-Auswahl** - User wählt welche Coins gehandelt werden
- Verschlüsselte API-Key-Speicherung
- Dark-Theme Dashboard

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), Pydantic
- **Frontend:** React, Tailwind CSS, Axios, shadcn/ui
- **Database:** MongoDB
- **Auth:** JWT mit bcrypt Password-Hashing
- **Verschlüsselung:** Fernet für API-Keys
- **Futures API:** MEXC Contract API

## Implementierte Features

### KI Learning Engine (NEU - 05.03.2026)
- [x] **Learning by Doing** - Erste 10 Trades: Bot sammelt Daten
- [x] **KI Übernahme** - Ab Trade 11 übernimmt die KI komplett
- [x] **Feedback-Loop** - KI lernt SOFORT aus jedem Fehler
- [x] **Gelernte Parameter** werden automatisch angepasst:
  - RSI Min/Max
  - ADX Minimum
  - Volume Threshold
  - ATR Multiplier
- [x] **KI Log Tab** - Zeigt was die KI gelernt hat, Fehler, Anpassungen
- [x] **KI Confidence** - Steigt bei Gewinnen, sinkt bei Verlusten

### SPOT & FUTURES Trading
- [x] **MEXC Futures API Client** für gehebelte Positionen
- [x] **Hebel 2x-20x** mit Isolated Margin
- [x] **Long & Short Positionen**
- [x] **AI entscheidet automatisch** zwischen SPOT und FUTURES
  - BULLISH → SPOT Long oder Futures Long
  - BEARISH → Futures Short!
- [x] **Futures Tab** mit Konto, Positionen, Einstellungen

### Coin-Auswahl (NEU - 05.03.2026)
- [x] **SPOT Coins** - User kann "Alle" oder spezifische Coins wählen
- [x] **FUTURES Coins** - Separate Auswahl für Futures
- [x] **Such-Funktion** für schnelles Finden
- [x] **Toggle "Alle handeln"** für einfache Konfiguration

### Position Sizing (NEU - 05.03.2026)
- [x] **Budget-System ENTFERNT**
- [x] **Position = % vom Gesamt-Portfolio**
- [x] KI berechnet optimale Position basierend auf:
  - Aktueller Portfolio-Wert
  - Gelernten Parametern
  - Markt-Regime
  - Confidence

### Settings Tab (Überarbeitet)
- [x] **API Keys** - bleibt
- [x] **Min Order / Max Positionen** - einzige manuelle Einstellungen
- [x] **SPOT Coin Auswahl** mit "Alle handeln" Toggle
- [x] **FUTURES Coin Auswahl** mit "Alle handeln" Toggle
- [x] **Budget/Reserve/Daily Cap ENTFERNT**

### Core Features
- [x] Multi-User-System (Registrierung, Login, JWT-Auth)
- [x] Per-User Daten-Isolation
- [x] Verschlüsselte MEXC API-Key-Speicherung
- [x] ECHTE MEXC API-Verifizierung

## API Endpoints

### KI Learning Endpoints (NEU)
- `GET /api/ki/stats` - KI Statistiken und Lernzustand
- `GET /api/ki/log` - KI Learning Log

### Coin Selection Endpoints (NEU)
- `GET /api/coins/available` - Alle verfügbaren SPOT & FUTURES Coins

### Futures Endpoints
- `GET /api/futures/status` - Futures Konto-Status
- `POST /api/futures/enable` - Futures aktivieren
- `POST /api/futures/disable` - Futures deaktivieren
- `GET /api/futures/pairs` - Verfügbare Futures-Paare
- `POST /api/futures/close-position` - Position schließen
- `POST /api/futures/close-all` - Alle schließen
- `PUT /api/futures/settings` - Futures-Einstellungen

## Offene Aufgaben

### P0 - Sofort
- [ ] **Deployment auf Hetzner** - User muss Code pullen

### P1 - Nächste Priorität
- [ ] KI-Integration in Trading-Loop testen
- [ ] Coin-Auswahl im Worker verwenden

### P2 - Zukünftig
- [ ] User Management Tab
- [ ] E-Mail-Verifizierung

### P3 - Backlog
- [ ] Telegram-Benachrichtigungen
- [ ] Performance-Dashboard

## Changelog
- **05.03.2026:** ✅ KI Learning Engine implementiert (Learning by Doing)
- **05.03.2026:** ✅ Budget-System komplett entfernt
- **05.03.2026:** ✅ Position Sizing auf Gesamt-Portfolio umgestellt
- **05.03.2026:** ✅ Coin-Auswahl für SPOT & FUTURES
- **05.03.2026:** ✅ Settings Tab überarbeitet
- **05.03.2026:** ✅ KI Log Tab hinzugefügt
- **05.03.2026:** ✅ FUTURES Trading implementiert

## Architektur

```
/app
├── backend/
│   ├── ki_learning_engine.py   # NEU: KI Learning by Doing
│   ├── mexc_futures_client.py  # Futures API Client
│   ├── ai_engine_v2.py         # AI Engine mit Futures
│   ├── ml_data_collector.py    # ML Datensammlung
│   ├── worker.py               # Trading Worker
│   ├── server.py               # FastAPI Server
│   └── models.py               # Datenmodelle
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── SettingsTab.js      # NEU: Coin-Auswahl UI
│       │   ├── KILogTab.js         # NEU: KI Learning Log
│       │   ├── FuturesTab.js       # Futures UI
│       │   └── ...
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
