import React from 'react';
import { Badge } from '@/components/ui/badge';
import { 
  Activity, Clock, TrendingUp, TrendingDown, Minus, 
  Shield, AlertTriangle, CheckCircle, XCircle, Pause
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { de } from 'date-fns/locale';

const BotStatusPanel = ({ settings, mode = 'paper', balance }) => {
  const prefix = mode;
  
  // Get status data for the mode
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
  
  // Determine decision status
  const getDecisionInfo = () => {
    if (!lastDecision) return { icon: Minus, color: 'text-zinc-500', label: 'Kein Status' };
    
    if (lastDecision.startsWith('TRADE:')) {
      return { icon: CheckCircle, color: 'text-green-500', label: lastDecision };
    }
    if (lastDecision.startsWith('BLOCKED:')) {
      return { icon: XCircle, color: 'text-red-500', label: lastDecision };
    }
    if (lastDecision.startsWith('SKIPPED:')) {
      return { icon: Pause, color: 'text-yellow-500', label: lastDecision };
    }
    if (lastDecision === 'SCANNING') {
      return { icon: Activity, color: 'text-blue-500', label: 'Scannt...' };
    }
    return { icon: Minus, color: 'text-zinc-500', label: lastDecision };
  };
  
  // Get regime icon
  const getRegimeInfo = () => {
    switch (lastRegime) {
      case 'BULLISH':
        return { icon: TrendingUp, color: 'text-green-500', label: 'BULLISH' };
      case 'BEARISH':
        return { icon: TrendingDown, color: 'text-red-500', label: 'BEARISH' };
      case 'SIDEWAYS':
        return { icon: Minus, color: 'text-yellow-500', label: 'SIDEWAYS' };
      default:
        return { icon: Minus, color: 'text-zinc-500', label: 'N/A' };
    }
  };
  
  const decisionInfo = getDecisionInfo();
  const regimeInfo = getRegimeInfo();
  const DecisionIcon = decisionInfo.icon;
  const RegimeIcon = regimeInfo.icon;
  
  const modeColor = mode === 'live' ? 'red' : 'yellow';
  const borderColor = mode === 'live' ? 'border-red-900/50' : 'border-yellow-900/50';
  const bgColor = mode === 'live' ? 'bg-red-950/20' : 'bg-yellow-950/20';
  
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD'
    }).format(value || 0);
  };
  
  return (
    <div className={`p-4 ${bgColor} border ${borderColor} rounded-lg`} data-testid={`${mode}-bot-status`}>
      <div className="flex items-center justify-between mb-4">
        <h4 className={`text-sm font-medium text-${modeColor}-500 flex items-center gap-2`}>
          {mode === 'live' ? <AlertTriangle className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
          Bot Status
        </h4>
        <Badge className={isRunning ? `bg-green-500/20 text-green-400` : 'bg-zinc-800 text-zinc-500'}>
          {isRunning ? 'RUNNING' : 'STOPPED'}
        </Badge>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Last Scan */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            Letzter Scan
          </div>
          <div className="text-sm font-mono text-zinc-300 mt-1">
            {lastScan ? (
              <span title={format(new Date(lastScan), 'PPpp', { locale: de })}>
                {formatDistanceToNow(new Date(lastScan), { locale: de, addSuffix: true })}
              </span>
            ) : (
              <span className="text-zinc-600">-</span>
            )}
          </div>
        </div>
        
        {/* Last Decision */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500">Letzte Entscheidung</div>
          <div className={`text-sm font-medium mt-1 flex items-center gap-1 ${decisionInfo.color}`}>
            <DecisionIcon className="w-3 h-3" />
            <span className="truncate" title={decisionInfo.label}>
              {decisionInfo.label.length > 20 ? decisionInfo.label.substring(0, 20) + '...' : decisionInfo.label}
            </span>
          </div>
        </div>
        
        {/* Regime */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500">Regime</div>
          <div className={`text-sm font-medium mt-1 flex items-center gap-1 ${regimeInfo.color}`}>
            <RegimeIcon className="w-3 h-3" />
            {regimeInfo.label}
          </div>
        </div>
        
        {/* Positions */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500">Positionen</div>
          <div className="text-sm font-mono text-zinc-300 mt-1">
            {positionsCount} / {settings?.max_positions || 3}
          </div>
        </div>
      </div>
      
      {/* Budget & Daily Cap Bar */}
      <div className="mt-3 grid grid-cols-2 gap-3">
        {/* Budget */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-zinc-500">Budget</span>
            <span className="text-zinc-400">
              {formatCurrency(budgetUsed)} / {formatCurrency(budgetUsed + budgetAvailable)}
            </span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full transition-all ${
                budgetAvailable <= 0 ? 'bg-red-500' : 
                budgetAvailable < 50 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${Math.min(100, (budgetUsed / (budgetUsed + budgetAvailable || 1)) * 100)}%` }}
            />
          </div>
          <div className="text-xs text-zinc-500 mt-1">
            {formatCurrency(budgetAvailable)} verfügbar
          </div>
        </div>
        
        {/* Daily Cap */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-zinc-500">Daily Cap</span>
            <span className="text-zinc-400">
              {formatCurrency(dailyUsed)} / {formatCurrency(dailyCap)}
            </span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full transition-all ${
                dailyRemaining <= 0 ? 'bg-red-500' : 
                (dailyUsed / dailyCap) > 0.7 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${Math.min(100, (dailyUsed / dailyCap) * 100)}%` }}
            />
          </div>
          <div className={`text-xs mt-1 ${dailyRemaining <= 0 ? 'text-red-400 font-medium' : 'text-zinc-500'}`}>
            {dailyRemaining <= 0 ? '⛔ Tageslimit erreicht!' : `${formatCurrency(dailyRemaining)} verfügbar`}
          </div>
        </div>
      </div>
      
      {/* Blocking Warnings */}
      {lastDecision?.startsWith('BLOCKED:') && (
        <div className="mt-3 p-2 bg-red-950/50 border border-red-900/50 rounded flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <span className="text-sm text-red-400">{lastDecision}</span>
        </div>
      )}
    </div>
  );
};

export default BotStatusPanel;
