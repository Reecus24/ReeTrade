import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Brain, Activity, TrendingUp, Zap, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

/**
 * RL-KI Status Panel - Zeigt den Lernstatus der KI an
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
    const interval = setInterval(fetchStatus, 10000); // Alle 10 Sekunden
    return () => clearInterval(interval);
  }, []);

  if (loading || !rlStatus) {
    return (
      <div className="p-4 bg-zinc-950 border border-purple-900/50 rounded-lg animate-pulse">
        <div className="h-20 bg-zinc-800 rounded"></div>
      </div>
    );
  }

  const explorationPct = rlStatus.exploration_pct || 100;
  const learningPct = 100 - explorationPct;
  const winRate = (rlStatus.win_rate || 0) * 100;

  return (
    <div className="p-4 bg-zinc-950 border border-purple-900/50 rounded-lg" data-testid="rl-status-panel">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Brain className="w-5 h-5 text-purple-400" />
          RL Trading KI
        </h3>
        <Badge className={rlStatus.is_learning ? 'bg-purple-500/20 text-purple-400' : 'bg-green-500/20 text-green-400'}>
          {rlStatus.is_learning ? '🧠 Lernt...' : '✅ Trainiert'}
        </Badge>
      </div>

      {/* Lernfortschritt */}
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-zinc-400">Lernfortschritt</span>
          <span className="text-purple-400">{learningPct.toFixed(0)}% gelernt</span>
        </div>
        <div className="w-full bg-zinc-800 rounded-full h-3">
          <div 
            className="bg-gradient-to-r from-purple-600 to-purple-400 h-3 rounded-full transition-all duration-500"
            style={{ width: `${learningPct}%` }}
          ></div>
        </div>
        <p className="text-xs text-zinc-500 mt-1">
          {explorationPct.toFixed(0)}% Exploration (probiert neue Strategien)
        </p>
      </div>

      {/* Statistiken */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-zinc-900 p-3 rounded-lg text-center">
          <p className="text-2xl font-bold text-white">{rlStatus.total_trades || 0}</p>
          <p className="text-xs text-zinc-500">Trades</p>
        </div>
        <div className="bg-zinc-900 p-3 rounded-lg text-center">
          <p className={`text-2xl font-bold ${winRate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
            {winRate.toFixed(1)}%
          </p>
          <p className="text-xs text-zinc-500">Win-Rate</p>
        </div>
        <div className="bg-zinc-900 p-3 rounded-lg text-center">
          <p className="text-2xl font-bold text-purple-400">{rlStatus.memory_size || 0}</p>
          <p className="text-xs text-zinc-500">Erfahrungen</p>
        </div>
      </div>

      {/* Aktive Trades */}
      {rlStatus.active_episodes && rlStatus.active_episodes.length > 0 && (
        <div className="bg-zinc-900/50 p-3 rounded-lg">
          <p className="text-sm text-zinc-400 mb-2">Aktive Positionen:</p>
          <div className="flex flex-wrap gap-2">
            {rlStatus.active_episodes.map(symbol => (
              <Badge key={symbol} className="bg-purple-900/30 text-purple-300">
                {symbol}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Erklärung */}
      <div className="mt-4 p-3 bg-purple-950/30 border border-purple-900/30 rounded-lg">
        <p className="text-xs text-purple-300">
          <strong>So lernt die KI:</strong> Sie analysiert Marktdaten, trifft Entscheidungen, 
          und lernt aus dem Ergebnis. Mit jedem Trade wird sie schlauer.
          {rlStatus.total_trades < 20 && (
            <span className="block mt-1 text-yellow-400">
              ⚠️ Noch in der Lernphase ({20 - rlStatus.total_trades} Trades bis zum ersten Training)
            </span>
          )}
        </p>
      </div>

      <Button 
        onClick={fetchStatus} 
        variant="ghost" 
        size="sm" 
        className="w-full mt-3 text-zinc-500"
        data-testid="refresh-rl-status"
      >
        <RefreshCw className="w-4 h-4 mr-2" />
        Aktualisieren
      </Button>
    </div>
  );
};


/**
 * Einfacher Trading Mode Selector - Nur RL-KI
 */
const TradingModeSelector = ({ currentMode, onModeChange, aiStatus }) => {
  const [rlEnabled, setRlEnabled] = useState(true);

  return (
    <div className="space-y-4">
      {/* RL-KI ist immer aktiv */}
      <div className="p-4 bg-gradient-to-r from-purple-950/50 to-zinc-950 border border-purple-800/50 rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-900/50 rounded-lg">
              <Brain className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h3 className="font-semibold text-white">Reinforcement Learning KI</h3>
              <p className="text-sm text-zinc-400">Lernt selbstständig aus jedem Trade</p>
            </div>
          </div>
          <Badge className="bg-green-500/20 text-green-400 text-sm px-3 py-1">
            AKTIV
          </Badge>
        </div>
      </div>

      {/* RL Status Panel */}
      <RLStatusPanel />
    </div>
  );
};

// Leere Komponenten für Kompatibilität
const AIStatusPanel = () => null;
const AIStatusPanelV2 = () => null;

export { TradingModeSelector, AIStatusPanel, AIStatusPanelV2, RLStatusPanel };
export default TradingModeSelector;
