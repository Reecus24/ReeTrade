# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
Ein Full-Stack Trading-Bot für die MEXC Kryptobörse mit:
- Multi-User-System
- **KI Learning by Doing** - KI übernimmt nach 10 Trades
- **SPOT & FUTURES Trading** mit Hebel (Isolated Margin)
- **Portfolio-basiertes Position Sizing**
- **Coin-Auswahl** - User wählt Coins
- Info Tab mit Konzept-Erklärung

## Implementierte Features (Stand: 05.03.2026)

### UI Updates ✅
- [x] **Budget/Reserve ENTFERNT** aus Portfolio-Übersicht
- [x] **SPOT Wallet** sauber dargestellt
- [x] **FUTURES Wallet** separat angezeigt (wenn aktiviert)
- [x] **Daily Cap ENTFERNT** (vereinfacht)
- [x] **Gesamt Portfolio** Summe (SPOT + FUTURES)
- [x] **Coin-Auswahl** zeigt alle verfügbaren Coins (~500 SPOT, ~300 FUTURES)
- [x] **Info Tab** erklärt das komplette Konzept

### Backend Fixes ✅
- [x] **SPOT Coins Endpoint** verwendet jetzt `ticker_24h` (zuverlässiger)
- [x] **FUTURES Coins Endpoint** lädt alle Contracts
- [x] **Futures API robuster** - bessere Fehlerbehandlung
- [x] **Balance Endpoint** inkludiert Futures-Daten

### KI Learning Engine ✅
- [x] Erste 10 Trades: Datensammlung
- [x] Ab Trade 11: KI übernimmt (VETO-Recht)
- [x] Feedback-Loop: Lernt aus Fehlern
- [x] KI Log Tab zeigt Lernfortschritt

### SPOT & FUTURES Trading ✅
- [x] SPOT Trading
- [x] FUTURES mit Hebel 2x-20x
- [x] Isolated Margin
- [x] Long & Short Positionen
- [x] AI entscheidet SPOT/FUTURES basierend auf Markt-Regime

## Offene Aufgaben

### P0 - Deployment
- [ ] Code auf Hetzner pullen und testen

### P2 - Zukünftig
- [ ] User Management
- [ ] Telegram-Benachrichtigungen

## Changelog
- **05.03.2026:** ✅ Budget/Reserve aus UI entfernt
- **05.03.2026:** ✅ SPOT/FUTURES Wallet getrennt angezeigt
- **05.03.2026:** ✅ Coin-Endpoint verbessert (alle Coins laden)
- **05.03.2026:** ✅ Futures-API robuster gemacht
- **05.03.2026:** ✅ Info Tab hinzugefügt
- **05.03.2026:** ✅ KI in Trading-Loop integriert
- **05.03.2026:** ✅ Coin-Auswahl im Worker

## Deployment
- **Hetzner Cloud VPS:** 178.104.19.199
- **Repository:** GitHub (Reecus24/ReeTrade)

### Deploy-Befehle:
```bash
cd /opt/reetrade
git pull origin main
cd backend && source venv/bin/activate && pip install numpy httpx tenacity
cd ../frontend && npm run build  
sudo systemctl restart reetrade-backend reetrade-worker
```
