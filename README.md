# MEXC SPOT Trading Bot - AlgoTrade Terminal

Ein automatisierter SPOT-Trading-Bot für die MEXC Exchange mit FastAPI Backend, React Frontend und MongoDB.

## 🎯 Features

### ✅ Trading Features
- **Paper Trading**: Simulierter Handel mit $10,000 Startkapital
- **Live Trading**: Echtes Trading über MEXC API (vorbereitet, Keys optional)
- **EMA Crossover Strategie**: EMA 50/200 mit RSI 14 Filter
- **Risk Management**: 
  - 1% Risiko pro Trade
  - Max 3 gleichzeitige Positionen
  - 3% Max Daily Loss (Bot stoppt automatisch)
  - Stop Loss & Take Profit (2:1 Risk/Reward)
- **Top 20 USDT Pairs**: Automatische tägliche Aktualisierung
- **15-Minuten Timeframe**: Scanning alle 15 Minuten

### 🎨 Dashboard Features
- **Passwortschutz**: Admin-Login erforderlich
- **Overview Tab**: Bot Status, Equity, PnL, offene Positionen
- **Strategie Tab**: Parameter, Risk Management, Top Pairs
- **Backtest Tab**: Historisches Backtesting
- **Logs Tab**: Live Terminal mit allen Events
- **Dark Theme**: Professionelles Trader-Design (Manrope + JetBrains Mono)

### 🔒 Sicherheit
- Session-basierte Authentifizierung
- Live Mode mit doppelter Bestätigung (Request + Passwort)
- Keine Withdrawal-Rechte erforderlich
- API Keys optional (nur für Live Mode)

## 🚀 Quick Start

### 1. Login
```
URL: https://reetrade-spot-ai.preview.emergentagent.com
Passwort: Rainer_70!PK
```

### 2. Bot starten (Paper Mode)
1. Im Dashboard auf "Start" klicken
2. Bot scannt automatisch Top 20 USDT Pairs
3. Öffnet Positionen bei EMA/RSI Signalen
4. Monitort Stop Loss & Take Profit

### 3. Live Mode aktivieren (Optional)
⚠️ **Voraussetzung**: MEXC API Keys in `/app/backend/.env` eintragen:
```bash
MEXC_API_KEY="your_key"
MEXC_API_SECRET="your_secret"
```

Dann im Dashboard:
1. "Go Live" Button klicken
2. Weiter zur Bestätigung
3. Admin-Passwort eingeben
4. Live Mode aktiviert! 🔴

## 📊 Strategie Details

### Entry Signal
- EMA 50 > EMA 200 (Bullish Crossover)
- RSI > 50 (Momentum)
- RSI < 75 (Nicht überkauft)

### Exit Signal
- Stop Loss erreicht
- Take Profit erreicht (2x Risiko)
- EMA crossover bearish

### Position Sizing
```
Risk Amount = Equity × 1%
Position Size = Risk Amount / (Entry - Stop Loss)
```

### Fees & Slippage
- Fees: 10 bps (0.1%)
- Slippage: 5 bps (0.05%)

## 🛠️ Technische Details

### Backend Stack
- **FastAPI**: REST API
- **MongoDB**: Datenbank (tradingbot)
- **Motor**: Async MongoDB Driver
- **HTTPX**: HTTP Client mit Retry Logic
- **Tenacity**: Exponential Backoff

### Frontend Stack
- **React 19**: UI Framework
- **Tailwind CSS**: Styling
- **Shadcn/UI**: Component Library
- **Recharts**: Charts
- **Sonner**: Toast Notifications
- **Axios**: HTTP Client

### Collections
```
settings: Bot-Konfiguration (singleton)
logs: Event-Log
paper_accounts: Paper Trading Account
trades: Trade History
daily_metrics: Performance Metriken
```

## 🔧 Development

### Backend Server
```bash
cd /app/backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd /app/frontend
yarn start
```

### Logs anzeigen
```bash
# Backend Logs
tail -f /var/log/supervisor/backend.err.log

# Frontend Logs
tail -f /var/log/supervisor/frontend.out.log
```

## 📈 API Endpoints

### Authentication
- `POST /api/auth/login` - Login mit Passwort

### Bot Control
- `POST /api/bot/start` - Bot starten
- `POST /api/bot/stop` - Bot stoppen
- `POST /api/bot/live/request` - Live Mode anfordern
- `POST /api/bot/live/confirm` - Live Mode bestätigen
- `POST /api/bot/live/disable` - Zurück zu Paper Mode

### Status & Data
- `GET /api/status` - Bot Status & Account Info
- `GET /api/logs` - Log Einträge
- `GET /api/market/top_pairs` - Top Trading Pairs
- `GET /api/market/candles` - Candlestick Daten
- `POST /api/backtest/run` - Backtest ausführen

## ⚙️ Konfiguration

### Environment Variables

**Backend** (`/app/backend/.env`):
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="tradingbot"
ADMIN_PASSWORD="Rainer_70!PK"
MEXC_API_KEY=""  # Optional für Live Mode
MEXC_API_SECRET=""  # Optional für Live Mode
```

**Frontend** (`/app/frontend/.env`):
```env
REACT_APP_BACKEND_URL=https://reetrade-spot-ai.preview.emergentagent.com
```

### Strategy Parameters (anpassbar in MongoDB)
```javascript
{
  ema_fast: 50,
  ema_slow: 200,
  rsi_period: 14,
  rsi_min: 50,
  rsi_overbought: 75,
  risk_per_trade: 0.01,
  max_positions: 3,
  max_daily_loss: 0.03,
  take_profit_rr: 2.0
}
```

## 🧪 Testing

Testing Agent Report: `/app/test_reports/iteration_1.json`
- **Backend**: 100% (15/15 API Tests)
- **Frontend**: 98% (minor warnings only)
- **Overall**: 99% Success Rate

## ⚠️ Wichtige Hinweise

1. **Keine Gewinn-Garantie**: Trading ist riskant, Verluste möglich
2. **Paper Mode First**: Immer erst im Paper Mode testen
3. **Live Mode**: Nur mit echten MEXC API Keys (keine Withdrawal-Rechte nötig)
4. **Daily Loss Limit**: Bot stoppt automatisch bei 3% Tagesverlust
5. **Heartbeat**: Worker sendet alle 60s Heartbeat
6. **Trading Cycle**: Alle 15 Minuten Scanning

## 📝 Worker Loop

```
Startup → Initialize DB → Start Background Tasks
                            ↓
                    ┌───────┴───────┐
                    ↓               ↓
              Heartbeat         Trading Loop
              (60 sec)          (15 min)
                    ↓               ↓
              Update DB      Scan Top Pairs
                            Check Positions
                            Execute Trades
                            Update Metrics
```

## 🎨 Design System

- **Fonts**: Manrope (UI), JetBrains Mono (Data)
- **Colors**: Deep Black (#050505), Zinc (#27272a)
- **Theme**: Dark Mode Only
- **Style**: Minimal, Technical, Professional

## 📦 Dependencies

### Backend
```
fastapi==0.110.1
motor==3.3.1
httpx==0.28.1
tenacity==8.2.3
pydantic>=2.6.4
python-dotenv>=1.0.1
```

### Frontend
```
react@19.0.0
tailwindcss@3.4.17
recharts@3.6.0
sonner@2.0.3
lucide-react@0.507.0
```

## 🔥 Production Ready Features

- ✅ Single-Process Deployment (Emergent-optimized)
- ✅ Background Worker als FastAPI Startup Task
- ✅ Retry Logic mit Exponential Backoff (3 Retries, 1/2/4s)
- ✅ Rate Limiting Ready (5 orders/sec MEXC limit)
- ✅ Error Handling & Logging
- ✅ Session Management
- ✅ Real-time Updates (5s polling)
- ✅ Responsive Design
- ✅ CORS configured
- ✅ Hot Reload enabled

## 🎯 Next Steps

### Empfohlene Verbesserungen:
1. **Charts**: Equity-Kurve, PnL-Chart im Overview
2. **Notifications**: Email/Telegram Alerts bei Trades
3. **Advanced Strategy**: Weitere Indikatoren (Bollinger, MACD)
4. **Multi-Timeframe**: 5m, 1h, 4h Analysen
5. **News Integration**: Optional Sentiment-Filter
6. **Performance Analytics**: Sharpe Ratio, Max Drawdown Tracking

### Live-Deployment Checklist:
- [ ] MEXC API Keys konfigurieren
- [ ] IP Whitelist bei MEXC eintragen
- [ ] Live Mode testen mit kleinem Betrag
- [ ] Daily Loss Limit verifizieren
- [ ] Monitoring Setup (Logs, Alerts)

## 📞 Support

Bei Fragen oder Problemen:
1. Check Logs: `/api/logs` Endpoint
2. Backend Logs: `/var/log/supervisor/backend.err.log`
3. Frontend Console: Browser DevTools

---

**Built with Emergent** 🚀 | **Dark Terminal Aesthetic** 🖥️ | **Production Ready** ✅
