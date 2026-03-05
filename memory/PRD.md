# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
Ein Full-Stack Trading-Bot für die MEXC Kryptobörse mit:
- Multi-User-System mit Registrierung/Login
- **KI Learning by Doing** - KI übernimmt nach 10 Trades und lernt aus Fehlern
- **SPOT & FUTURES Trading** mit Hebel (Long & Short)
- **Portfolio-basiertes Position Sizing** (% vom Gesamt-Portfolio)
- **Coin-Auswahl** - User wählt welche Coins gehandelt werden
- Isolated Margin für Futures
- Verschlüsselte API-Key-Speicherung
- Dark-Theme Dashboard

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), Pydantic
- **Frontend:** React, Tailwind CSS, Axios, shadcn/ui
- **Database:** MongoDB
- **Auth:** JWT mit bcrypt Password-Hashing
- **Verschlüsselung:** Fernet für API-Keys

## Implementierte Features

### KI Learning Engine
- [x] **Learning by Doing** - Erste 10 Trades: Bot sammelt Daten
- [x] **KI Übernahme** - Ab Trade 11 übernimmt die KI komplett
- [x] **Feedback-Loop** - KI lernt SOFORT aus jedem Fehler
- [x] **Gelernte Parameter** werden automatisch angepasst
- [x] **KI Log Tab** - Zeigt was die KI gelernt hat
- [x] **KI im Trading-Loop integriert** ✅ P1 ERLEDIGT

### SPOT & FUTURES Trading
- [x] **MEXC Futures API Client** für gehebelte Positionen
- [x] **Hebel 2x-20x** mit **Isolated Margin**
- [x] **Long & Short Positionen**
- [x] **AI entscheidet automatisch** zwischen SPOT und FUTURES
- [x] **Futures Tab** mit Konto, Positionen, Einstellungen

### Coin-Auswahl ✅ P1 ERLEDIGT
- [x] **SPOT Coins** - User kann "Alle" oder spezifische Coins wählen
- [x] **FUTURES Coins** - Separate Auswahl für Futures
- [x] **Coin-Auswahl im Worker integriert**

### Info Tab (NEU)
- [x] **Konzept-Erklärung** - Wie ReeTrade funktioniert
- [x] **SPOT vs FUTURES** Vergleich
- [x] **KI Entscheidungsprozess** visualisiert
- [x] **Markt-Regime Tabelle** (BULLISH/SIDEWAYS/BEARISH)
- [x] **Risk Management** erklärt (SL/TP)
- [x] **Feedback-Loop** erklärt
- [x] **Isolated Margin** erklärt

### Settings Tab
- [x] **API Keys** - bleibt
- [x] **Min Order / Max Positionen**
- [x] **SPOT Coin Auswahl** mit Toggle
- [x] **FUTURES Coin Auswahl** mit Toggle
- [x] **Budget-System ENTFERNT**

## API Endpoints

### KI Learning
- `GET /api/ki/stats` - KI Statistiken
- `GET /api/ki/log` - KI Learning Log

### Coins
- `GET /api/coins/available` - Verfügbare SPOT & FUTURES Coins

### Futures
- `GET /api/futures/status` - Konto-Status
- `POST /api/futures/enable|disable` - Ein/Ausschalten
- `POST /api/futures/close-position|close-all` - Positionen schließen

## Offene Aufgaben

### P0 - Sofort
- [ ] **Deployment auf Hetzner** - Code pullen und testen

### P2 - Zukünftig
- [ ] User Management Tab
- [ ] E-Mail-Verifizierung
- [ ] Telegram-Benachrichtigungen

## Changelog
- **05.03.2026:** ✅ Info Tab mit Konzept-Erklärung
- **05.03.2026:** ✅ KI in Trading-Loop integriert (P1)
- **05.03.2026:** ✅ Coin-Auswahl im Worker (P1)
- **05.03.2026:** ✅ KI Learning Engine implementiert
- **05.03.2026:** ✅ Budget-System entfernt
- **05.03.2026:** ✅ FUTURES Trading mit Isolated Margin

## Architektur

```
/app
├── backend/
│   ├── ki_learning_engine.py   # KI Learning by Doing
│   ├── mexc_futures_client.py  # Futures API (Isolated Margin)
│   ├── worker.py               # Trading Worker (KI + Coins integriert)
│   └── server.py               # FastAPI Server
├── frontend/
│   └── src/components/
│       ├── SettingsTab.js      # Coin-Auswahl UI
│       ├── KILogTab.js         # KI Learning Log
│       ├── FuturesTab.js       # Futures UI
│       └── InfoTab.js          # Konzept-Erklärung
└── memory/PRD.md
```

## Deployment
- **Hetzner Cloud VPS:** 178.104.19.199
- **Repository:** GitHub (Reecus24/ReeTrade)
