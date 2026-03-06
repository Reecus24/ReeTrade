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
1. Min Hold 10s, Hard Exit 10min
2. Net PnL Reward (nach Fees/Slippage)
3. Coin Universe 30, Active 20
4. Epsilon 0.05 end, 0.995 decay

### Phase 2: Orderbook & Microstructure ✅
- Orderbook API mit Plausibility Checks
- 32 Features inkl. spread, imbalance, microtrends
- MFE/MAE Tracking

### P0 Fixes ✅
1. **SELL FAILED 400**: OrderSizer mit basePrecision
2. **Orderbook Plausibility**: ask > bid, spread > 0 Validierung

### P1 Fixes ✅ (Dezember 2025)

#### 1. Telegram 409 Conflict Fix ✅
- **Neue Datei**: `distributed_lock.py`
- **Mechanismus**: MongoDB TTL-basiertes Leader Election
- **Features**:
  - Nur Leader-Instanz führt Polling aus
  - Heartbeat alle 10s verlängert Lock
  - Automatische Lock-Expiration nach 30s
  - Bei 409 Conflict: Lock wird released
- **Integration**: `server.py` telegram_polling_loop()

#### 2. Prioritized Experience Replay (PER) ✅
- **Klasse**: `PrioritizedReplayMemory` in `rl_trading_ai.py`
- **Algorithm**:
  - priority_i = |TD_error| + epsilon
  - P(i) = priority^alpha / sum(priority^alpha)
  - Importance sampling: w_i = (N * P(i))^(-beta)
- **Parameters**:
  - alpha = 0.6 (prioritization strength)
  - beta_start = 0.4 → 1.0 (importance sampling annealing)
  - epsilon = 0.01 (avoid zero priority)
- **Benefits**:
  - Erfahrungen mit hohem TD-Error werden öfter gesamplet
  - Schnelleres Lernen mit weniger Trades
  - Importance sampling korrigiert Bias

## Aktiver Backlog

### P1.5 - Safety (Future)
- [ ] observed_stepSize Discovery/Cache per Symbol
- [ ] Handle non-decimal step sizes

### P2 - Nice-to-have
- [ ] Paper Trading Modus
- [ ] Backend Code Cleanup
- [ ] Volatility/Regime Awareness als Feature
- [ ] Webhook statt Polling (alternative to Lock)

## Key Files
- `backend/worker.py` - Trading Loop
- `backend/rl_trading_ai.py` - RL AI + PER
- `backend/mexc_client.py` - MEXC API + Orderbook
- `backend/order_sizer.py` - Order validation
- `backend/distributed_lock.py` - Leader Election ✅ NEW
- `backend/server.py` - API + Telegram Polling

## PER Algorithm Details

```python
# Priority calculation
priority = abs(td_error) + epsilon

# Sampling probability
P(i) = priority_i^alpha / sum_j(priority_j^alpha)

# Importance sampling weight (corrects bias)
w_i = (N * P(i))^(-beta)

# Beta annealing (starts at 0.4, increases to 1.0)
beta = beta_start + (1 - beta_start) * frame / beta_frames
```

## Distributed Lock Details

```
Instance A (Leader):
  - Acquires lock
  - Runs telegram polling
  - Heartbeat every 10s
  
Instance B (Follower):
  - try_acquire() returns False
  - Waits 10s, retries
  
If Instance A dies:
  - Lock expires after 30s (TTL)
  - Instance B acquires lock
  - Becomes new leader
```
