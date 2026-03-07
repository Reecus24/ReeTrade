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

### Exit-Strategie Analyse & Transparenz ✅ (März 2026)

#### 1. Exit Source Breakdown
- **Tracking aller Exit-Quellen**:
  - `time_limit`: 10-Minuten Hard Exit
  - `exploitation`: KI-basierte Entscheidung (Q[SELL] > Q[HOLD])
  - `random_exploration`: Zufälliges Verkaufen während Lernphase
  - `emergency`: Notfall-Exit bei hohem Verlust (<-5%)
  
- **Metriken pro Exit-Quelle**:
  - Anzahl Exits
  - Prozentsatz aller Exits
  - Durchschnittliche Haltezeit

#### 2. Exit Decision Logging
- Jede Exit-Entscheidung wird geloggt mit:
  - Symbol
  - Hold-Time (Sekunden)
  - Aktueller PnL %
  - Q-Values (HOLD/BUY/SELL)
  - Epsilon (Exploration Rate)
  - Entscheidung (SELL/HOLD)
  - Grund

#### 3. Dashboard-Erweiterungen (`KILogTab.js`)
- **Exit Source Breakdown Balkendiagramm**:
  - Visuelle Darstellung aller 4 Exit-Quellen
  - Prozentuale Verteilung
  - Warnung wenn time_limit > 70%
  
- **Hold Time Distribution**:
  - Buckets: <60s, 60-180s, 180-360s, 360-600s, >600s
  - Visuelle Darstellung

- **Key Metrics**:
  - Total Exits
  - Ø Hold Time
  - Exploitation Ratio
  - Ø Sell Probability

- **Recent Exits Tabelle**:
  - Symbol, Source, Hold, PnL, Q[SELL]

- **Exit Decision Log**:
  - Letzte 30 Entscheidungen mit Details

#### 4. Backend-Änderungen
- `rl_trading_ai.py`: Neue Methoden für Exit-Tracking
  - `record_time_limit_exit()`
  - `record_exit_detail()`
  - `log_exit_decision()`
  - Erweiterte `get_status()` mit vollständigen Exit-Stats

- `worker.py`: Time-Limit Exits werden jetzt getrackt mit Q-Values

- `server.py`: `/api/rl/status` gibt jetzt `exit_stats` zurück

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

### Telegram Integration (Neu aufgebaut) ✅ (März 2026)

#### Architektur
- **Pro-User Integration**: Jeder User kann seinen eigenen Telegram-Account verknüpfen
- **Code-basiertes Linking**: 
  1. User tippt `/link` im Telegram Bot
  2. Bot generiert 6-stelligen Code (gültig 10 Min)
  3. User gibt Code in Web-App ein
  4. Verknüpfung wird hergestellt

#### Features
- **Bot-Befehle**: `/status`, `/balance`, `/profit`, `/trades`, `/ki`, `/help`
- **Benachrichtigungen**: Trade Open/Close (pro User)
- **Daten in DB**: `telegram_chat_id` in `users` Collection

#### Dateien
- `backend/telegram_bot.py` - Neuer, sauberer Bot
- `backend/server.py` - Endpoints: `/api/telegram/status`, `/api/telegram/link`, `/api/telegram/unlink`, `/api/telegram/test`
- `frontend/src/components/SettingsTab.js` - Telegram UI

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

---

## Changelog (Dezember 2025)

### Dust-Handling Feature ✅ (06.03.2026)

**Problem**: Restbestände (Dust) im Portfolio, die zu klein sind um verkauft zu werden (unter minQty/minNotional), erzeugen "SELL FAILED 400" Fehler und verfälschen die Trading-Statistiken.

**Lösung**: Vollständiges Dust-Detection und -Handling System implementiert.

#### Änderungen:

1. **Backend: `order_sizer.py`**
   - Neue Methode `is_dust_position(symbol, qty, current_price)` → prüft ob Position zu klein
   - Neue Methode `get_dust_status(symbol, qty, current_price)` → gibt UI-freundliche Details
   - Prüfungen: qty < minQty, qty rounds to 0 (stepSize), notional < minNotional

2. **Backend: `server.py`**
   - `enrich_positions_with_prices()` fügt Dust-Status hinzu (`is_dust`, `can_sell`, `dust_reason`)
   - `/api/positions/sell` blockiert Dust-Positionen mit klarer Fehlermeldung
   - Exchange-Filter werden beim Enrichment aktualisiert

3. **Backend: `worker.py`**
   - `_close_spot_position()` prüft auf Dust VOR dem SELL-Versuch
   - Dust wird sauber geloggt mit `[DUST]` Prefix (kein ERROR-Spam)
   - Position bleibt als "Dust" erhalten, keine weiteren SELL-Versuche

4. **Frontend: `PositionsPanel.js`**
   - Trennung: `activePositions` vs `dustPositions`
   - Header zeigt: "POSITIONS (X) +Y Dust"
   - Separater "DUST / RESTBESTÄNDE" Bereich am Ende
   - Dust-Positionen haben KEIN SELL-Button
   - Info-Text: "Diese Bestände sind zu klein zum Verkaufen"

#### Verhalten:
- Dust-Positionen werden **nicht** als aktive Positionen gezählt
- Dust-Positionen erzeugen **keine** SELL-Fehler mehr
- Dust-Positionen beeinflussen **nicht** die Trading-Statistiken
- KI ignoriert Dust bei RL-Signalen

---

### Buy-Pipeline Transparenz Feature ✅ (07.03.2026)

**Problem**: Benutzer sieht im Log "TRXUSDT: RL-KI sagt JA", aber der Scan endet mit "0 Signale". Es war unklar, welcher Filter danach den Trade blockierte.

**Lösung**: Vollständige Transparenz in der Buy-Pipeline implementiert.

#### Änderungen in `worker.py`:

1. **Detailliertes Pipeline-Tracking pro Coin**:
   - Für jeden Coin mit RL BUY wird ein `coin_pipeline` Dictionary erstellt
   - Trackt jeden Schritt: `rl_decision`, `paused_check`, `klines_15m`, `min_move`, `order_sizing`, `final_action`
   - Speichert auch den `block_reason` wenn der Coin blockiert wird

2. **Neue Counter**:
   - `blocked_by_order_sizing`: Zählt Order-Sizing-Fehler
   - `actual_buy_orders`: Zählt tatsächlich platzierte Orders

3. **Detailliertes Pro-Coin-Log** (nach dem Scan):
   ```
   ═══════════════════════════════════════════════════════════════
   [BUY PIPELINE] Detaillierte Analyse für X Coins mit RL BUY:
   ═══════════════════════════════════════════════════════════════
   
   [TRXUSDT] ❌ BLOCKED
      ├─ RL decision:    BUY ✅
      ├─ paused check:   PASSED ✅
      ├─ 15m klines:     PASSED ✅ (500)
      ├─ min_move:       FAILED ❌ (0.280% < 0.369%)
      ├─ order_sizing:   PENDING
      └─ final action:   BLOCKED (blocked by: MIN_MOVE)
   ```

4. **Kompakte Zusammenfassung** (Box-Format):
   ```
   ╔════════════════════════════════════════════════════════════════╗
   ║                    📊 PIPELINE SUMMARY                         ║
   ╠════════════════════════════════════════════════════════════════╣
   ║  RL BUY candidates:        X                                   ║
   ╠════════════════════════════════════════════════════════════════╣
   ║  ❌ blocked by paused:      Y                                   ║
   ║  ❌ blocked by RL_HOLD:     Z                                   ║
   ║  ❌ blocked by 15m klines:  A                                   ║
   ║  ❌ blocked by MIN_MOVE:    B                                   ║
   ║  ❌ blocked by order_sizing:C                                   ║
   ╠════════════════════════════════════════════════════════════════╣
   ║  ✅ ready for order:        D                                   ║
   ║  🛒 actual buy orders:      E                                   ║
   ╚════════════════════════════════════════════════════════════════╝
   ```

#### Ziel erreicht:
- Benutzer sieht jetzt genau, warum jeder Coin mit RL BUY nicht gekauft wurde
- Alle Filter werden einzeln aufgelistet: paused, klines, MIN_MOVE, order_sizing
- Klare Unterscheidung zwischen "ready for order" und "actual buy orders"

### MIN_MOVE Filter Toleranz ✅ (07.03.2026)

**Problem**: RL BUY-Signale wurden durch den MIN_MOVE Filter blockiert, auch bei minimalen Differenzen wie 0.367% vs 0.369%.

**Lösung**: Toleranz-System und schnellere dynamische Anpassung implementiert.

#### Änderungen:

1. **Neue Konstanten in `__init__`**:
   ```python
   self.MIN_MOVE_TOLERANCE_PCT = 0.02  # 0.02% Toleranz für Grenzfälle
   self.consecutive_rl_buy_blocked = {}  # Zählt RL BUYs die am MIN_MOVE scheitern
   self.RL_BUY_BLOCKED_THRESHOLD = 5  # Nach 5 RL BUYs -> schneller lockern
   ```

2. **Neue Filter-Logik mit Toleranz**:
   ```python
   effective_move = expected_move + tolerance
   passes_filter = effective_move >= min_threshold
   ```
   - Trades scheitern nicht mehr an minimalen Differenzen
   - Grenzfälle wie 0.367% vs 0.369% werden jetzt durchgelassen

3. **Erweitertes Logging**:
   - `expected_move`: Berechnete erwartete Bewegung
   - `tolerance`: +0.02%
   - `effective_move`: expected_move + tolerance
   - `min_threshold`: Aktueller Schwellenwert (basierend auf Multiplier)
   - `diff`: Differenz zum Threshold
   - `RL BUY blocked`: Counter für RL BUYs die am MIN_MOVE scheitern

4. **Schnellere dynamische Anpassung**:
   - Nach nur 5 RL BUYs die am MIN_MOVE scheitern (statt 10 Scans) wird der Multiplier reduziert
   - Zählt nur RL BUY-Signale, nicht alle Scans
   - `update_dynamic_move_filter()` erhält neuen Parameter `rl_buy_blocked_by_min_move`

#### Effekt:
- Trades mit expected_move >= 0.349% werden jetzt durchgelassen (statt erst ab 0.369%)
- KI wird nicht mehr künstlich ausgebremst bei knappen Grenzfällen
- Filter lockert schneller wenn RL BUYs systematisch blockiert werden

---

## Backlog

### P0 (Kritisch)
- [x] Dust-Handling implementiert
- [x] Buy-Pipeline Transparenz implementiert

### P1 (Hoch)
- [ ] Telegram-Verknüpfung debuggen (Code-Validierung)
- [ ] Live-Preis und PnL Anzeige für offene Positionen

### P2 (Mittel)
- [ ] "Institutional-Grade" Erweiterungen (Regime-Bewusstsein)
- [ ] stepSize Discovery Caching

### Future
- [ ] Admin-Tab für Benutzerverwaltung
- [ ] E-Mail-Verifizierung & Passwort-Reset
- [ ] deploy.sh Automatisierungsskript
- [ ] server.py Aufteilung in FastAPI-Router
