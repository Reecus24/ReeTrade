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

#### 3. Umfassendes RL Trading Stats System ✅ (Dezember 2025)
- **Endpoint**: `GET /api/rl/trading-stats?hours={1,6,24}`
- **Backend** (server.py:2377-2779):
  - 8 Haupt-Datengruppen: hold_stats, pnl_stats, fee_stats, sell_sources, trade_counts, performance, rl_metrics, health
  - Alle Werte aggregiert für gewählten Zeitraum (1h/6h/24h)
  - Fee Ratio Berechnung: `(total_fees / total_notional) * 100`
  - Health Status mit klarer Ampel-Logik (healthy/warning/critical)
  
- **Health Status Logik**:
  - **Critical**: Net PnL < -0.5%, Profit Factor < 0.5, Random Exploration > 70%, Fee Ratio > 1%, Avg Hold < 60s
  - **Warning**: Net PnL negativ, Profit Factor < 1.0, Random Exploration > 50%, PnL Gap > 0.3%, Fee Ratio > 0.5%, Avg Hold < 90s
  - **Healthy**: Win Rate >= 50%, Profit Factor >= 1.0, Exploitation > 50%
  
- **Frontend** (DashboardPage.js:31-440):
  - RLStatusPanel komplett überarbeitet
  - Zeitraum-Buttons (1h/6h/24h)
  - Auto-Refresh alle 10 Sekunden
  - Health Status Ampel mit Gründen
  - Sell Sources als visuelle Balken
  - Vergleich Theoretical vs Net PnL
  - Cyberpunk-Design beibehalten

- **Test Coverage**: 23/23 Tests bestanden (100%)

### P0 Fix: Scan-Logik für RL Trading Universe ✅ (März 2026)

#### Problem
Der Scanner scannte keine Coins mehr, weil er nur Top-20 Coins nach globalem Volume berücksichtigte. Da das Trading-Universe auf Mid-Cap Coins umgestellt wurde, funktionierte diese Logik nicht mehr.

#### Lösung
**Neue Scan-Logik implementiert:**

1. **DIREKT aus definiertem Universe scannen** (nicht mehr Top-20 global):
   ```
   SOLUSDT, AVAXUSDT, DOTUSDT, LINKUSDT, MATICUSDT, ATOMUSDT, TRXUSDT, NEARUSDT, 
   FILUSDT, APTUSDT, ARBUSDT, OPUSDT, INJUSDT, SUIUSDT, SEIUSDT, AAVEUSDT, UNIUSDT, 
   RUNEUSDT, STXUSDT, TIAUSDT, IMXUSDT, FTMUSDT, GALAUSDT, SANDUSDT, MANAUSDT, 
   AXSUSDT, CHZUSDT, ZILUSDT, IOTAUSDT, XLMUSDT, ALGOUSDT, FLOWUSDT, MINAUSDT, 
   RNDRUSDT, DYDXUSDT, GMXUSDT, LDOUSDT, CRVUSDT, SNXUSDT, COMPUSDT, BALUSDT, ANKRUSDT
   ```

2. **Optimierte Liquidity Filter für MEXC Mid-Caps**:
   - 24h Volume > 3M USDT (statt 20M)
   - Spread < 0.5% (statt 0.2%)

3. **Active Scan Pool mit Rotation**:
   - Universe: ~42 Coins (alle liquiden Mid-Caps)
   - Active Scan Pool: 15-20 Coins gleichzeitig
   - Rotation alle 45 Minuten (statt 4 Stunden)

4. **Robustere Fehlerbehandlung**:
   - Sofortiger Refresh wenn `top_pairs` leer ist
   - Fallback zu Batch-Rotation wenn nach Refresh leer
   - Detailliertes Logging für Debugging

#### Geänderte Dateien
- `backend/mexc_client.py`: `get_momentum_universe()` komplett überarbeitet
- `backend/worker.py`: `process_user()`, `refresh_top_pairs()`, `rotate_to_next_batch()` angepasst

#### Test-Ergebnis
Mit den neuen Filtern: **13-20 tradable Coins** (vorher: 0-5)

### P0 Fix: Große Bereinigung - Telegram, Futures & Cooldown entfernt ✅ (März 2026)

#### Entfernte Features
1. **Telegram Integration komplett entfernt:**
   - `telegram_bot.py` gelöscht
   - `distributed_lock.py` gelöscht  
   - Alle Telegram-Endpoints entfernt
   - Frontend: Telegram-Linking UI entfernt

2. **Futures/Leverage komplett entfernt:**
   - `mexc_futures_client.py` gelöscht
   - `FuturesTab.js` gelöscht
   - Alle Futures-Endpoints entfernt
   - Nur noch SPOT Trading!

3. **Buy Cooldown entfernt:**
   - Keine Wartezeit mehr zwischen Trades
   - Bot kann sofort wieder traden
   - Cooldown-Endpoint entfernt
   - Cooldown-UI im Dashboard entfernt

#### Bereinigte Dateien
- `backend/server.py`: ~500 Zeilen entfernt
- `backend/worker.py`: ~200 Zeilen entfernt  
- `backend/models.py`: Futures- und Paper-Mode Felder entfernt
- `frontend/src/components/SettingsTab.js`: Telegram & Cooldown UI entfernt
- `frontend/src/pages/DashboardPage.js`: Cooldown-Anzeige entfernt

## Aktiver Backlog

### P1.5 - Safety (Future)
- [ ] observed_stepSize Discovery/Cache per Symbol
- [ ] Handle non-decimal step sizes

### P2 - Nice-to-have
- [ ] Backend Code Cleanup
- [ ] Volatility/Regime Awareness als Feature

## Key Files
- `backend/worker.py` - Trading Loop + Universe Rotation (SPOT only)
- `backend/rl_trading_ai.py` - RL AI + PER
- `backend/mexc_client.py` - MEXC SPOT API + Orderbook + Universe Scanner
- `backend/order_sizer.py` - Order validation
- `backend/server.py` - API Endpoints (ohne Telegram/Futures/Cooldown)

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
