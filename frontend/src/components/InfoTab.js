import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { 
  Brain, TrendingUp, TrendingDown, Zap, Shield, Target, 
  BarChart3, Coins, RefreshCw, AlertTriangle, CheckCircle,
  ArrowRight, Cpu, Database, LineChart
} from 'lucide-react';

export default function InfoTab() {
  return (
    <div className="space-y-6" data-testid="info-tab">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">ReeTrade Terminal</h1>
        <p className="text-zinc-400">KI-gesteuerter Trading Bot für MEXC</p>
        <Badge className="mt-2 bg-purple-600">Learning by Doing AI</Badge>
      </div>

      {/* Hauptkonzept */}
      <Card className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border-purple-700">
        <CardHeader>
          <CardTitle className="text-xl text-white flex items-center gap-2">
            <Brain className="w-6 h-6 text-purple-400" />
            Das Konzept
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-zinc-300">
            ReeTrade Terminal ist ein <strong className="text-white">selbstlernender Trading-Bot</strong>, 
            der mit deinem echten MEXC-Konto handelt. Die KI lernt aus jedem Trade und verbessert sich kontinuierlich.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div className="bg-zinc-900/50 p-4 rounded-lg text-center">
              <div className="text-3xl font-bold text-blue-400">1-10</div>
              <p className="text-sm text-zinc-400">Trades: Datensammlung</p>
              <p className="text-xs text-zinc-500">Bot handelt, KI beobachtet</p>
            </div>
            <div className="bg-zinc-900/50 p-4 rounded-lg text-center">
              <div className="text-3xl font-bold text-purple-400">11+</div>
              <p className="text-sm text-zinc-400">Trades: KI übernimmt</p>
              <p className="text-xs text-zinc-500">KI trifft Entscheidungen</p>
            </div>
            <div className="bg-zinc-900/50 p-4 rounded-lg text-center">
              <div className="text-3xl font-bold text-green-400">∞</div>
              <p className="text-sm text-zinc-400">Kontinuierliches Lernen</p>
              <p className="text-xs text-zinc-500">Aus jedem Fehler lernen</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Trading Modes */}
      <div className="grid grid-cols-1 gap-4">
        <Card className="bg-zinc-900 border-green-800">
          <CardHeader>
            <CardTitle className="text-lg text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-500" />
              SPOT Trading (Aktuell aktiv)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm text-zinc-300">
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                <span>Kein Hebel - sicherer für Anfänger</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                <span>Nur Long-Positionen (auf steigende Kurse setzen)</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                <span>Kein Liquidationsrisiko</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                <span>Ideal für BULLISH Märkte</span>
              </li>
            </ul>
            <div className="mt-4 p-3 bg-purple-900/20 border border-purple-800 rounded-lg">
              <p className="text-sm text-purple-300">
                <Brain className="w-4 h-4 inline mr-1" />
                <strong>Smart Exit KI:</strong> Die KI überwacht deine Positionen und kann intelligent früher verkaufen wenn sich der Markt ändert.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Smart Exit Engine - NEU */}
      <Card className="bg-gradient-to-r from-cyan-900/30 to-purple-900/30 border-cyan-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Brain className="w-5 h-5 text-cyan-400" />
            Intelligente Exit-Strategie
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-zinc-300">
            Die KI hält sich <strong className="text-white">nicht starr an Stop-Loss und Take-Profit</strong>. 
            Sie analysiert kontinuierlich den Markt und entscheidet selbstständig:
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-zinc-900/50 p-4 rounded-lg">
              <h4 className="font-medium text-green-400 mb-2">Kann FRÜHER verkaufen wenn:</h4>
              <ul className="text-sm text-zinc-400 space-y-1">
                <li>• Trend dreht sich um (Trendumkehr erkannt)</li>
                <li>• Momentum nachlässt</li>
                <li>• Volumen stark fällt</li>
                <li>• Mehrere rote Kerzen in Folge</li>
                <li>• RSI zeigt überkauft + negatives Momentum</li>
              </ul>
            </div>
            <div className="bg-zinc-900/50 p-4 rounded-lg">
              <h4 className="font-medium text-blue-400 mb-2">Kann LÄNGER halten wenn:</h4>
              <ul className="text-sm text-zinc-400 space-y-1">
                <li>• Trade läuft gut (über TP hinaus)</li>
                <li>• Momentum weiterhin positiv</li>
                <li>• RSI noch nicht überkauft</li>
                <li>• Trend weiterhin stark</li>
              </ul>
            </div>
          </div>
          
          <div className="p-3 bg-yellow-900/20 border border-yellow-800 rounded-lg">
            <p className="text-sm text-yellow-300">
              <AlertTriangle className="w-4 h-4 inline mr-1" />
              <strong>Lernfähig:</strong> Die KI merkt sich ihre Exit-Entscheidungen und lernt aus Fehlern. 
              War ein früher Exit falsch? Sie passt ihre Parameter für die Zukunft an!
            </p>
          </div>
        </CardContent>
      </Card>

      {/* KI Entscheidungsprozess */}
      <Card className="bg-zinc-900 border-zinc-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            Wie die KI entscheidet
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex-1 bg-zinc-800/50 p-4 rounded-lg text-center">
              <BarChart3 className="w-8 h-8 text-blue-400 mx-auto mb-2" />
              <p className="font-medium text-white">Markt analysieren</p>
              <p className="text-xs text-zinc-500">RSI, ADX, ATR, Volumen, Momentum</p>
            </div>
            
            <ArrowRight className="w-6 h-6 text-zinc-600 hidden md:block" />
            
            <div className="flex-1 bg-zinc-800/50 p-4 rounded-lg text-center">
              <Brain className="w-8 h-8 text-purple-400 mx-auto mb-2" />
              <p className="font-medium text-white">Regime erkennen</p>
              <p className="text-xs text-zinc-500">BULLISH / SIDEWAYS / BEARISH</p>
            </div>
            
            <ArrowRight className="w-6 h-6 text-zinc-600 hidden md:block" />
            
            <div className="flex-1 bg-zinc-800/50 p-4 rounded-lg text-center">
              <Target className="w-8 h-8 text-green-400 mx-auto mb-2" />
              <p className="font-medium text-white">Entry Entscheidung</p>
              <p className="text-xs text-zinc-500">KAUFEN / WARTEN</p>
            </div>
            
            <ArrowRight className="w-6 h-6 text-zinc-600 hidden md:block" />
            
            <div className="flex-1 bg-zinc-800/50 p-4 rounded-lg text-center">
              <RefreshCw className="w-8 h-8 text-cyan-400 mx-auto mb-2" />
              <p className="font-medium text-white">Smart Exit</p>
              <p className="text-xs text-zinc-500">Kontinuierliche Überwachung</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Markt-Regime Tabelle */}
      <Card className="bg-zinc-900 border-zinc-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <LineChart className="w-5 h-5 text-yellow-400" />
            Markt-Regime → KI Reaktion
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-700">
                  <th className="text-left py-2 text-zinc-400">Regime</th>
                  <th className="text-left py-2 text-zinc-400">Erkennung</th>
                  <th className="text-left py-2 text-zinc-400">KI Aktion</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-zinc-800">
                  <td className="py-3">
                    <Badge className="bg-green-600">BULLISH</Badge>
                  </td>
                  <td className="py-3 text-zinc-300">ADX &gt; 25, Preis über EMA</td>
                  <td className="py-3 text-zinc-300">
                    <span className="text-green-400">SPOT Long</span> oder 
                    <span className="text-orange-400"> Futures Long (2-3x)</span>
                  </td>
                </tr>
                <tr className="border-b border-zinc-800">
                  <td className="py-3">
                    <Badge className="bg-yellow-600">SIDEWAYS</Badge>
                  </td>
                  <td className="py-3 text-zinc-300">ADX &lt; 20, keine klare Richtung</td>
                  <td className="py-3 text-zinc-300">
                    <span className="text-blue-400">Vorsichtiger SPOT</span> oder 
                    <span className="text-zinc-500"> Skip</span>
                  </td>
                </tr>
                <tr>
                  <td className="py-3">
                    <Badge className="bg-red-600">BEARISH</Badge>
                  </td>
                  <td className="py-3 text-zinc-300">ADX &gt; 25, Preis unter EMA, neg. Momentum</td>
                  <td className="py-3 text-zinc-300">
                    <span className="text-red-400">Futures SHORT</span> 
                    <span className="text-zinc-500"> (Profit bei fallenden Kursen!)</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Risk Management */}
      <Card className="bg-zinc-900 border-zinc-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Risiko-Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              <h4 className="font-medium text-white">Stop Loss (SL)</h4>
              <p className="text-sm text-zinc-400">
                Automatisch basierend auf ATR (Average True Range). 
                Typisch 1.5x-2.5x ATR unter dem Einstiegspreis.
              </p>
              <div className="bg-red-900/20 p-2 rounded text-sm text-red-300">
                Beispiel: Entry $100, ATR $2 → SL bei ~$96
              </div>
            </div>
            
            <div className="space-y-3">
              <h4 className="font-medium text-white">Take Profit (TP)</h4>
              <p className="text-sm text-zinc-400">
                Risk:Reward Ratio von 1:1.5 bis 1:2.5 je nach Markt-Regime.
                Höheres TP bei starkem Trend.
              </p>
              <div className="bg-green-900/20 p-2 rounded text-sm text-green-300">
                Beispiel: Risiko $4 → TP bei +$6 bis +$10
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Feedback Loop */}
      <Card className="bg-gradient-to-r from-red-900/30 to-orange-900/30 border-red-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-red-400" />
            Feedback-Loop: Lernen aus Fehlern
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-zinc-300">
              Wenn ein Trade mit Verlust endet, analysiert die KI <strong className="text-white">sofort</strong> was falsch war:
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div className="bg-zinc-900/50 p-3 rounded-lg">
                <p className="text-red-400 font-medium mb-1">❌ RSI war 72 (überkauft)</p>
                <p className="text-zinc-400">→ KI senkt RSI Maximum von 70 auf 68</p>
              </div>
              <div className="bg-zinc-900/50 p-3 rounded-lg">
                <p className="text-red-400 font-medium mb-1">❌ ADX war nur 12 (kein Trend)</p>
                <p className="text-zinc-400">→ KI erhöht ADX Minimum von 20 auf 22</p>
              </div>
              <div className="bg-zinc-900/50 p-3 rounded-lg">
                <p className="text-red-400 font-medium mb-1">❌ Volumen war $150k (illiquide)</p>
                <p className="text-zinc-400">→ KI erhöht Volume Threshold auf $500k</p>
              </div>
              <div className="bg-zinc-900/50 p-3 rounded-lg">
                <p className="text-red-400 font-medium mb-1">❌ SL bei -8% getroffen</p>
                <p className="text-zinc-400">→ KI erhöht ATR Multiplier für mehr Puffer</p>
              </div>
            </div>
            
            <p className="text-xs text-zinc-500 text-center mt-4">
              Die KI passt ihre Parameter nach jedem Verlust an und wird mit der Zeit besser.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Margin Erklärung */}
      <Card className="bg-zinc-900 border-zinc-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-orange-400" />
            Isolated Margin erklärt
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-zinc-300">
              Bei Futures mit Hebel wird <strong className="text-white">Isolated Margin</strong> verwendet:
            </p>
            
            <div className="bg-orange-900/20 p-4 rounded-lg">
              <h4 className="font-medium text-orange-400 mb-2">Beispiel: 5x Hebel, $100 Margin</h4>
              <ul className="space-y-1 text-sm text-zinc-300">
                <li>• Du setzt $100 als Margin (Sicherheit)</li>
                <li>• Der Bot kontrolliert eine $500 Position (5x)</li>
                <li>• Gewinne und Verluste werden 5x verstärkt</li>
                <li>• Bei ~20% Preisrückgang: <span className="text-red-400">Liquidation</span> (du verlierst nur die $100)</li>
              </ul>
            </div>
            
            <div className="flex items-start gap-2 bg-blue-900/20 p-3 rounded-lg">
              <Shield className="w-5 h-5 text-blue-400 mt-0.5 shrink-0" />
              <p className="text-sm text-zinc-300">
                <strong className="text-blue-400">Vorteil von Isolated:</strong> Du kannst maximal nur die 
                Margin verlieren, nicht dein gesamtes Konto. Jede Position ist isoliert.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="text-center text-zinc-500 text-sm py-4">
        <p>ReeTrade Terminal v2.0 - Learning by Doing AI</p>
        <p className="text-xs mt-1">Trading mit KI birgt Risiken. Investiere nur, was du dir leisten kannst zu verlieren.</p>
      </div>
    </div>
  );
}
