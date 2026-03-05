# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Vollautomatischer SPOT Trading**
- **Learning by Doing AI**
- **Smart Exit Engine**
- **Telegram Benachrichtigungen**

## Implementierte Features (05.03.2026)

### Telegram Integration (Komplett)
**Bot:** @reetrade_trading_bot

**Automatische Benachrichtigungen:**
- 🟢 Trade geöffnet
- 🔴 Trade geschlossen  
- 🛑 Stop-Loss ausgelöst
- 🎯 Take-Profit erreicht
- 🧠 KI Smart Exit Entscheidung
- 📊 **Tägliche Zusammenfassung um 21:00 Uhr** (NEU)

**Befehle:**
- `/status` - Offene Positionen
- `/profit` - Heutiger Profit
- `/profit_week` - Wochenprofit
- `/profit_month` - Monatsprofit
- `/balance` - Wallet-Stand
- `/trades` - Letzte 5 Trades
- `/ki` - KI Status & Lernfortschritt
- `/summary` - Tages-Zusammenfassung jetzt (NEU)
- `/stop` - Bot pausieren
- `/resume` - Bot fortsetzen
- `/help` - Hilfe

### Smart Exit Engine
- Intelligente Verkaufsentscheidungen ohne starre TP/SL
- Analysiert RSI, Momentum, EMA20, Candlestick-Patterns
- Kann früher verkaufen bei Trendumkehr
- Kann länger halten wenn Trade gut läuft
- Lernfähig

### FUTURES deaktiviert
- Tab und Keys ausgeblendet (kommt später)

## Deployment auf Hetzner

```bash
cd /opt/reetrade && git pull
cd frontend && npm run build && cd ..
sudo systemctl restart reetrade-backend reetrade-worker
```

**.env Datei:**
```
TELEGRAM_BOT_TOKEN=8791012984:AAHWj1EF0YqAZwpH2Cle-H-UwdVq7OaSpyU
TELEGRAM_CHAT_ID=5642445106
```

## API Endpoints

**Telegram:**
- `GET /api/telegram/status` - Status
- `POST /api/telegram/test` - Test senden
- `POST /api/telegram/summary` - Zusammenfassung jetzt

## Offene Aufgaben

### P1
- [x] Tägliche Zusammenfassung um 21:00 Uhr ✅
- [ ] Smart Exit mit echten Trades verifizieren

### P2 (Zukunft)
- [ ] FUTURES Trading wieder aktivieren
- [ ] Email-Benachrichtigungen
- [ ] User Management Admin Tab
