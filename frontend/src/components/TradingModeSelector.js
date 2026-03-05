import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Brain, RefreshCw, Zap, TrendingUp, Activity } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

/**
 * RL-KI Status Panel - Zeigt den Lernstatus der KI an (Cyberpunk Style)
 */
const RLStatusPanel = () => {
  const [rlStatus, setRlStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/rl/status`, getAuthHeaders());
      setRlStatus(response.data);
    } catch (error) {
      console.error('RL Status error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !rlStatus) {
    return (
      <div className="cyber-panel p-6 animate-pulse">
        <div className="h-32 bg-zinc-900/50"></div>
      </div>
    );
  }

  const explorationPct = rlStatus.exploration_pct || 100;
  const learningPct = 100 - explorationPct;
  const winRate = (rlStatus.win_rate || 0) * 100;
  const totalTrades = rlStatus.total_trades || 0;

  return (
    <div className="cyber-panel p-6 box-glow-purple" data-testid="rl-status-panel">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
            <Brain className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="font-cyber text-sm text-purple-400 tracking-widest uppercase">
              Neural Network
            </h3>
            <p className="text-xs text-zinc-500 font-mono-cyber">RL TRADING AI</p>
          </div>
        </div>
        <Badge className={`cyber-badge ${rlStatus.is_learning ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50' : 'bg-green-500/20 text-green-400 border border-green-500/50'}`}>
          {rlStatus.is_learning ? 'LEARNING' : 'TRAINED'}
        </Badge>
      </div>

      {/* Learning Progress */}
      <div className="mb-6">
        <div className="flex justify-between text-xs mb-2">
          <span className="text-zinc-500 font-mono-cyber">NEURAL TRAINING</span>
          <span className="text-cyan-400 font-mono-cyber">{learningPct.toFixed(0)}%</span>
        </div>
        <div className="cyber-progress">
          <div 
            className="cyber-progress-bar"
            style={{ width: `${learningPct}%` }}
          />
        </div>
        <div className="flex justify-between text-xs mt-2 text-zinc-600">
          <span>EXPLORATION: {explorationPct.toFixed(0)}%</span>
          <span>EXPLOITATION: {learningPct.toFixed(0)}%</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
          <p className="text-2xl font-cyber text-white">{totalTrades}</p>
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider">TRADES</p>
        </div>
        <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
          <p className={`text-2xl font-cyber ${winRate >= 50 ? 'text-green-400 glow-green' : 'text-red-400'}`}>
            {winRate.toFixed(1)}%
          </p>
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider">WIN RATE</p>
        </div>
        <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
          <p className="text-2xl font-cyber text-purple-400">{rlStatus.memory_size || 0}</p>
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider">MEMORY</p>
        </div>
      </div>

      {/* Active Episodes */}
      {rlStatus.active_episodes && rlStatus.active_episodes.length > 0 && (
        <div className="mt-4 p-3 bg-purple-500/5 border border-purple-500/20">
          <p className="text-xs text-purple-400 mb-2 font-mono-cyber">ACTIVE POSITIONS:</p>
          <div className="flex flex-wrap gap-2">
            {rlStatus.active_episodes.map(symbol => (
              <span key={symbol} className="px-2 py-1 bg-purple-500/20 text-purple-300 text-xs font-mono">
                {symbol}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Boot Phase Warning */}
      {totalTrades < 10 && (
        <div className="mt-4 p-3 border border-yellow-500/30 bg-yellow-500/5">
          <p className="text-sm text-yellow-400 font-mono-cyber">
            <Zap className="w-3 h-3 inline mr-1" />
            LERNPHASE: Noch {10 - totalTrades} Trades - KI sammelt Erfahrung
          </p>
        </div>
      )}

      <Button 
        onClick={fetchStatus} 
        variant="ghost" 
        size="sm" 
        className="w-full mt-4 text-zinc-600 hover:text-cyan-400 font-mono-cyber text-xs"
        data-testid="refresh-rl-status"
      >
        <RefreshCw className="w-3 h-3 mr-2" />
        REFRESH STATUS
      </Button>
    </div>
  );
};


/**
 * Einfacher Trading Mode Selector - Nur RL-KI aktiv, alte Modi deaktiviert
 */
const TradingModeSelector = ({ currentMode, onModeChange, aiStatus }) => {
  return (
    <div className="space-y-4">
      {/* RL-KI ist immer aktiv */}
      <div className="cyber-panel p-4 box-glow-purple">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
              <Brain className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-white tracking-wider">Reinforcement Learning KI</h3>
              <p className="text-xs text-zinc-500 font-mono-cyber">Lernt selbstständig aus jedem Trade</p>
            </div>
          </div>
          <Badge className="cyber-badge bg-green-500/20 text-green-400 border border-green-500/50">
            AKTIV
          </Badge>
        </div>
      </div>

      {/* RL Status Panel */}
      <RLStatusPanel />

      {/* Info about disabled modes */}
      <div className="p-3 border border-zinc-800 bg-zinc-900/30">
        <p className="text-xs text-zinc-600 font-mono-cyber">
          <Activity className="w-3 h-3 inline mr-1" />
          Alte KI-Modi (KI Explorer, KI Hyper) wurden deaktiviert. 
          Die neue RL-KI lernt durch echte Trades und verbessert sich kontinuierlich.
        </p>
      </div>
    </div>
  );
};

// Legacy exports for compatibility
const AIStatusPanel = () => null;
const AIStatusPanelV2 = () => null;

export { TradingModeSelector, AIStatusPanel, AIStatusPanelV2, RLStatusPanel };
export default TradingModeSelector;
