# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Learning by Doing AI** - KI übernimmt nach 10 Trades
- **SPOT & FUTURES Trading** (komplett getrennt)
- **Alles automatisch** - KI setzt Limits, SL/TP selbst
- Portfolio-basiertes Position Sizing

## Implementierte Features (05.03.2026)

### Neue Tab-Struktur ✅
- **Info Tab als Default** - Öffnet sich beim Start
- **Settings Tab** - Oben/Links positioniert
- **SPOT Tab** - Separate History für SPOT Trades
- **FUTURES Tab** - Separate History + Konto + Positionen
- **KI Log Tab** - Was die KI gelernt hat
- **Logs Tab** - System Logs

### SPOT History ✅
- Eigene History nur für SPOT Trades
- PnL Chart getrennt
- Win Rate nur für SPOT

### FUTURES Tab (komplett) ✅
- **Futures Konto** - Balance, Margin, PnL
- **Offene Positionen** - Live mit Liquidationspreis
- **Futures History** - Alle Long/Short Trades
- **Einstellungen** - Hebel, Short erlauben
- **Alles automatisch** - KI setzt SL/TP automatisch

### KI Learning Engine ✅
- Erste 10 Trades: Datensammlung
- Ab Trade 11: KI übernimmt
- Feedback-Loop: Lernt aus Fehlern
- Gelernte Parameter automatisch angepasst

### Entfernt ✅
- Budget/Reserve System
- Manuelle Limit-Eingabe
- Daily Cap

## Offene Aufgaben

### P0
- [ ] Deployment auf Hetzner

### P2
- [ ] Telegram-Benachrichtigungen
- [ ] User Management

## Deployment
```bash
cd /opt/reetrade && git pull origin main
cd backend && source venv/bin/activate && pip install numpy httpx tenacity
cd ../frontend && npm run build  
sudo systemctl restart reetrade-backend reetrade-worker
```
