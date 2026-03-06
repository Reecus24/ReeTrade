import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { 
  Activity, Play, Square, AlertTriangle, Settings, FileText,
  Wifi, WifiOff, RefreshCw, LogOut, Wallet, Brain, Zap,
  TrendingUp, Info, ChevronRight
} from 'lucide-react';
import { format } from 'date-fns';
import TradesTab from '@/components/TradesTab';
import SettingsTab from '@/components/SettingsTab';
import LogsTab from '@/components/LogsTab';
import LiveModeConfirm from '@/components/LiveModeConfirm';
import BotStatusPanel from '@/components/BotStatusPanel';
import PositionsPanel from '@/components/PositionsPanel';
import KILogTab from '@/components/KILogTab';
import InfoTab from '@/components/InfoTab';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

// ═══════════════════════════════════════════════════════════════════════════════
// CYBERPUNK RL TRADING STATS PANEL - KOMPLETT ÜBERARBEITET
// ═══════════════════════════════════════════════════════════════════════════════

const RLStatusPanel = () => {
  const [rlStatus, setRlStatus] = useState(null);
  const [tradingStats, setTradingStats] = useState(null);
  const [buyCooldown, setBuyCooldown] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statsHours, setStatsHours] = useState(24);

  const fetchStatus = async () => {
    try {
      const [statusRes, statsRes, cooldownRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/rl/status`, getAuthHeaders()),
        axios.get(`${BACKEND_URL}/api/rl/trading-stats?hours=${statsHours}`, getAuthHeaders()),
        axios.get(`${BACKEND_URL}/api/rl/buy-cooldown`, getAuthHeaders())
      ]);
      setRlStatus(statusRes.data);
      setTradingStats(statsRes.data);
      setBuyCooldown(cooldownRes.data);
    } catch (error) {
      console.error('RL Status error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000); // Auto-refresh alle 10 Sekunden
    return () => clearInterval(interval);
  }, [statsHours]);

  if (loading) {
    return (
      <div className="cyber-panel p-6 animate-pulse">
        <div className="h-32 bg-zinc-900/50"></div>
      </div>
    );
  }

  const explorationPct = rlStatus?.exploration_pct || 100;
  const learningPct = 100 - explorationPct;
  const totalTrades = rlStatus?.total_trades || 0;

  // Extrahiere Stats aus der neuen Struktur
  const stats = tradingStats || {};
  const holdStats = stats.hold_stats || {};
  const pnlStats = stats.pnl_stats || {};
  const feeStats = stats.fee_stats || {};
  const sellSources = stats.sell_sources || {};
  const tradeCounts = stats.trade_counts || {};
  const performance = stats.performance || {};
  const rlMetrics = stats.rl_metrics || {};
  const health = stats.health || {};

  // Health Status Farben
  const healthColors = {
    healthy: { bg: 'bg-green-500/20', border: 'border-green-500/50', text: 'text-green-400', glow: 'shadow-[0_0_10px_rgba(34,197,94,0.3)]' },
    warning: { bg: 'bg-yellow-500/20', border: 'border-yellow-500/50', text: 'text-yellow-400', glow: 'shadow-[0_0_10px_rgba(234,179,8,0.3)]' },
    critical: { bg: 'bg-red-500/20', border: 'border-red-500/50', text: 'text-red-400', glow: 'shadow-[0_0_10px_rgba(239,68,68,0.3)]' }
  };
  const healthStyle = healthColors[health.status] || healthColors.warning;

  return (
    <div className="cyber-panel p-6 box-glow-purple" data-testid="rl-status-panel">
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* HEADER MIT ZEITRAUM-AUSWAHL */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
            <Brain className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="font-cyber text-sm text-purple-400 tracking-widest uppercase">
              RL Trading Stats
            </h3>
            <p className="text-xs text-zinc-500 font-mono-cyber">REINFORCEMENT LEARNING AI</p>
          </div>
        </div>
        
        {/* Zeitraum Toggle */}
        <div className="flex gap-1 bg-black/50 border border-cyan-500/30 p-1">
          {[1, 6, 24].map(h => (
            <button
              key={h}
              onClick={() => setStatsHours(h)}
              data-testid={`stats-period-${h}h`}
              className={`px-3 py-1 text-xs font-mono-cyber transition-all ${
                statsHours === h 
                  ? 'bg-cyan-500/30 text-cyan-400 border border-cyan-500/50' 
                  : 'text-zinc-500 hover:text-cyan-400 hover:bg-cyan-500/10'
              }`}
            >
              {h}h
            </button>
          ))}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* HEALTH STATUS AMPEL */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className={`mb-4 p-3 border ${healthStyle.border} ${healthStyle.bg} ${healthStyle.glow}`} data-testid="health-status">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${health.status === 'healthy' ? 'bg-green-500' : health.status === 'warning' ? 'bg-yellow-500' : 'bg-red-500'} animate-pulse`} />
            <span className={`text-sm font-cyber uppercase tracking-wider ${healthStyle.text}`}>
              {health.status === 'healthy' ? 'HEALTHY' : health.status === 'warning' ? 'WARNING' : 'CRITICAL'}
            </span>
          </div>
          <span className="text-xs text-zinc-500 font-mono-cyber">{tradeCounts.total || 0} TRADES</span>
        </div>
        
        {/* Status Reasons */}
        {health.reasons && health.reasons.length > 0 && (
          <div className="space-y-1">
            {health.reasons.slice(0, 3).map((reason, idx) => (
              <p key={idx} className="text-xs text-zinc-400 font-mono-cyber pl-5">
                • {reason}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* BUY COOLDOWN STATUS */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {buyCooldown && (
        <div className={`mb-4 p-3 border ${buyCooldown.cooldown_active 
          ? 'border-orange-500/50 bg-orange-500/10' 
          : 'border-green-500/30 bg-green-500/5'}`}
          data-testid="buy-cooldown"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className={`w-4 h-4 ${buyCooldown.cooldown_active ? 'text-orange-400' : 'text-green-400'}`} />
              <span className="text-xs font-mono-cyber text-zinc-400">BUY COOLDOWN</span>
            </div>
            <span className={`text-sm font-cyber ${buyCooldown.cooldown_active ? 'text-orange-400' : 'text-green-400'}`}>
              {buyCooldown.cooldown_active ? buyCooldown.remaining_formatted : '✓ READY'}
            </span>
          </div>
          {buyCooldown.cooldown_active && (
            <div className="mt-2">
              <div className="h-1 bg-black/50 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-orange-500 transition-all duration-1000"
                  style={{ width: `${(1 - buyCooldown.remaining_seconds / buyCooldown.cooldown_seconds) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Learning Progress (kompakt) */}
      <div className="mb-4 p-3 bg-black/30 border border-purple-500/20">
        <div className="flex justify-between text-xs mb-2">
          <span className="text-zinc-500 font-mono-cyber">NEURAL TRAINING</span>
          <span className="text-cyan-400 font-mono-cyber">{learningPct.toFixed(0)}% TRAINED</span>
        </div>
        <div className="h-2 bg-black/50 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 transition-all"
            style={{ width: `${learningPct}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] mt-1 text-zinc-600">
          <span>EXPLORE: {explorationPct.toFixed(0)}%</span>
          <span>MEMORY: {rlStatus?.memory_size || 0}</span>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* 1. HOLD STATS */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className="mb-3 border border-cyan-500/20 bg-black/30" data-testid="hold-stats">
        <div className="p-2 border-b border-cyan-500/20">
          <span className="text-[10px] text-cyan-400 font-mono-cyber uppercase tracking-wider">HOLD DURATION</span>
        </div>
        <div className="grid grid-cols-3 gap-px bg-cyan-500/10">
          <div className="bg-black p-2 text-center">
            <p className="text-lg font-cyber text-white">{holdStats.avg_hold_formatted || '0m 0s'}</p>
            <p className="text-[9px] text-zinc-500">AVG HOLD</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-zinc-400">{holdStats.min_hold_formatted || '0m 0s'}</p>
            <p className="text-[9px] text-zinc-500">MIN</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-zinc-400">{holdStats.max_hold_formatted || '0m 0s'}</p>
            <p className="text-[9px] text-zinc-500">MAX</p>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* 2. NET PNL STATS - VERGLEICH THEORETICAL VS NET */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className="mb-3 border border-cyan-500/20 bg-black/30" data-testid="pnl-stats">
        <div className="p-2 border-b border-cyan-500/20">
          <span className="text-[10px] text-cyan-400 font-mono-cyber uppercase tracking-wider">NET PNL ANALYSIS</span>
        </div>
        
        {/* Avg PnL Vergleich */}
        <div className="grid grid-cols-2 gap-px bg-cyan-500/10">
          <div className="bg-black p-3">
            <p className="text-[10px] text-zinc-500 mb-1">AVG NET PnL</p>
            <p className={`text-xl font-cyber ${(pnlStats.avg_net_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {(pnlStats.avg_net_pnl_pct || 0) >= 0 ? '+' : ''}{(pnlStats.avg_net_pnl_pct || 0).toFixed(3)}%
            </p>
            <p className="text-[10px] text-zinc-600">${(pnlStats.avg_net_pnl_usdt || 0).toFixed(4)}</p>
          </div>
          <div className="bg-black p-3">
            <p className="text-[10px] text-zinc-500 mb-1">AVG THEORETICAL</p>
            <p className={`text-xl font-cyber ${(pnlStats.avg_theoretical_pnl_pct || 0) >= 0 ? 'text-blue-400' : 'text-orange-400'}`}>
              {(pnlStats.avg_theoretical_pnl_pct || 0) >= 0 ? '+' : ''}{(pnlStats.avg_theoretical_pnl_pct || 0).toFixed(3)}%
            </p>
            <p className="text-[10px] text-zinc-600">Gap: {(pnlStats.pnl_gap_pct || 0).toFixed(3)}%</p>
          </div>
        </div>
        
        {/* Total PnL */}
        <div className="grid grid-cols-2 gap-px bg-cyan-500/10 border-t border-cyan-500/20">
          <div className="bg-black p-2 text-center">
            <p className="text-[10px] text-zinc-500">TOTAL NET</p>
            <p className={`text-sm font-cyber ${(pnlStats.total_net_pnl_usdt || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${(pnlStats.total_net_pnl_usdt || 0).toFixed(4)}
            </p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-[10px] text-zinc-500">TOTAL THEORETICAL</p>
            <p className={`text-sm font-cyber ${(pnlStats.total_theoretical_pnl_pct || 0) >= 0 ? 'text-blue-400' : 'text-orange-400'}`}>
              {(pnlStats.total_theoretical_pnl_pct || 0).toFixed(3)}%
            </p>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* 3. FEES ANALYSIS */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className="mb-3 border border-yellow-500/20 bg-black/30" data-testid="fee-stats">
        <div className="p-2 border-b border-yellow-500/20">
          <span className="text-[10px] text-yellow-400 font-mono-cyber uppercase tracking-wider">FEES & COSTS</span>
        </div>
        <div className="grid grid-cols-3 gap-px bg-yellow-500/10">
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-yellow-400">${(feeStats.total_fees_paid || 0).toFixed(4)}</p>
            <p className="text-[9px] text-zinc-500">TOTAL FEES</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-orange-400">${(feeStats.total_slippage || 0).toFixed(4)}</p>
            <p className="text-[9px] text-zinc-500">SLIPPAGE</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className={`text-sm font-cyber ${(feeStats.fee_ratio_pct || 0) > 0.5 ? 'text-red-400' : 'text-green-400'}`}>
              {(feeStats.fee_ratio_pct || 0).toFixed(3)}%
            </p>
            <p className="text-[9px] text-zinc-500">FEE RATIO</p>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* 4. SELL SOURCE BREAKDOWN */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className="mb-3 border border-purple-500/20 bg-black/30" data-testid="sell-sources">
        <div className="p-2 border-b border-purple-500/20">
          <span className="text-[10px] text-purple-400 font-mono-cyber uppercase tracking-wider">SELL SOURCES</span>
        </div>
        <div className="p-3">
          {/* Visual Bars */}
          <div className="space-y-2">
            {/* Exploitation */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-zinc-500 w-16">EXPLOIT</span>
              <div className="flex-1 h-3 bg-black/50 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all"
                  style={{ width: `${sellSources.percentages?.exploitation || 0}%` }}
                />
              </div>
              <span className="text-xs font-cyber text-blue-400 w-12 text-right">
                {(sellSources.percentages?.exploitation || 0).toFixed(0)}%
              </span>
            </div>
            
            {/* Random Exploration */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-zinc-500 w-16">RANDOM</span>
              <div className="flex-1 h-3 bg-black/50 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-purple-500 transition-all"
                  style={{ width: `${sellSources.percentages?.random_exploration || 0}%` }}
                />
              </div>
              <span className="text-xs font-cyber text-purple-400 w-12 text-right">
                {(sellSources.percentages?.random_exploration || 0).toFixed(0)}%
              </span>
            </div>
            
            {/* Time Limit */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-zinc-500 w-16">TIME</span>
              <div className="flex-1 h-3 bg-black/50 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-yellow-500 transition-all"
                  style={{ width: `${sellSources.percentages?.time_limit || 0}%` }}
                />
              </div>
              <span className="text-xs font-cyber text-yellow-400 w-12 text-right">
                {(sellSources.percentages?.time_limit || 0).toFixed(0)}%
              </span>
            </div>
            
            {/* Emergency */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-zinc-500 w-16">EMERG</span>
              <div className="flex-1 h-3 bg-black/50 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-red-500 transition-all"
                  style={{ width: `${sellSources.percentages?.emergency || 0}%` }}
                />
              </div>
              <span className="text-xs font-cyber text-red-400 w-12 text-right">
                {(sellSources.percentages?.emergency || 0).toFixed(0)}%
              </span>
            </div>
          </div>
          
          {/* Counts */}
          <div className="grid grid-cols-4 gap-2 mt-3 pt-3 border-t border-purple-500/20 text-center">
            <div>
              <p className="text-xs font-cyber text-blue-400">{sellSources.counts?.exploitation || 0}</p>
              <p className="text-[8px] text-zinc-600">EXPLOIT</p>
            </div>
            <div>
              <p className="text-xs font-cyber text-purple-400">{sellSources.counts?.random_exploration || 0}</p>
              <p className="text-[8px] text-zinc-600">RANDOM</p>
            </div>
            <div>
              <p className="text-xs font-cyber text-yellow-400">{sellSources.counts?.time_limit || 0}</p>
              <p className="text-[8px] text-zinc-600">TIME</p>
            </div>
            <div>
              <p className="text-xs font-cyber text-red-400">{sellSources.counts?.emergency || 0}</p>
              <p className="text-[8px] text-zinc-600">EMERG</p>
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* 5. PERFORMANCE METRICS */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className="mb-3 border border-green-500/20 bg-black/30" data-testid="performance">
        <div className="p-2 border-b border-green-500/20">
          <span className="text-[10px] text-green-400 font-mono-cyber uppercase tracking-wider">PERFORMANCE</span>
        </div>
        
        {/* Win Rate & Trade Counts */}
        <div className="grid grid-cols-3 gap-px bg-green-500/10">
          <div className="bg-black p-2 text-center">
            <p className={`text-xl font-cyber ${(performance.win_rate_pct || 0) >= 50 ? 'text-green-400' : 'text-red-400'}`}>
              {(performance.win_rate_pct || 0).toFixed(1)}%
            </p>
            <p className="text-[9px] text-zinc-500">WIN RATE</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-lg font-cyber text-green-400">{tradeCounts.winning || 0}</p>
            <p className="text-[9px] text-zinc-500">WINNERS</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-lg font-cyber text-red-400">{tradeCounts.losing || 0}</p>
            <p className="text-[9px] text-zinc-500">LOSERS</p>
          </div>
        </div>
        
        {/* Avg Win/Loss */}
        <div className="grid grid-cols-3 gap-px bg-green-500/10 border-t border-green-500/20">
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-green-400">${(performance.avg_win_usdt || 0).toFixed(4)}</p>
            <p className="text-[9px] text-zinc-500">AVG WIN</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-red-400">${Math.abs(performance.avg_loss_usdt || 0).toFixed(4)}</p>
            <p className="text-[9px] text-zinc-500">AVG LOSS</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className={`text-sm font-cyber ${(performance.profit_factor || 0) >= 1 ? 'text-green-400' : 'text-red-400'}`}>
              {(performance.profit_factor || 0).toFixed(2)}
            </p>
            <p className="text-[9px] text-zinc-500">PROFIT FACTOR</p>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      {/* 6. RL-SPECIFIC METRICS */}
      {/* ═══════════════════════════════════════════════════════════════════════════ */}
      <div className="mb-3 border border-cyan-500/20 bg-black/30" data-testid="rl-metrics">
        <div className="p-2 border-b border-cyan-500/20">
          <span className="text-[10px] text-cyan-400 font-mono-cyber uppercase tracking-wider">RL METRICS</span>
        </div>
        <div className="grid grid-cols-2 gap-px bg-cyan-500/10">
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-cyan-400">{rlMetrics.avg_duration_winning_formatted || '0m 0s'}</p>
            <p className="text-[9px] text-zinc-500">AVG WIN DURATION</p>
          </div>
          <div className="bg-black p-2 text-center">
            <p className="text-sm font-cyber text-orange-400">{rlMetrics.avg_duration_losing_formatted || '0m 0s'}</p>
            <p className="text-[9px] text-zinc-500">AVG LOSS DURATION</p>
          </div>
        </div>
      </div>

      {/* Active Episodes */}
      {rlStatus?.active_episodes && rlStatus.active_episodes.length > 0 && (
        <div className="mb-3 p-3 bg-purple-500/5 border border-purple-500/20">
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

      {/* Info für Lernphase */}
      {totalTrades < 10 && (
        <div className="mb-3 p-3 border border-yellow-500/30 bg-yellow-500/5">
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
        className="w-full mt-2 text-zinc-600 hover:text-cyan-400 font-mono-cyber text-xs"
        data-testid="refresh-rl-status"
      >
        <RefreshCw className="w-3 h-3 mr-2" />
        REFRESH STATUS
      </Button>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

const DashboardPage = ({ onLogout }) => {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [liveLoading, setLiveLoading] = useState(false);
  const [showLiveConfirm, setShowLiveConfirm] = useState(false);
  const [balance, setBalance] = useState(null);
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [balanceError, setBalanceError] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/status`, getAuthHeaders());
      setStatus(response.data);
    } catch (error) {
      if (error.response?.status === 401) {
        onLogout();
      }
    }
  }, [onLogout]);

  const fetchLogs = useCallback(async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/logs?limit=100`, getAuthHeaders());
      setLogs(response.data.logs || []);
    } catch (error) {
      console.error('Logs fetch error:', error);
    }
  }, []);

  const fetchBalance = useCallback(async () => {
    if (!status?.settings?.live_confirmed) return;
    
    setBalanceLoading(true);
    setBalanceError(null);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/account/balance`, getAuthHeaders());
      setBalance(response.data);
    } catch (error) {
      setBalanceError(error.response?.data?.detail || 'Fehler beim Laden');
      setBalance(null);
    } finally {
      setBalanceLoading(false);
    }
  }, [status?.settings?.live_confirmed]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        await Promise.all([fetchStatus(), fetchLogs()]);
      } catch (error) {
        console.error('Init error:', error);
      } finally {
        setLoading(false);
      }
    };
    init();
    const interval = setInterval(() => {
      fetchStatus();
      fetchLogs();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchLogs]);

  useEffect(() => {
    if (status?.settings?.live_confirmed) {
      fetchBalance();
    }
  }, [status?.settings?.live_confirmed, fetchBalance]);

  const handleLiveStart = async () => {
    setLiveLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/live/start`, {}, getAuthHeaders());
      toast.success('NEURAL NETWORK AKTIVIERT');
      await fetchStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Systemfehler');
    } finally {
      setLiveLoading(false);
    }
  };

  const handleLiveStop = async () => {
    setLiveLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/live/stop`, {}, getAuthHeaders());
      toast.success('SYSTEM DEAKTIVIERT');
      await fetchStatus();
    } catch (error) {
      toast.error('Systemfehler');
    } finally {
      setLiveLoading(false);
    }
  };

  const handleLiveConfirmed = async () => {
    setShowLiveConfirm(false);
    await fetchStatus();
    await fetchBalance();
  };

  const handleRevokeLive = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/live/revoke`, {}, getAuthHeaders());
      toast.success('Zugang widerrufen');
      await fetchStatus();
    } catch (error) {
      toast.error('Fehler');
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(value || 0);
  };

  if (loading || !status) {
    return (
      <div className="min-h-screen bg-[#050508] flex items-center justify-center cyber-grid">
        <div className="text-center">
          <Activity className="w-12 h-12 text-cyan-400 animate-spin mx-auto mb-4" />
          <p className="font-cyber text-cyan-400 text-sm tracking-widest animate-pulse">
            INITIALIZING SYSTEM...
          </p>
        </div>
      </div>
    );
  }

  const { settings, live_account, mexc_keys_connected } = status;

  return (
    <div className="min-h-screen bg-[#050508] text-white cyber-grid">
      {/* Scanline Overlay */}
      <div className="fixed inset-0 pointer-events-none scanlines z-50 opacity-20" />
      
      <div className="relative z-10 p-6">
        <div className="max-w-7xl mx-auto">
          
          {/* ═══ HEADER ═══ */}
          <header className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 border border-cyan-500/50 flex items-center justify-center bg-cyan-500/10">
                <Zap className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <h1 className="font-cyber text-2xl text-white tracking-wider">
                  REE<span className="text-cyan-400 glow-cyan">TRADE</span>
                </h1>
                <p className="text-xs text-zinc-600 font-mono-cyber tracking-widest">
                  NEURAL TRADING TERMINAL v2.0
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              {/* Connection Status */}
              <div className={`flex items-center gap-2 px-4 py-2 border ${mexc_keys_connected ? 'border-green-500/50 bg-green-500/10' : 'border-red-500/30 bg-red-500/5'}`}>
                {mexc_keys_connected ? (
                  <>
                    <Wifi className="w-4 h-4 text-green-400" />
                    <span className="text-xs font-mono-cyber text-green-400">MEXC LINKED</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-mono-cyber text-red-400">OFFLINE</span>
                  </>
                )}
              </div>
              
              <Button 
                onClick={onLogout} 
                variant="ghost" 
                size="sm" 
                className="text-zinc-600 hover:text-red-400 font-mono-cyber text-xs"
              >
                <LogOut className="w-4 h-4 mr-2" />
                DISCONNECT
              </Button>
            </div>
          </header>

          {/* ═══ LIVE MODE WARNING ═══ */}
          {!settings.live_confirmed && (
            <div className="cyber-panel p-4 mb-6 border-yellow-500/30 box-glow-red">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <AlertTriangle className="w-8 h-8 text-yellow-400 animate-pulse" />
                  <div>
                    <p className="font-cyber text-yellow-400 text-sm tracking-wider">SYSTEM LOCKED</p>
                    <p className="text-xs text-zinc-500 font-mono-cyber">Aktiviere Live Mode um Trading zu starten</p>
                  </div>
                </div>
                <Button 
                  onClick={() => setShowLiveConfirm(true)} 
                  className="cyber-btn bg-yellow-500/10 border-yellow-500 text-yellow-400 hover:bg-yellow-500/20"
                >
                  AKTIVIEREN
                </Button>
              </div>
            </div>
          )}

          {/* ═══ MAIN CONTROL PANEL ═══ */}
          <div className={`cyber-panel p-6 mb-6 ${settings.live_running ? 'border-red-500/50 box-glow-red' : 'border-cyan-500/30'}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                {/* Status Indicator */}
                <div className={`w-16 h-16 border-2 flex items-center justify-center ${settings.live_running ? 'border-red-500 bg-red-500/10' : settings.live_confirmed ? 'border-green-500/50 bg-green-500/10' : 'border-zinc-700 bg-zinc-900'}`}>
                  <div className={`w-4 h-4 rounded-full ${settings.live_running ? 'bg-red-500 animate-pulse shadow-[0_0_20px_#ff0044]' : settings.live_confirmed ? 'bg-green-500' : 'bg-zinc-600'}`} />
                </div>
                
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="font-cyber text-xl tracking-wider">
                      {settings.live_running ? (
                        <span className="text-red-400 glitch-text">LIVE TRADING</span>
                      ) : settings.live_confirmed ? (
                        <span className="text-green-400">SYSTEM READY</span>
                      ) : (
                        <span className="text-zinc-500">OFFLINE</span>
                      )}
                    </h2>
                    <Badge className={`cyber-badge ${
                      settings.live_running 
                        ? 'bg-red-500/20 text-red-400 border border-red-500/50 animate-pulse' 
                        : settings.live_confirmed 
                          ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                          : 'bg-zinc-800 text-zinc-500 border border-zinc-700'
                    }`}>
                      {settings.live_running ? 'ACTIVE' : settings.live_confirmed ? 'STANDBY' : 'LOCKED'}
                    </Badge>
                  </div>
                  
                  {status.live_heartbeat && settings.live_running && (
                    <p className="text-xs text-zinc-600 font-mono-cyber mt-1">
                      LAST SIGNAL: {format(new Date(status.live_heartbeat), 'HH:mm:ss')}
                    </p>
                  )}
                </div>
              </div>

              {/* Control Buttons */}
              <div className="flex gap-3">
                {!settings.live_confirmed ? (
                  <Button 
                    onClick={() => setShowLiveConfirm(true)} 
                    className="cyber-btn"
                  >
                    <Zap className="w-4 h-4 mr-2" />
                    UNLOCK
                  </Button>
                ) : !settings.live_running ? (
                  <>
                    <Button 
                      onClick={handleLiveStart} 
                      disabled={liveLoading || !mexc_keys_connected} 
                      className="cyber-btn bg-green-500/10 border-green-500 text-green-400 hover:bg-green-500/20"
                    >
                      <Play className="w-4 h-4 mr-2" />
                      LAUNCH
                    </Button>
                    <Button 
                      onClick={handleRevokeLive} 
                      variant="ghost" 
                      className="text-zinc-600 hover:text-red-400 font-mono-cyber text-xs"
                    >
                      REVOKE
                    </Button>
                  </>
                ) : (
                  <Button 
                    onClick={handleLiveStop} 
                    disabled={liveLoading} 
                    className="cyber-btn bg-red-500/20 border-red-500 text-red-400 hover:bg-red-500/30"
                  >
                    <Square className="w-4 h-4 mr-2" />
                    TERMINATE
                  </Button>
                )}
              </div>
            </div>

            {/* Live Warning */}
            {settings.live_running && (
              <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30">
                <p className="text-center text-red-400 font-mono-cyber text-xs tracking-wider">
                  <AlertTriangle className="w-4 h-4 inline mr-2" />
                  WARNING: REAL FUNDS AT RISK - NEURAL NETWORK IS TRADING LIVE
                </p>
              </div>
            )}
          </div>

          {/* ═══ TWO COLUMN LAYOUT ═══ */}
          {settings.live_confirmed && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
              
              {/* LEFT: Portfolio Overview */}
              <div className="lg:col-span-2 cyber-panel p-6 box-glow-cyan">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Wallet className="w-5 h-5 text-cyan-400" />
                    <h3 className="font-cyber text-sm text-cyan-400 tracking-widest uppercase">Portfolio</h3>
                  </div>
                  <Button 
                    onClick={fetchBalance} 
                    disabled={balanceLoading}
                    variant="ghost" 
                    size="sm"
                    className="text-zinc-600 hover:text-cyan-400"
                  >
                    <RefreshCw className={`w-4 h-4 ${balanceLoading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                
                {balanceError ? (
                  <div className="p-4 border border-red-500/30 bg-red-500/5 text-red-400 text-sm font-mono-cyber">
                    ERROR: {balanceError}
                  </div>
                ) : balance ? (
                  <>
                    {/* Main Stats */}
                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className="bg-black/50 border border-cyan-500/20 p-4">
                        <p className="text-xs text-cyan-400 mb-1 font-mono-cyber">USDT FREE</p>
                        <p className="text-2xl font-cyber text-white">
                          {formatCurrency(balance.budget?.usdt_free || balance.cash || 0)}
                        </p>
                        <p className="text-xs text-zinc-600 mt-1 font-mono-cyber">AVAILABLE</p>
                      </div>
                      <div className="bg-black/50 border border-purple-500/20 p-4">
                        <p className="text-xs text-purple-400 mb-1 font-mono-cyber">INVESTED</p>
                        <p className="text-2xl font-cyber text-purple-400">
                          {formatCurrency(balance.invested_value || balance.budget?.used_budget || 0)}
                        </p>
                        <p className="text-xs text-zinc-600 mt-1 font-mono-cyber">
                          {(balance?.open_positions || live_account?.open_positions || []).length} POSITIONS
                        </p>
                      </div>
                      <div className="bg-black/50 border border-green-500/20 p-4">
                        <p className="text-xs text-green-400 mb-1 font-mono-cyber">TOTAL</p>
                        <p className="text-2xl font-cyber text-white">
                          {formatCurrency(
                            (balance.budget?.usdt_free || balance.cash || 0) + 
                            (balance.invested_value || balance.budget?.used_budget || 0)
                          )}
                        </p>
                        <p className={`text-xs mt-1 font-mono-cyber ${(balance.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          PNL: {(balance.total_pnl || 0) >= 0 ? '+' : ''}{formatCurrency(balance.total_pnl || 0)}
                        </p>
                      </div>
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-3 gap-3 mb-6">
                      <div className="p-3 border border-zinc-800 text-center">
                        <p className="text-xs text-zinc-600 font-mono-cyber">POSITIONS</p>
                        <p className="text-lg font-cyber text-white">
                          {(balance?.open_positions || live_account?.open_positions || []).length} / {balance.ai_max_positions || settings.max_positions}
                        </p>
                      </div>
                      <div className="p-3 border border-zinc-800 text-center">
                        <p className="text-xs text-zinc-600 font-mono-cyber">AI RANGE</p>
                        <p className="text-sm font-mono-cyber text-purple-400">
                          {balance?.ai_position_range ? (
                            `${formatCurrency(balance.ai_position_range.min)} - ${formatCurrency(balance.ai_position_range.max)}`
                          ) : (
                            formatCurrency(settings.live_max_order_usdt)
                          )}
                        </p>
                      </div>
                      <div className="p-3 border border-zinc-800 text-center">
                        <p className="text-xs text-zinc-600 font-mono-cyber">MODE</p>
                        <p className="text-sm font-cyber text-cyan-400">
                          RL-AI ACTIVE
                        </p>
                      </div>
                    </div>

                    {/* ═══════════════════════════════════════════════════════════════════════════ */}
                    {/* POSITIONS PANEL - Das existierende gute System */}
                    {/* ═══════════════════════════════════════════════════════════════════════════ */}
                    <div className="border-t border-cyan-500/20 pt-4 mt-4">
                      <PositionsPanel 
                        positions={balance?.open_positions || live_account?.open_positions || []}
                        mode="live"
                        onSellComplete={fetchBalance}
                      />
                    </div>
                  </>
                ) : (
                  <div className="text-center py-8">
                    <Activity className="w-8 h-8 mx-auto text-cyan-400 animate-spin mb-3" />
                    <p className="text-zinc-600 font-mono-cyber text-sm">LOADING DATA...</p>
                  </div>
                )}
              </div>

              {/* RIGHT: RL Status Panel */}
              <div className="lg:col-span-1">
                <RLStatusPanel />
              </div>
            </div>
          )}

          {/* Not Activated State */}
          {!settings.live_confirmed && (
            <div className="cyber-panel p-12 text-center mb-6">
              <AlertTriangle className="w-16 h-16 mx-auto mb-6 text-yellow-400 opacity-50" />
              <h3 className="font-cyber text-xl text-zinc-500 mb-2">SYSTEM LOCKED</h3>
              <p className="text-zinc-600 font-mono-cyber text-sm mb-6">
                Aktiviere Live Mode um Portfolio und Trading zu starten
              </p>
              {!mexc_keys_connected && (
                <div className="p-4 border border-red-500/30 bg-red-500/5 max-w-md mx-auto">
                  <p className="text-red-400 font-mono-cyber text-sm">
                    <AlertTriangle className="w-4 h-4 inline mr-2" />
                    MEXC API KEYS REQUIRED
                  </p>
                  <p className="text-zinc-600 text-xs mt-2">
                    Gehe zu <span className="text-cyan-400">SETTINGS</span> und gib deine MEXC API Keys ein
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Bot Status Panel */}
          {settings.live_confirmed && (
            <BotStatusPanel 
              settings={settings} 
              mode="live" 
              balance={balance} 
              actualPositionsCount={(balance?.open_positions || live_account?.open_positions || []).length}
            />
          )}

          {/* Positions Panel */}
          {settings.live_confirmed && (
            <PositionsPanel 
              positions={live_account?.open_positions || []} 
              mode="live"
              onSellComplete={() => { fetchStatus(); fetchBalance(); }}
            />
          )}

          {/* ═══ TABS ═══ */}
          <Tabs defaultValue="info" className="w-full mt-6">
            <TabsList className="bg-transparent border-b border-cyan-500/20 rounded-none p-0 h-auto gap-0">
              <TabsTrigger 
                value="settings" 
                className="cyber-tab data-[state=active]:cyber-tab-active px-6 py-3 rounded-none"
              >
                <Settings className="w-4 h-4 mr-2" />
                SETTINGS
              </TabsTrigger>
              {settings.live_confirmed && (
                <>
                  <TabsTrigger 
                    value="spot" 
                    className="cyber-tab data-[state=active]:cyber-tab-active data-[state=active]:text-green-400 data-[state=active]:border-green-400 px-6 py-3 rounded-none"
                  >
                    <TrendingUp className="w-4 h-4 mr-2" />
                    SPOT
                  </TabsTrigger>
                  <TabsTrigger 
                    value="ki" 
                    className="cyber-tab data-[state=active]:cyber-tab-active data-[state=active]:text-purple-400 data-[state=active]:border-purple-400 px-6 py-3 rounded-none"
                  >
                    <Brain className="w-4 h-4 mr-2" />
                    AI LOG
                  </TabsTrigger>
                  <TabsTrigger 
                    value="logs" 
                    className="cyber-tab data-[state=active]:cyber-tab-active data-[state=active]:text-red-400 data-[state=active]:border-red-400 px-6 py-3 rounded-none"
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    SYSTEM
                  </TabsTrigger>
                </>
              )}
              <TabsTrigger 
                value="info" 
                className="cyber-tab data-[state=active]:cyber-tab-active px-6 py-3 rounded-none"
              >
                <Info className="w-4 h-4 mr-2" />
                INFO
              </TabsTrigger>
            </TabsList>
            
            <div className="mt-6">
              <TabsContent value="settings"><SettingsTab /></TabsContent>
              {settings.live_confirmed && (
                <>
                  <TabsContent value="spot">
                    <TradesTab marketType="spot" />
                  </TabsContent>
                  <TabsContent value="ki"><KILogTab /></TabsContent>
                  <TabsContent value="logs">
                    <LogsTab logs={logs.filter(l => l.msg?.includes('[LIVE]') || l.msg?.includes('[RL]'))} />
                  </TabsContent>
                </>
              )}
              <TabsContent value="info"><InfoTab /></TabsContent>
            </div>
          </Tabs>

          {/* Live Mode Confirmation Dialog */}
          <LiveModeConfirm 
            open={showLiveConfirm} 
            onClose={() => setShowLiveConfirm(false)} 
            onConfirm={handleLiveConfirmed}
          />
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
