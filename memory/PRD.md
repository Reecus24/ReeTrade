# ReeTrade Terminal - Product Requirements Document

## Originale Anforderung
KI-gesteuerter Trading Bot für MEXC mit:
- **Vollautomatischer SPOT Trading** - Die KI übernimmt komplett
- **Learning by Doing AI** - KI übernimmt nach 10 Trades
- **Smart Exit Engine** - KI entscheidet selbstständig wann verkaufen
- **Keine starren TP/SL** - KI analysiert Markt kontinuierlich
- **Portfolio-basiertes Position Sizing** (% vom Wallet)

## Implementierte Features (05.03.2026)

### Smart Exit Engine (NEU)
- **Intelligente Verkaufsentscheidungen** ohne starre TP/SL
- KI analysiert kontinuierlich:
  - RSI, Momentum, EMA20
  - Candlestick-Patterns (rote/grüne Kerzen)
  - Volumen-Änderungen
  - Trendumkehr-Signale
- **Kann FRÜHER verkaufen** wenn:
  - Trendumkehr erkannt
  - Momentum nachlässt
  - Volumen stark fällt
  - Mehrere rote Kerzen in Folge
- **Kann LÄNGER halten** wenn:
  - Trade läuft gut (über TP hinaus)
  - Momentum weiterhin positiv
  - RSI noch nicht überkauft
- **Lernfähig**: Passt Parameter basierend auf vergangenen Exit-Entscheidungen an

### FUTURES deaktiviert
- FUTURES Tab ausgeblendet (kommt später)
- FUTURES API Keys ausgeblendet
- Fokus auf SPOT Trading

### UI Änderungen
- Nur noch **Settings** und **Info** Tabs (vor Live-Aktivierung)
- Nach Live-Aktivierung: **SPOT**, **KI Log**, **Logs** Tabs
- **Info Tab** erklärt die neue Smart Exit KI

## Architektur

```
/app/backend/
├── smart_exit_engine.py     # NEU: Intelligente Exit-Logik
├── ki_learning_engine.py    # Lernende KI
├── ai_engine_v2.py          # AI Trading Engine
├── worker.py                # Trading Worker (mit Smart Exit Integration)
└── server.py                # FastAPI Backend

/app/frontend/src/
├── pages/DashboardPage.js   # FUTURES Tab ausgeblendet
├── components/
│   ├── InfoTab.js           # Aktualisiert: Smart Exit erklärt
│   └── SettingsTab.js       # FUTURES Keys ausgeblendet
```

## Wie die Smart Exit KI funktioniert

1. **Alle 30 Sekunden** prüft der Worker alle offenen Positionen
2. Für jede Position werden Marktdaten gesammelt:
   - Aktueller Preis, RSI, Momentum, EMA20
   - Candlestick-Pattern der letzten Kerzen
   - Volumen-Verhältnis
3. **Smart Exit Engine** analysiert die Daten
4. Bei Exit-Signal:
   - KI loggt die Entscheidung mit Begründung
   - Position wird geschlossen
   - Ergebnis wird für zukünftiges Lernen gespeichert
5. Bei Hold-Signal:
   - Position bleibt offen
   - Nächster Check in 30 Sekunden

## Deployment auf Hetzner

```bash
cd /opt/reetrade && git pull
cd frontend && npm run build && cd ..
sudo systemctl restart reetrade-backend reetrade-worker
```

## Offene Aufgaben

### P1
- [ ] Smart Exit Engine mit echten Trades testen
- [ ] KI-Log Tab für Exit-Entscheidungen anzeigen

### P2 (Zukunft)
- [ ] FUTURES Trading wieder aktivieren (wenn MEXC erlaubt)
- [ ] Telegram-Benachrichtigungen
- [ ] User Management Admin Tab
