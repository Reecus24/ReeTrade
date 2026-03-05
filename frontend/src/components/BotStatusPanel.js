import React from 'react';
import { Badge } from '@/components/ui/badge';
import { 
  Activity, Clock, TrendingUp, TrendingDown, Minus, 
  Shield, AlertTriangle, CheckCircle, XCircle, Pause, Cpu
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { de } from 'date-fns/locale';

const BotStatusPanel = ({ settings, mode = 'paper', balance }) => {
  const prefix = mode;
  
  const lastScan = settings?.[`${prefix}_last_scan`];
  const lastDecision = settings?.[`${prefix}_last_decision`];
  const lastRegime = settings?.[`${prefix}_last_regime`];
  const lastSymbol = settings?.[`${prefix}_last_symbol`];
  const budgetUsed = balance?.budget?.used_budget || settings?.[`${prefix}_budget_used`] || 0;
  const budgetAvailable = balance?.budget?.remaining_budget || settings?.[`${prefix}_budget_available`] || 0;
  const dailyUsed = balance?.daily_cap?.used || settings?.[`${prefix}_daily_used`] || 0;
  const dailyRemaining = balance?.daily_cap?.remaining || settings?.[`${prefix}_daily_remaining`] || 0;
  const dailyCap = balance?.daily_cap?.cap || (mode === 'live' ? settings?.live_daily_cap_usdt : settings?.paper_daily_cap_usdt) || 0;
  const positionsCount = settings?.[`${prefix}_positions_count`] || 0;
  const isRunning = mode === 'live' ? settings?.live_running : settings?.paper_running;
  
  const getDecisionInfo = () => {
    if (!lastDecision) return { icon: Minus, color: 'text-zinc-500', label: 'Kein Status' };
    
    if (lastDecision.startsWith('TRADE:')) {
      return { icon: CheckCircle, color: 'text-green-400', label: lastDecision };
    }
    if (lastDecision.startsWith('BLOCKED:')) {
      return { icon: XCircle, color: 'text-red-400', label: lastDecision };
    }
    if (lastDecision.startsWith('SKIPPED:')) {
      return { icon: Pause, color: 'text-yellow-400', label: lastDecision };
    }
    if (lastDecision === 'SCANNING') {
      return { icon: Activity, color: 'text-cyan-400', label: 'Scannt...' };
    }
    return { icon: Minus, color: 'text-zinc-500', label: lastDecision };
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
        return { icon: Minus, color: 'text-zinc-500', label: 'N/A' };
    }
  };
  
  const decisionInfo = getDecisionInfo();
  const regimeInfo = getRegimeInfo();
  const DecisionIcon = decisionInfo.icon;
  const RegimeIcon = regimeInfo.icon;
  
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD'
    }).format(value || 0);
  };
  
  return (
    <div className="cyber-panel p-6 mb-6" data-testid={`${mode}-bot-status`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center bg-red-500/20 border border-red-500/50">
            <Cpu className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className="font-cyber text-sm text-red-400 tracking-widest uppercase">Bot Status</h3>
            <p className="text-xs text-zinc-600 font-mono-cyber">TRADING ENGINE</p>
          </div>
        </div>
        <Badge className={`cyber-badge ${isRunning ? 'bg-green-500/20 text-green-400 border border-green-500/50 animate-pulse' : 'bg-zinc-800 text-zinc-500 border border-zinc-700'}`}>
          {isRunning ? 'ACTIVE' : 'OFFLINE'}
        </Badge>
      </div>
      
      <div className="grid grid-cols-4 gap-3 mb-4">
        {/* Last Scan */}
        <div className="bg-black/50 border border-cyan-500/20 p-3">
          <div className="text-[10px] text-cyan-400 flex items-center gap-1 font-mono-cyber mb-1">
            <Clock className="w-3 h-3" />
            LAST SCAN
          </div>
          <div className="text-sm font-mono-cyber text-zinc-300">
            {lastScan ? (
              <span title={format(new Date(lastScan), 'PPpp', { locale: de })}>
                {formatDistanceToNow(new Date(lastScan), { locale: de, addSuffix: true })}
              </span>
            ) : (
              <span className="text-zinc-600">-</span>
            )}
          </div>
        </div>
        
        {/* Last Symbol */}
        <div className="bg-black/50 border border-cyan-500/20 p-3">
          <div className="text-[10px] text-cyan-400 font-mono-cyber mb-1">SYMBOL</div>
          <div className="text-sm font-cyber text-white">
            {lastSymbol ? lastSymbol.replace('USDT', '') : '-'}
          </div>
        </div>
        
        {/* Regime */}
        <div className="bg-black/50 border border-cyan-500/20 p-3">
          <div className="text-[10px] text-cyan-400 font-mono-cyber mb-1">REGIME</div>
          <div className={`text-sm font-cyber flex items-center gap-1 ${regimeInfo.color}`}>
            <RegimeIcon className="w-3 h-3" />
            {regimeInfo.label}
          </div>
        </div>
        
        {/* Positions */}
        <div className="bg-black/50 border border-cyan-500/20 p-3">
          <div className="text-[10px] text-cyan-400 font-mono-cyber mb-1">POSITIONS</div>
          <div className="text-sm font-cyber text-white">
            {positionsCount} / {settings?.max_positions || 3}
          </div>
        </div>
      </div>
      
      {/* Decision - Full Width */}
      <div className="p-3 bg-black/50 border border-purple-500/20 mb-4">
        <div className="text-[10px] text-purple-400 font-mono-cyber mb-1">LAST DECISION</div>
        <div className={`text-sm font-mono-cyber flex items-center gap-2 ${decisionInfo.color}`}>
          <DecisionIcon className="w-4 h-4 flex-shrink-0" />
          <span>{decisionInfo.label}</span>
        </div>
      </div>
      
      {/* Budget & Daily Cap Bar */}
      <div className="grid grid-cols-2 gap-3">
        {/* Budget */}
        <div className="p-3 bg-black/50 border border-cyan-500/20">
          <div className="flex justify-between text-[10px] mb-2 font-mono-cyber">
            <span className="text-cyan-400">BUDGET</span>
            <span className="text-zinc-500">
              {formatCurrency(budgetUsed)} / {formatCurrency(budgetUsed + budgetAvailable)}
            </span>
          </div>
          <div className="cyber-progress">
            <div 
              className="h-full transition-all"
              style={{ 
                width: `${Math.min(100, (budgetUsed / (budgetUsed + budgetAvailable || 1)) * 100)}%`,
                background: budgetAvailable <= 0 ? '#ff0044' : budgetAvailable < 50 ? '#ffff00' : 'linear-gradient(90deg, #bf00ff, #00f0ff)'
              }}
            />
          </div>
          <div className="text-[10px] text-zinc-600 mt-1 font-mono-cyber">
            {formatCurrency(budgetAvailable)} AVAILABLE
          </div>
        </div>
        
        {/* Daily Cap */}
        <div className="p-3 bg-black/50 border border-cyan-500/20">
          <div className="flex justify-between text-[10px] mb-2 font-mono-cyber">
            <span className="text-cyan-400">DAILY CAP</span>
            <span className="text-zinc-500">
              {formatCurrency(dailyUsed)} / {formatCurrency(dailyCap)}
            </span>
          </div>
          <div className="cyber-progress">
            <div 
              className="h-full transition-all"
              style={{ 
                width: `${Math.min(100, (dailyUsed / dailyCap) * 100)}%`,
                background: dailyRemaining <= 0 ? '#ff0044' : (dailyUsed / dailyCap) > 0.7 ? '#ffff00' : 'linear-gradient(90deg, #bf00ff, #00f0ff)'
              }}
            />
          </div>
          <div className={`text-[10px] mt-1 font-mono-cyber ${dailyRemaining <= 0 ? 'text-red-400' : 'text-zinc-600'}`}>
            {dailyRemaining <= 0 ? 'LIMIT REACHED' : `${formatCurrency(dailyRemaining)} AVAILABLE`}
          </div>
        </div>
      </div>
      
      {/* Blocking Warnings */}
      {lastDecision?.startsWith('BLOCKED:') && (
        <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span className="text-sm text-red-400 font-mono-cyber">{lastDecision}</span>
        </div>
      )}
    </div>
  );
};

export default BotStatusPanel;
