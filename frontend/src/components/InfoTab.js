import React from 'react';
import { Badge } from './ui/badge';
import { 
  Brain, TrendingUp, Zap, Target, 
  RefreshCw, AlertTriangle, CheckCircle,
  ArrowRight, Activity
} from 'lucide-react';

export default function InfoTab() {
  return (
    <div className="space-y-8 text-base" data-testid="info-tab">
      {/* Header */}
      <div className="text-center mb-10">
        <h1 className="font-cyber text-4xl text-white tracking-wider mb-3">
          Ree<span className="text-cyan-400 glow-cyan">Trade</span> Terminal
        </h1>
        <p className="text-lg text-zinc-300">Selbstlernender Trading Bot für MEXC SPOT</p>
        <Badge className="mt-4 cyber-badge bg-purple-500/20 text-purple-400 border border-purple-500/50 text-sm px-4 py-1">
          Reinforcement Learning KI
        </Badge>
      </div>

      {/* Hauptkonzept */}
      <div className="cyber-panel p-8 box-glow-purple">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
            <Brain className="w-6 h-6 text-purple-400" />
          </div>
          <h3 className="font-cyber text-lg text-purple-400 tracking-widest uppercase">Was ist ReeTrade?</h3>
        </div>
        
        <p className="text-lg text-zinc-200 mb-8 leading-relaxed">
          ReeTrade ist ein <strong className="text-white">selbstlernender Trading-Bot</strong>, 
          der mit deinem echten MEXC-Konto handelt. Die KI lernt aus <strong className="text-cyan-400">jedem einzelnen Trade</strong> und 
          verbessert ihre Strategie kontinuierlich.
        </p>
        
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-black/50 border border-cyan-500/30 p-6 text-center">
            <div className="text-4xl font-cyber text-cyan-400 mb-2">1-10</div>
            <p className="text-base text-zinc-200 mb-1">Lernphase</p>
            <p className="text-sm text-zinc-400">KI sammelt Erfahrung</p>
          </div>
          <div className="bg-black/50 border border-purple-500/30 p-6 text-center">
            <div className="text-4xl font-cyber text-purple-400 mb-2">11+</div>
            <p className="text-base text-zinc-200 mb-1">KI übernimmt</p>
            <p className="text-sm text-zinc-400">Nutzt gelerntes Wissen</p>
          </div>
          <div className="bg-black/50 border border-green-500/30 p-6 text-center">
            <div className="text-4xl font-cyber text-green-400 mb-2">∞</div>
            <p className="text-base text-zinc-200 mb-1">Immer besser</p>
            <p className="text-sm text-zinc-400">Lernt aus jedem Trade</p>
          </div>
        </div>
      </div>

      {/* Wie funktioniert die KI */}
      <div className="cyber-panel p-8 box-glow-cyan">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 flex items-center justify-center bg-cyan-500/20 border border-cyan-500/50">
            <Zap className="w-6 h-6 text-cyan-400" />
          </div>
          <h3 className="font-cyber text-lg text-cyan-400 tracking-widest uppercase">Wie lernt die KI?</h3>
        </div>
        
        <p className="text-lg text-zinc-200 mb-6 leading-relaxed">
          Die KI verwendet <strong className="text-cyan-400">Reinforcement Learning</strong> - 
          sie lernt durch Versuch und Irrtum, genau wie ein Mensch.
        </p>
        
        <div className="space-y-4">
          <div className="flex items-start gap-4 p-5 bg-black/50 border border-cyan-500/20">
            <Activity className="w-6 h-6 text-cyan-400 mt-1 shrink-0" />
            <div>
              <p className="text-lg text-white font-semibold mb-1">1. Markt analysieren</p>
              <p className="text-base text-zinc-300">RSI, EMA, Volumen, Momentum und mehr werden geprüft</p>
            </div>
          </div>
          <div className="flex items-start gap-4 p-5 bg-black/50 border border-purple-500/20">
            <Brain className="w-6 h-6 text-purple-400 mt-1 shrink-0" />
            <div>
              <p className="text-lg text-white font-semibold mb-1">2. Entscheidung treffen</p>
              <p className="text-base text-zinc-300">KAUFEN, HALTEN oder VERKAUFEN - die KI entscheidet</p>
            </div>
          </div>
          <div className="flex items-start gap-4 p-5 bg-black/50 border border-green-500/20">
            <Target className="w-6 h-6 text-green-400 mt-1 shrink-0" />
            <div>
              <p className="text-lg text-white font-semibold mb-1">3. Aus Ergebnis lernen</p>
              <p className="text-base text-zinc-300">Gewinn = "Das war gut!" | Verlust = "Das mache ich anders"</p>
            </div>
          </div>
        </div>
        
        <div className="mt-6 p-5 bg-purple-500/10 border border-purple-500/30">
          <p className="text-base text-purple-300">
            <Zap className="w-5 h-5 inline mr-2" />
            <strong>Exploration vs Exploitation:</strong> Am Anfang probiert die KI viel aus (Exploration). 
            Mit mehr Erfahrung verlässt sie sich immer mehr auf bewährte Strategien (Exploitation).
          </p>
        </div>
      </div>

      {/* SPOT Trading */}
      <div className="cyber-panel p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 flex items-center justify-center bg-green-500/20 border border-green-500/50">
            <TrendingUp className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h3 className="font-cyber text-lg text-green-400 tracking-widest uppercase">SPOT Trading</h3>
            <p className="text-sm text-zinc-400">Sicher und einfach</p>
          </div>
        </div>
        
        <ul className="space-y-4 text-base">
          <li className="flex items-start gap-3">
            <CheckCircle className="w-6 h-6 text-green-500 mt-0.5 shrink-0" />
            <span className="text-zinc-200"><strong className="text-white">Kein Hebel</strong> - Du handelst nur mit dem was du hast</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle className="w-6 h-6 text-green-500 mt-0.5 shrink-0" />
            <span className="text-zinc-200"><strong className="text-white">Nur Long</strong> - Kaufen wenn günstig, verkaufen wenn teurer</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle className="w-6 h-6 text-green-500 mt-0.5 shrink-0" />
            <span className="text-zinc-200"><strong className="text-white">Kein Liquidationsrisiko</strong> - Du verlierst maximal deinen Einsatz</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle className="w-6 h-6 text-green-500 mt-0.5 shrink-0" />
            <span className="text-zinc-200"><strong className="text-white">100+ Coins</strong> - Die KI wählt die besten Chancen aus</span>
          </li>
        </ul>
      </div>

      {/* Decision Flow */}
      <div className="cyber-panel p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 flex items-center justify-center bg-cyan-500/20 border border-cyan-500/50">
            <RefreshCw className="w-6 h-6 text-cyan-400" />
          </div>
          <h3 className="font-cyber text-lg text-cyan-400 tracking-widest uppercase">So arbeitet die KI</h3>
        </div>
        
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex-1 bg-black/50 border border-cyan-500/30 p-6 text-center">
            <Activity className="w-8 h-8 text-cyan-400 mx-auto mb-3" />
            <p className="text-base font-semibold text-white mb-1">SCAN</p>
            <p className="text-sm text-zinc-400">100+ Coins prüfen</p>
          </div>
          
          <ArrowRight className="w-6 h-6 text-cyan-500/50 hidden md:block" />
          
          <div className="flex-1 bg-black/50 border border-purple-500/30 p-6 text-center">
            <Brain className="w-8 h-8 text-purple-400 mx-auto mb-3" />
            <p className="text-base font-semibold text-white mb-1">ANALYSE</p>
            <p className="text-sm text-zinc-400">22 Indikatoren</p>
          </div>
          
          <ArrowRight className="w-6 h-6 text-cyan-500/50 hidden md:block" />
          
          <div className="flex-1 bg-black/50 border border-green-500/30 p-6 text-center">
            <Target className="w-8 h-8 text-green-400 mx-auto mb-3" />
            <p className="text-base font-semibold text-white mb-1">TRADE</p>
            <p className="text-sm text-zinc-400">Kaufen / Verkaufen</p>
          </div>
          
          <ArrowRight className="w-6 h-6 text-cyan-500/50 hidden md:block" />
          
          <div className="flex-1 bg-black/50 border border-yellow-500/30 p-6 text-center">
            <RefreshCw className="w-8 h-8 text-yellow-400 mx-auto mb-3" />
            <p className="text-base font-semibold text-white mb-1">LERNEN</p>
            <p className="text-sm text-zinc-400">Strategie anpassen</p>
          </div>
        </div>
      </div>

      {/* Sicherheit */}
      <div className="cyber-panel p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 flex items-center justify-center bg-blue-500/20 border border-blue-500/50">
            <Target className="w-6 h-6 text-blue-400" />
          </div>
          <h3 className="font-cyber text-lg text-blue-400 tracking-widest uppercase">Risiko-Management</h3>
        </div>
        
        <div className="grid grid-cols-2 gap-6">
          <div className="p-6 bg-black/50 border border-red-500/30">
            <h4 className="text-lg font-semibold text-red-400 mb-3">Stop Loss</h4>
            <p className="text-base text-zinc-300 mb-3">
              Automatischer Verkauf bei zu großem Verlust. Basiert auf der Volatilität des Coins.
            </p>
            <div className="p-3 bg-red-500/10 text-base text-red-300">
              Typisch: 2-4% unter Kaufpreis
            </div>
          </div>
          
          <div className="p-6 bg-black/50 border border-green-500/30">
            <h4 className="text-lg font-semibold text-green-400 mb-3">Take Profit</h4>
            <p className="text-base text-zinc-300 mb-3">
              Automatischer Verkauf bei Zielgewinn. Die KI passt das Ziel dynamisch an.
            </p>
            <div className="p-3 bg-green-500/10 text-base text-green-300">
              Typisch: 4-8% über Kaufpreis
            </div>
          </div>
        </div>
      </div>

      {/* Warning */}
      <div className="p-6 border border-yellow-500/40 bg-yellow-500/10">
        <div className="flex items-start gap-4">
          <AlertTriangle className="w-8 h-8 text-yellow-400 shrink-0" />
          <div>
            <p className="text-lg font-semibold text-yellow-400 mb-2">Wichtiger Hinweis</p>
            <p className="text-base text-zinc-200 leading-relaxed">
              Die KI lernt durch <strong className="text-white">echte Trades mit echtem Geld</strong>. 
              Die ersten Trades können Verluste bringen - das ist Teil des Lernprozesses. 
              Investiere nur, was du dir leisten kannst zu verlieren.
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center py-6">
        <p className="font-cyber text-base text-zinc-400 tracking-widest">
          REETRADE TERMINAL v2.0
        </p>
        <p className="text-sm text-zinc-500 mt-2">
          Reinforcement Learning Trading • MEXC SPOT • Automatisiert
        </p>
      </div>
    </div>
  );
}
