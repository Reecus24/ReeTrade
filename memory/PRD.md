# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Learning by Doing AI** - KI übernimmt nach 10 Trades
- **SPOT & FUTURES Trading** (komplett getrennt)
- **Separate API Keys** für SPOT und FUTURES
- Portfolio-basiertes Position Sizing (% vom Wallet)

## Implementierte Features (05.03.2026)

### NEU: Separate API Keys für SPOT und FUTURES
- SPOT und FUTURES verwenden jetzt **getrennte API Keys**
- Im Settings Tab gibt es zwei separate Bereiche:
  - MEXC SPOT API Keys (blau)
  - MEXC FUTURES API Keys (lila, separater Key)
- Backend speichert beide Keys verschlüsselt in `user_keys` Collection
- Futures-Endpoints verwenden automatisch die Futures-Keys

### Backend Änderungen
- `db_operations.py`: `set_mexc_keys()` und `get_mexc_keys()` unterstützen jetzt `key_type='spot'|'futures'`
- `server.py`: Neuer Endpoint `POST /api/keys/mexc/futures` für Futures-Keys
- Alle Futures-Endpoints (`/api/futures/*`) verwenden jetzt Futures-spezifische Keys

### Frontend Änderungen
- `SettingsTab.js`: Zwei getrennte Bereiche für SPOT und FUTURES Keys
- Status-Badges zeigen getrennt: SPOT verbunden / FUTURES verbunden

## Deployment auf Hetzner

```bash
# 1. Code aktualisieren
cd /opt/reetrade && git pull origin main

# 2. Frontend neu bauen
cd frontend && yarn install && yarn build && cd ..

# 3. Services neustarten
sudo systemctl restart reetrade-backend reetrade-worker
```

**WICHTIG:** Nach dem Update müssen Sie:
1. SPOT API Keys eingeben (für Spot Trading)
2. FUTURES API Keys eingeben (separater Key mit Futures-Berechtigung)

## Offene Aufgaben

### P0
- [x] Separate API Keys für SPOT und FUTURES implementiert

### P1
- [ ] KI Learning Engine verifizieren
- [ ] Coin-Auswahl im Worker testen

### P2
- [ ] Telegram-Benachrichtigungen
- [ ] User Management Admin Tab
- [ ] Email-Verifizierung

## Architektur

```
/opt/reetrade/
├── backend/
│   ├── db_operations.py     # UPDATED: Separate Keys Support
│   ├── server.py            # UPDATED: Neue Futures-Keys Endpoints
│   ├── mexc_futures_client.py
│   └── worker.py
├── frontend/
│   └── src/
│       └── components/
│           └── SettingsTab.js  # UPDATED: Separate Keys UI
└── HETZNER_DEPLOYMENT.md
```

## Wichtige Endpoints

- `POST /api/keys/mexc` - SPOT Keys speichern
- `POST /api/keys/mexc/futures` - FUTURES Keys speichern (NEU)
- `GET /api/keys/mexc/status` - Status beider Keys
- `GET /api/futures/status` - Futures Konto (verwendet Futures-Keys)
