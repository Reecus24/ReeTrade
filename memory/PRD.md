# ReeTrade - RL Trading Bot PRD

## Original Problem Statement
Vollständig autonome Reinforcement Learning KI für SPOT Trading auf MEXC Exchange.
- Nur SPOT (kein Leverage, keine Futures)
- 10-Minuten Maximum Haltezeit
- Selbstlernendes System ohne manuelle Strategien
- Gebühren + Slippage müssen berücksichtigt werden
- Orderbook/Microstructure für kurzfristiges Trading

## Implementiert

### Phase 1: Critical Fixes ✅
1. **Mindest-Haltezeit**: 2min → 10s (Anti-Flip)
2. **Hard Exit**: 10 Minuten Maximum
3. **Reward System**: Zeit-Bonus entfernt → Net PnL nach Kosten
4. **Gebühren**: 0.1% MEXC Fee berechnet + Slippage
5. **Logging**: fees_paid, slippage_cost, duration, exit_reason
6. **Coin Universe**: 500 → 30 Top-Volume
7. **Active Set**: 100 → 20 Coins
8. **Epsilon**: End 0.05, Decay 0.995

### Phase 2: Orderbook & Microstructure ✅
1. **Orderbook API** (mexc_client.py):
   - `get_orderbook()` - Raw depth data
   - `get_orderbook_snapshot()` - Processed snapshot with plausibility checks

2. **MarketState erweitert** (32 Features)

3. **Orderbook Plausibility Fix** ✅:
   - Validates ask > bid
   - Validates spread_abs > 0
   - Returns None for invalid orderbooks
   - Correct spread_pct calculation

### Phase 3: MFE/MAE Tracking ✅
- Position tracking: max_price_seen, min_price_seen
- Trade record: mfe, mae, max_price_during_trade

### P0 Fixes (Dezember 2025) ✅

#### SELL FAILED 400 Fix ✅
- **Root Cause**: MEXC has no explicit LOT_SIZE filters, uses basePrecision
- **Fix**: OrderSizer now derives stepSize from basePrecision
- **Formula**: `stepSize = 10^(-basePrecision)`
- **Validation**: `prepare_sell_quantity()` validates before SELL orders

#### Orderbook Plausibility Fix ✅
- **Issue**: spread=0.0000% was invalid
- **Fix**: Proper validation (ask > bid, spread > 0)
- **Result**: BTC spread now shows 0.000014%, DOGE shows 0.01%

## Aktiver Backlog

### P1 - Wichtig
- [ ] Telegram 409 Conflict (single polling instance)
- [ ] Prioritized Experience Replay

### P2 - Nice-to-have
- [ ] Paper Trading Modus
- [ ] Backend Code Cleanup
- [ ] Volatility/Regime Awareness

## Key Files
- `backend/worker.py` - Trading Loop
- `backend/rl_trading_ai.py` - RL AI (32 Features)
- `backend/mexc_client.py` - MEXC API + Orderbook
- `backend/order_sizer.py` - Order validation ✅ FIXED
- `backend/models.py` - Data Models

## OrderSizer Logic

```python
# Step size from MEXC basePrecision:
stepSize = 10^(-basePrecision)

# Round DOWN to stepSize:
rounded_qty = floor(qty / stepSize) * stepSize

# Validation:
- rounded_qty >= minQty (= stepSize)
- rounded_qty * price >= minNotional (= 1 USDT)
```

## Test Results
- SKYUSDT (basePrecision=2): 656.123456 → 656.12 ✅
- BTCUSDT (basePrecision=8): 0.001234567 → 0.00123456 ✅
- ETHUSDT (basePrecision=5): 0.12345678 → 0.12345 ✅
