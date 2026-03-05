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
// CYBERPUNK RL STATUS PANEL
// ═══════════════════════════════════════════════════════════════════════════════

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

  if (loading) {
    return (
      <div className="cyber-panel p-6 animate-pulse">
        <div className="h-32 bg-zinc-900/50"></div>
      </div>
    );
  }

  const explorationPct = rlStatus?.exploration_pct || 100;
  const learningPct = 100 - explorationPct;
  const winRate = (rlStatus?.win_rate || 0) * 100;
  const totalTrades = rlStatus?.total_trades || 0;

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
            <p className="text-xs text-zinc-500 font-mono-cyber">REINFORCEMENT LEARNING AI</p>
          </div>
        </div>
        <Badge className={`cyber-badge ${rlStatus?.is_learning ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50' : 'bg-green-500/20 text-green-400 border border-green-500/50'}`}>
          {rlStatus?.is_learning ? 'LEARNING' : 'TRAINED'}
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
          <p className="text-2xl font-cyber text-purple-400">{rlStatus?.memory_size || 0}</p>
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider">MEMORY</p>
        </div>
      </div>

      {/* Active Episodes */}
      {rlStatus?.active_episodes && rlStatus.active_episodes.length > 0 && (
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

      {/* Info */}
      {totalTrades < 20 && (
        <div className="mt-4 p-3 border border-yellow-500/30 bg-yellow-500/5">
          <p className="text-xs text-yellow-400 font-mono-cyber">
            <Zap className="w-3 h-3 inline mr-1" />
            BOOT PHASE: {20 - totalTrades} Trades bis Neural Training aktiviert
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
                          {balance.open_positions_count || 0} POSITIONS
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
                    <div className="grid grid-cols-3 gap-3">
                      <div className="p-3 border border-zinc-800 text-center">
                        <p className="text-xs text-zinc-600 font-mono-cyber">POSITIONS</p>
                        <p className="text-lg font-cyber text-white">
                          {balance.open_positions_count || 0} / {balance.ai_max_positions || settings.max_positions}
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
            <BotStatusPanel settings={settings} mode="live" balance={balance} />
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
