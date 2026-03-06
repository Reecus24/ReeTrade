# ReeTrade - RL Trading Bot PRD

## Original Problem Statement
Vollständig autonome Reinforcement Learning KI für SPOT Trading auf MEXC Exchange.
- Nur SPOT (kein Leverage, keine Futures)
- 10-Minuten Maximum Haltezeit
- Selbstlernendes System ohne manuelle Strategien
- Gebühren + Slippage müssen berücksichtigt werden
- Orderbook/Microstructure für kurzfristiges Trading

## Implementiert

### Phase 1: Critical Fixes ✅ (Dezember 2025)
1. **Mindest-Haltezeit**: 2min → 10s (Anti-Flip)
2. **Hard Exit**: 10 Minuten Maximum
3. **Reward System**: Zeit-Bonus entfernt → Net PnL nach Kosten
4. **Gebühren**: 0.1% MEXC Fee berechnet + Slippage
5. **Logging**: fees_paid, slippage_cost, duration, exit_reason
6. **Coin Universe**: 500 → 30 Top-Volume
7. **Active Set**: 100 → 20 Coins
8. **Epsilon**: End 0.05, Decay 0.995

### Phase 2: Orderbook & Microstructure ✅ (Dezember 2025)
1. **Orderbook API** (mexc_client.py):
   - `get_orderbook()` - Raw depth data
   - `get_orderbook_snapshot()` - Processed snapshot with aggregates

2. **MarketState erweitert** (32 Features):
   - `spread_pct` - Bid-Ask Spread %
   - `mid_price` - (best_bid + best_ask) / 2
   - `orderbook_imbalance` - bid_vol / ask_vol
   - `bid_volume_sum`, `ask_volume_sum` - Top 5 Levels
   - `return_30s`, `return_60s`, `return_180s` - Microtrend Returns
   - `volatility_1m` - 1-Minute realized volatility

3. **Trade Logging erweitert**:
   - Orderbook context at entry
   - Spread, Imbalance stored

### Phase 3: MFE/MAE Tracking ✅ (Dezember 2025)
1. **Position Tracking**:
   - `max_price_seen` - Updated every exit check
   - `min_price_seen` - Updated every exit check

2. **Trade Record**:
   - `mfe` - Max Favorable Excursion %
   - `mae` - Max Adverse Excursion %
   - `max_price_during_trade`
   - `min_price_during_trade`

### Frühere Fixes ✅
- PnL Bug: cummulativeQuoteQty für MARKET Orders
- Telegram Bot: Lokale DB als Source of Truth
- UI Konsistenz: Open Positions Count

## Aktiver Backlog

### P0 - Kritisch
- [x] Orderbook Integration (Top 5 Levels) ✅
- [x] Microtrend Returns (30s, 60s, 180s) ✅
- [x] MFE/MAE Tracking ✅

### P1 - Wichtig
- [ ] SELL FAILED 400 für SKYUSDT (Lot Size)
- [ ] Telegram 409 Conflict Fix
- [ ] Prioritized Experience Replay

### P2 - Nice-to-have
- [ ] Paper Trading Modus
- [ ] Backend Code Cleanup (Futures entfernen)
- [ ] Admin Tab
- [ ] Volatility/Regime Awareness als Feature

## Tech Stack
- Backend: Python/FastAPI
- Frontend: React
- Database: MongoDB
- AI: scikit-learn (MLPRegressor)
- Exchange: MEXC SPOT API
- Notifications: Telegram

## Key Files
- `backend/worker.py` - Trading Loop (Exit checks mit MFE/MAE)
- `backend/rl_trading_ai.py` - RL AI (32 Features inkl. Orderbook)
- `backend/mexc_client.py` - MEXC API (inkl. Orderbook)
- `backend/models.py` - Data Models (Trade, Position erweitert)

## Feature Matrix

| Feature | Status | File |
|---------|--------|------|
| 10min Hard Exit | ✅ | worker.py |
| Net PnL Reward | ✅ | rl_trading_ai.py |
| Fee Calculation | ✅ | worker.py |
| Orderbook API | ✅ | mexc_client.py |
| Spread/Imbalance | ✅ | rl_trading_ai.py |
| Microtrend Returns | ✅ | rl_trading_ai.py |
| MFE/MAE Tracking | ✅ | worker.py, models.py |
| Trade Logging | ✅ | worker.py |
