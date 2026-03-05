import React from 'react';
import { Badge } from './ui/badge';
import { 
  Brain, TrendingUp, Zap, Shield, Target, 
  BarChart3, RefreshCw, AlertTriangle, CheckCircle,
  ArrowRight, Cpu, Database, LineChart, Activity
} from 'lucide-react';

export default function InfoTab() {
  return (
    <div className="space-y-6" data-testid="info-tab">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="font-cyber text-3xl text-white tracking-wider mb-2">
          Ree<span className="text-cyan-400 glow-cyan">Trade</span> Terminal
        </h1>
        <p className="text-zinc-500 font-mono-cyber">KI-gesteuerter Trading Bot für MEXC</p>
        <Badge className="mt-3 cyber-badge bg-purple-500/20 text-purple-400 border border-purple-500/50">
          Learning by Doing AI
        </Badge>
      </div>

      {/* Hauptkonzept */}
      <div className="cyber-panel p-6 box-glow-purple">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
            <Brain className="w-5 h-5 text-purple-400" />
          </div>
          <h3 className="font-cyber text-sm text-purple-400 tracking-widest uppercase">Das Konzept</h3>
        </div>
        
        <p className="text-zinc-400 font-mono-cyber text-sm mb-6">
          ReeTrade Terminal ist ein <strong className="text-white">selbstlernender Trading-Bot</strong>, 
          der mit deinem echten MEXC-Konto handelt. Die KI lernt aus jedem Trade und verbessert sich kontinuierlich.
        </p>
        
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-black/50 border border-cyan-500/20 p-4 text-center">
            <div className="text-3xl font-cyber text-cyan-400">1-10</div>
            <p className="text-xs text-zinc-500 font-mono-cyber mt-1">Trades: Datensammlung</p>
            <p className="text-[10px] text-zinc-600 mt-1">Bot handelt, KI beobachtet</p>
          </div>
          <div className="bg-black/50 border border-purple-500/20 p-4 text-center">
            <div className="text-3xl font-cyber text-purple-400">11+</div>
            <p className="text-xs text-zinc-500 font-mono-cyber mt-1">Trades: KI übernimmt</p>
            <p className="text-[10px] text-zinc-600 mt-1">KI trifft Entscheidungen</p>
          </div>
          <div className="bg-black/50 border border-green-500/20 p-4 text-center">
            <div className="text-3xl font-cyber text-green-400">∞</div>
            <p className="text-xs text-zinc-500 font-mono-cyber mt-1">Kontinuierliches Lernen</p>
            <p className="text-[10px] text-zinc-600 mt-1">Aus jedem Fehler lernen</p>
          </div>
        </div>
      </div>

      {/* RL-KI Erklärung */}
      <div className="cyber-panel p-6 box-glow-cyan">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-cyan-500/20 border border-cyan-500/50">
            <Cpu className="w-5 h-5 text-cyan-400" />
          </div>
          <h3 className="font-cyber text-sm text-cyan-400 tracking-widest uppercase">Reinforcement Learning KI</h3>
        </div>
        
        <p className="text-zinc-400 font-mono-cyber text-sm mb-4">
          Die KI verwendet <strong className="text-cyan-400">Q-Learning</strong>, um die beste Handelsstrategie zu finden:
        </p>
        
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-3 bg-black/50 border border-cyan-500/10">
            <Activity className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm text-white font-mono-cyber">STATE → Marktdaten analysieren</p>
              <p className="text-xs text-zinc-600">RSI, EMA, Volumen, Momentum, Kerzenmuster</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-black/50 border border-purple-500/10">
            <Brain className="w-5 h-5 text-purple-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm text-white font-mono-cyber">ACTION → Entscheidung treffen</p>
              <p className="text-xs text-zinc-600">HOLD (warten), BUY (kaufen), SELL (verkaufen)</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-black/50 border border-green-500/10">
            <Target className="w-5 h-5 text-green-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm text-white font-mono-cyber">REWARD → Aus Ergebnis lernen</p>
              <p className="text-xs text-zinc-600">Profit = positives Signal, Verlust = negative Anpassung</p>
            </div>
          </div>
        </div>
        
        <div className="mt-4 p-3 bg-purple-500/5 border border-purple-500/20">
          <p className="text-xs text-purple-400 font-mono-cyber">
            <Zap className="w-3 h-3 inline mr-1" />
            Die KI beginnt mit Exploration (probiert verschiedene Strategien) und verlässt sich mit mehr Trades immer mehr auf gelerntes Wissen.
          </p>
        </div>
      </div>

      {/* SPOT Trading */}
      <div className="cyber-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-green-500/20 border border-green-500/50">
            <TrendingUp className="w-5 h-5 text-green-400" />
          </div>
          <div>
            <h3 className="font-cyber text-sm text-green-400 tracking-widest uppercase">SPOT Trading</h3>
            <p className="text-xs text-zinc-600 font-mono-cyber">AKTIV</p>
          </div>
        </div>
        
        <ul className="space-y-2 text-sm text-zinc-400 font-mono-cyber">
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
            <span>Kein Hebel - sicherer für Anfänger</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
            <span>Nur Long-Positionen (auf steigende Kurse)</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
            <span>Kein Liquidationsrisiko</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
            <span>RL-KI analysiert Markt und entscheidet autonom</span>
          </li>
        </ul>
      </div>

      {/* KI Entscheidungsprozess */}
      <div className="cyber-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-cyan-500/20 border border-cyan-500/50">
            <LineChart className="w-5 h-5 text-cyan-400" />
          </div>
          <h3 className="font-cyber text-sm text-cyan-400 tracking-widest uppercase">KI Decision Flow</h3>
        </div>
        
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex-1 bg-black/50 border border-cyan-500/20 p-4 text-center">
            <BarChart3 className="w-6 h-6 text-cyan-400 mx-auto mb-2" />
            <p className="text-xs text-white font-mono-cyber">ANALYZE</p>
            <p className="text-[10px] text-zinc-600">22 Features</p>
          </div>
          
          <ArrowRight className="w-5 h-5 text-cyan-500/50 hidden md:block" />
          
          <div className="flex-1 bg-black/50 border border-purple-500/20 p-4 text-center">
            <Brain className="w-6 h-6 text-purple-400 mx-auto mb-2" />
            <p className="text-xs text-white font-mono-cyber">PROCESS</p>
            <p className="text-[10px] text-zinc-600">Neural Net</p>
          </div>
          
          <ArrowRight className="w-5 h-5 text-cyan-500/50 hidden md:block" />
          
          <div className="flex-1 bg-black/50 border border-green-500/20 p-4 text-center">
            <Target className="w-6 h-6 text-green-400 mx-auto mb-2" />
            <p className="text-xs text-white font-mono-cyber">DECIDE</p>
            <p className="text-[10px] text-zinc-600">BUY/HOLD/SELL</p>
          </div>
          
          <ArrowRight className="w-5 h-5 text-cyan-500/50 hidden md:block" />
          
          <div className="flex-1 bg-black/50 border border-yellow-500/20 p-4 text-center">
            <RefreshCw className="w-6 h-6 text-yellow-400 mx-auto mb-2" />
            <p className="text-xs text-white font-mono-cyber">LEARN</p>
            <p className="text-[10px] text-zinc-600">From Result</p>
          </div>
        </div>
      </div>

      {/* Risk Management */}
      <div className="cyber-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-blue-500/20 border border-blue-500/50">
            <Shield className="w-5 h-5 text-blue-400" />
          </div>
          <h3 className="font-cyber text-sm text-blue-400 tracking-widest uppercase">Risk Management</h3>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-black/50 border border-red-500/20">
            <h4 className="font-mono-cyber text-sm text-red-400 mb-2">STOP LOSS</h4>
            <p className="text-xs text-zinc-500 font-mono-cyber">
              Automatisch basierend auf ATR. Typisch 1.5x-2.5x ATR unter Entry.
            </p>
            <div className="mt-2 p-2 bg-red-500/10 text-xs text-red-300 font-mono-cyber">
              Entry $100, ATR $2 → SL ~$96
            </div>
          </div>
          
          <div className="p-4 bg-black/50 border border-green-500/20">
            <h4 className="font-mono-cyber text-sm text-green-400 mb-2">TAKE PROFIT</h4>
            <p className="text-xs text-zinc-500 font-mono-cyber">
              Risk:Reward 1:1.5 bis 1:2.5 je nach Markt-Regime.
            </p>
            <div className="mt-2 p-2 bg-green-500/10 text-xs text-green-300 font-mono-cyber">
              Risiko $4 → TP +$6 bis +$10
            </div>
          </div>
        </div>
      </div>

      {/* Feedback Loop */}
      <div className="cyber-panel p-6 box-glow-red" style={{boxShadow: '0 0 15px rgba(255,0,68,0.2)'}}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-red-500/20 border border-red-500/50">
            <RefreshCw className="w-5 h-5 text-red-400" />
          </div>
          <h3 className="font-cyber text-sm text-red-400 tracking-widest uppercase">Learning from Losses</h3>
        </div>
        
        <p className="text-zinc-400 font-mono-cyber text-sm mb-4">
          Wenn ein Trade mit Verlust endet, analysiert die KI <strong className="text-white">sofort</strong> was falsch war:
        </p>
        
        <div className="grid grid-cols-2 gap-3 text-xs font-mono-cyber">
          <div className="p-3 bg-black/50 border border-red-500/10">
            <p className="text-red-400">❌ RSI war 72</p>
            <p className="text-zinc-600">→ KI senkt RSI Maximum</p>
          </div>
          <div className="p-3 bg-black/50 border border-red-500/10">
            <p className="text-red-400">❌ ADX nur 12</p>
            <p className="text-zinc-600">→ KI erhöht ADX Minimum</p>
          </div>
          <div className="p-3 bg-black/50 border border-red-500/10">
            <p className="text-red-400">❌ Volumen $150k</p>
            <p className="text-zinc-600">→ KI erhöht Vol-Threshold</p>
          </div>
          <div className="p-3 bg-black/50 border border-red-500/10">
            <p className="text-red-400">❌ SL -8% getroffen</p>
            <p className="text-zinc-600">→ KI passt ATR Multiplier an</p>
          </div>
        </div>
        
        <p className="text-[10px] text-zinc-600 text-center mt-4 font-mono-cyber">
          Die KI passt sich nach jedem Verlust an und wird mit der Zeit besser.
        </p>
      </div>

      {/* Warning */}
      <div className="p-4 border border-yellow-500/30 bg-yellow-500/5">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm text-yellow-400 font-mono-cyber">WARNING</p>
            <p className="text-xs text-zinc-500 font-mono-cyber mt-1">
              Trading mit KI birgt Risiken. Die KI lernt durch echte Trades mit echtem Geld. 
              Investiere nur, was du dir leisten kannst zu verlieren.
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center py-4">
        <p className="font-cyber text-xs text-zinc-600 tracking-widest">
          REETRADE TERMINAL v2.0
        </p>
        <p className="text-[10px] text-zinc-700 font-mono-cyber mt-1">
          REINFORCEMENT LEARNING TRADING AI
        </p>
      </div>
    </div>
  );
}
