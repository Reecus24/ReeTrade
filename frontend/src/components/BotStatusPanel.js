import React from 'react';
import { Badge } from '@/components/ui/badge';
import { 
  Activity, Clock, TrendingUp, TrendingDown, Minus, 
  CheckCircle, XCircle, Pause, Brain
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { de } from 'date-fns/locale';

const BotStatusPanel = ({ settings, mode = 'paper', balance, actualPositionsCount }) => {
  const prefix = mode;
  
  const lastScan = settings?.[`${prefix}_last_scan`];
  const lastDecision = settings?.[`${prefix}_last_decision`];
  const lastRegime = settings?.[`${prefix}_last_regime`];
  const lastSymbol = settings?.[`${prefix}_last_symbol`];
  // Verwende actualPositionsCount (Array-Länge) für konsistente Werte mit PositionsPanel
  const positionsCount = actualPositionsCount ?? balance?.open_positions_count ?? settings?.[`${prefix}_positions_count`] ?? 0;
  const maxPositions = balance?.ai_max_positions ?? settings?.max_positions ?? 5;
  const isRunning = mode === 'live' ? settings?.live_running : settings?.paper_running;
  
  const getDecisionInfo = () => {
    if (!lastDecision) return { icon: Minus, color: 'text-zinc-400', label: 'Waiting...' };
    
    if (lastDecision.startsWith('TRADE:') || lastDecision.includes('RL-AI')) {
      return { icon: CheckCircle, color: 'text-green-400', label: lastDecision };
    }
    if (lastDecision.startsWith('BLOCKED:')) {
      return { icon: XCircle, color: 'text-red-400', label: lastDecision };
    }
    if (lastDecision.startsWith('SKIPPED:')) {
      return { icon: Pause, color: 'text-yellow-400', label: lastDecision };
    }
    if (lastDecision === 'SCANNING') {
      return { icon: Activity, color: 'text-cyan-400', label: 'Scanning Market...' };
    }
    return { icon: Minus, color: 'text-zinc-400', label: lastDecision };
  };
  
  const getRegimeInfo = () => {
    switch (lastRegime) {
      case 'BULLISH':
        return { icon: TrendingUp, color: 'text-green-400', label: 'BULLISH' };
      case 'BEARISH':
        return { icon: TrendingDown, color: 'text-red-400', label: 'BEARISH' };
      case 'SIDEWAYS':
        return { icon: Minus, color: 'text-yellow-400', label: 'SIDEWAYS' };
      default:
        return { icon: Minus, color: 'text-zinc-400', label: '-' };
    }
  };
  
  const decisionInfo = getDecisionInfo();
  const regimeInfo = getRegimeInfo();
  const DecisionIcon = decisionInfo.icon;
  const RegimeIcon = regimeInfo.icon;
  
  return (
    <div className="cyber-panel p-6 mb-6" data-testid={`${mode}-bot-status`}>
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
            <Brain className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h3 className="font-cyber text-lg text-purple-400 tracking-widest uppercase">KI Status</h3>
            <p className="text-sm text-zinc-400">Reinforcement Learning Engine</p>
          </div>
        </div>
        <Badge className={`cyber-badge text-sm ${isRunning ? 'bg-green-500/20 text-green-400 border border-green-500/50 animate-pulse' : 'bg-zinc-800 text-zinc-400 border border-zinc-700'}`}>
          {isRunning ? 'AKTIV' : 'OFFLINE'}
        </Badge>
      </div>
      
      <div className="grid grid-cols-4 gap-4 mb-5">
        {/* Last Scan */}
        <div className="bg-black/50 border border-purple-500/20 p-4">
          <div className="text-sm text-purple-400 flex items-center gap-2 font-mono-cyber mb-2">
            <Clock className="w-4 h-4" />
            LAST SCAN
          </div>
          <div className="text-base font-mono-cyber text-zinc-200">
            {lastScan ? (
              <span title={format(new Date(lastScan), 'PPpp', { locale: de })}>
                {formatDistanceToNow(new Date(lastScan), { locale: de, addSuffix: true })}
              </span>
            ) : (
              <span className="text-zinc-500">-</span>
            )}
          </div>
        </div>
        
        {/* Last Symbol */}
        <div className="bg-black/50 border border-purple-500/20 p-4">
          <div className="text-sm text-purple-400 font-mono-cyber mb-2">LAST COIN</div>
          <div className="text-xl font-cyber text-white">
            {lastSymbol ? lastSymbol.replace('USDT', '') : '-'}
          </div>
        </div>
        
        {/* Regime */}
        <div className="bg-black/50 border border-purple-500/20 p-4">
          <div className="text-sm text-purple-400 font-mono-cyber mb-2">MARKET</div>
          <div className={`text-lg font-cyber flex items-center gap-2 ${regimeInfo.color}`}>
            <RegimeIcon className="w-5 h-5" />
            {regimeInfo.label}
          </div>
        </div>
        
        {/* Positions */}
        <div className="bg-black/50 border border-purple-500/20 p-4">
          <div className="text-sm text-purple-400 font-mono-cyber mb-2">POSITIONS</div>
          <div className="text-xl font-cyber text-white">
            {positionsCount} <span className="text-zinc-500">/ {maxPositions}</span>
          </div>
        </div>
      </div>
      
      {/* Last Decision */}
      <div className="p-4 bg-black/50 border border-purple-500/20">
        <div className="text-sm text-purple-400 font-mono-cyber mb-2">LAST DECISION</div>
        <div className={`text-base font-mono-cyber flex items-center gap-3 ${decisionInfo.color}`}>
          <DecisionIcon className="w-5 h-5 flex-shrink-0" />
          <span>{decisionInfo.label}</span>
        </div>
      </div>
      
      {/* Blocking Warning */}
      {lastDecision?.startsWith('BLOCKED:') && (
        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 flex items-center gap-3">
          <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <span className="text-base text-red-400 font-mono-cyber">{lastDecision}</span>
        </div>
      )}
    </div>
  );
};

export default BotStatusPanel;
