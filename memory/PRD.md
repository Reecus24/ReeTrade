# ReeTrade - Neural Trading Terminal

## Original Problem Statement
Autonomous Reinforcement Learning (RL) AI for SPOT trading on MEXC exchange with:
- RL AI that learns from trade outcomes
- Detailed logging of AI learning progress
- Cyberpunk UI aesthetic
- Clean backend without old AI logic

## Architecture
```
/opt/reetrade/
├── backend/
│   ├── server.py           # FastAPI main server
│   ├── worker.py           # Trading worker (RL only)
│   ├── rl_trading_ai.py    # Reinforcement Learning engine
│   ├── telegram_bot.py     # Telegram notifications
│   └── models.py           # Pydantic models
├── frontend/
│   └── src/
│       ├── pages/DashboardPage.js
│       ├── components/
│       │   ├── BotStatusPanel.js
│       │   └── PositionsPanel.js
│       └── styles/index.css (Cyberpunk theme)
```

## Completed Work

### 2024-12 (Current Session)
- [x] Fixed Position Count Diskrepanz - all panels now use consistent array length

### Previous Session
- [x] Cyberpunk UI overhaul
- [x] Backend refactoring (removed old AI logic from worker.py)
- [x] UI labels switched to English
- [x] Font size improvements
- [x] Info Tab content updated for RL AI

## Known Issues

### P0 - Blockers
1. **Frontend not deployed on user's Hetzner server** - User needs to run npm build
2. **Telegram 409 Conflict Error** - Likely duplicate worker service running

### P1 - High Priority
3. **`_buying_positions` AttributeError** - Critical bug, needs testing after backend restart

## Backlog

### P1 - Upcoming
- [ ] Paper Trading Mode for safe RL training
- [ ] Verify smart_exit_engine.py data
- [ ] Complete backend code cleanup

### P2 - Future
- [ ] History reset script execution
- [ ] Futures trading (on hold)
- [ ] Admin tab for user management
- [ ] Email verification & password reset

## 3rd Party Integrations
- MEXC Exchange API (SPOT trading)
- Telegram Bot API (notifications)
- scikit-learn (RL Neural Network)

## User's Language
German (conversations) / English (UI labels)
