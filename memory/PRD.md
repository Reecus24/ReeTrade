# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Vollautomatischer SPOT Trading** - Die KI übernimmt komplett
- **Learning by Doing AI** - KI übernimmt nach 10 Trades
- **Smart Exit Engine** - KI entscheidet selbstständig wann verkaufen
- **Telegram Benachrichtigungen** - Bidirektional mit Befehlen

## Implementierte Features (05.03.2026)

### Telegram Integration (NEU)
**Bot:** @reetrade_trading_bot

**Automatische Benachrichtigungen:**
- 🟢 Trade geöffnet
- 🔴 Trade geschlossen  
- 🛑 Stop-Loss ausgelöst
- 🎯 Take-Profit erreicht
- 🧠 KI Smart Exit Entscheidung

**Befehle:**
- `/status` - Offene Positionen
- `/profit` - Heutiger Profit
- `/profit_week` - Wochenprofit
- `/profit_month` - Monatsprofit
- `/balance` - Wallet-Stand
- `/trades` - Letzte 5 Trades
- `/ki` - KI Status & Lernfortschritt
- `/stop` - Bot pausieren
- `/resume` - Bot fortsetzen
- `/help` - Hilfe

### Smart Exit Engine
- Intelligente Verkaufsentscheidungen ohne starre TP/SL
- Analysiert RSI, Momentum, EMA20, Candlestick-Patterns
- Kann früher verkaufen bei Trendumkehr
- Kann länger halten wenn Trade gut läuft
- Lernfähig: Passt Parameter basierend auf Erfahrung an

### FUTURES deaktiviert
- Tab und Keys ausgeblendet (kommt später)
- Fokus auf SPOT Trading

## Architektur

```
/app/backend/
├── telegram_bot.py          # NEU: Telegram Integration
├── smart_exit_engine.py     # Intelligente Exit-Logik
├── ki_learning_engine.py    # Lernende KI
├── worker.py                # Trading Worker (mit Telegram Integration)
└── server.py                # FastAPI Backend

/app/frontend/src/
├── components/
│   └── SettingsTab.js       # Mit Telegram Status & Test Button
```

## Deployment auf Hetzner

```bash
cd /opt/reetrade && git pull
cd frontend && npm run build && cd ..
sudo systemctl restart reetrade-backend reetrade-worker
```

**WICHTIG:** Nach dem Deployment die .env Datei aktualisieren:
```
TELEGRAM_BOT_TOKEN=8791012984:AAHWj1EF0YqAZwpH2Cle-H-UwdVq7OaSpyU
TELEGRAM_CHAT_ID=5642445106
```

## API Endpoints

**Telegram:**
- `GET /api/telegram/status` - Telegram-Status
- `POST /api/telegram/test` - Test-Nachricht senden

**Trading:**
- `GET /api/status` - Bot-Status
- `GET /api/trades` - Trade-Historie
- `GET /api/balance` - Balance

## Offene Aufgaben

### P1
- [ ] Tägliche Zusammenfassung automatisch senden (z.B. 21:00 Uhr)
- [ ] Smart Exit mit echten Trades testen

### P2 (Zukunft)
- [ ] FUTURES Trading wieder aktivieren
- [ ] Email-Benachrichtigungen
- [ ] User Management Admin Tab
