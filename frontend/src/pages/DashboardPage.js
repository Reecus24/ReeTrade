import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { 
  Activity, Play, Square, AlertTriangle, Settings, FileText, History,
  TrendingUp, Wifi, WifiOff, Shield, RefreshCw, LogOut, Wallet, Lock, DollarSign, Clock
} from 'lucide-react';
import { format } from 'date-fns';
import TradesTab from '@/components/TradesTab';
import SettingsTab from '@/components/SettingsTab';
import LogsTab from '@/components/LogsTab';
import LiveModeConfirm from '@/components/LiveModeConfirm';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

const DashboardPage = ({ onLogout }) => {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeMainTab, setActiveMainTab] = useState('paper');
  const [paperLoading, setPaperLoading] = useState(false);
  const [liveLoading, setLiveLoading] = useState(false);
  const [showLiveConfirm, setShowLiveConfirm] = useState(false);
  const [liveBalance, setLiveBalance] = useState(null);
  const [liveBalanceLoading, setLiveBalanceLoading] = useState(false);
  const [liveBalanceError, setLiveBalanceError] = useState(null);
  const [paperBalance, setPaperBalance] = useState(null);
  const [paperBalanceLoading, setPaperBalanceLoading] = useState(false);

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

  const fetchLiveBalance = useCallback(async () => {
    if (!status?.settings?.live_confirmed) return;
    
    setLiveBalanceLoading(true);
    setLiveBalanceError(null);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/account/balance?mode=live`, getAuthHeaders());
      setLiveBalance(response.data);
    } catch (error) {
      setLiveBalanceError(error.response?.data?.detail || 'Fehler beim Laden');
      setLiveBalance(null);
    } finally {
      setLiveBalanceLoading(false);
    }
  }, [status?.settings?.live_confirmed]);

  const fetchPaperBalance = useCallback(async () => {
    setPaperBalanceLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/account/balance?mode=paper`, getAuthHeaders());
      setPaperBalance(response.data);
    } catch (error) {
      console.error('Paper balance fetch error:', error);
    } finally {
      setPaperBalanceLoading(false);
    }
  }, []);

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

  // Fetch paper balance on paper tab (only when logged in and status loaded)
  useEffect(() => {
    if (activeMainTab === 'paper' && status) {
      fetchPaperBalance();
    }
  }, [activeMainTab, fetchPaperBalance, status]);

  // Fetch live balance when tab changes or live is confirmed
  useEffect(() => {
    if (activeMainTab === 'live' && status?.settings?.live_confirmed) {
      fetchLiveBalance();
    }
  }, [activeMainTab, status?.settings?.live_confirmed, fetchLiveBalance]);

  // Paper controls
  const handlePaperStart = async () => {
    setPaperLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/paper/start`, {}, getAuthHeaders());
      toast.success('Paper Bot gestartet');
      await fetchStatus();
    } catch (error) {
      toast.error('Fehler beim Starten');
    } finally {
      setPaperLoading(false);
    }
  };

  const handlePaperStop = async () => {
    setPaperLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/paper/stop`, {}, getAuthHeaders());
      toast.success('Paper Bot gestoppt');
      await fetchStatus();
    } catch (error) {
      toast.error('Fehler beim Stoppen');
    } finally {
      setPaperLoading(false);
    }
  };

  // Live controls
  const handleLiveStart = async () => {
    setLiveLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/live/start`, {}, getAuthHeaders());
      toast.success('Live Bot gestartet - ECHTES TRADING AKTIV!');
      await fetchStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Starten');
    } finally {
      setLiveLoading(false);
    }
  };

  const handleLiveStop = async () => {
    setLiveLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/live/stop`, {}, getAuthHeaders());
      toast.success('Live Bot gestoppt');
      await fetchStatus();
    } catch (error) {
      toast.error('Fehler beim Stoppen');
    } finally {
      setLiveLoading(false);
    }
  };

  const handleLiveConfirmed = async () => {
    setShowLiveConfirm(false);
    await fetchStatus();
  };

  const handleRevokeLive = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/live/revoke`, {}, getAuthHeaders());
      toast.success('Live Mode widerrufen');
      await fetchStatus();
    } catch (error) {
      toast.error('Fehler');
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD'
    }).format(value || 0);
  };

  if (loading || !status) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <Activity className="w-8 h-8 text-zinc-600 animate-spin" />
      </div>
    );
  }

  const { settings, paper_account, mexc_keys_connected } = status;

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">ReeTrade Terminal</h1>
            <p className="text-zinc-500">Trading Bot Dashboard</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 rounded-lg">
              {mexc_keys_connected ? (
                <><Wifi className="w-4 h-4 text-green-500" /><span className="text-sm text-green-500">MEXC Connected</span></>
              ) : (
                <><WifiOff className="w-4 h-4 text-zinc-500" /><span className="text-sm text-zinc-500">Keys nicht konfiguriert</span></>
              )}
            </div>
            <Button onClick={onLogout} variant="ghost" size="sm" className="text-zinc-400">
              <LogOut className="w-4 h-4 mr-2" />Logout
            </Button>
          </div>
        </div>

        {/* Main Mode Tabs */}
        <Tabs value={activeMainTab} onValueChange={setActiveMainTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 bg-zinc-950 border border-zinc-800 h-14 mb-6">
            <TabsTrigger 
              value="paper" 
              className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500 data-[state=active]:border-yellow-500/30 h-12 text-lg"
              data-testid="main-tab-paper"
            >
              <Shield className="w-5 h-5 mr-2" />
              PAPER
              {settings.paper_running && (
                <Badge className="ml-2 bg-green-500/20 text-green-500 border-0">RUNNING</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger 
              value="live" 
              className="data-[state=active]:bg-red-500/10 data-[state=active]:text-red-500 data-[state=active]:border-red-500/30 h-12 text-lg"
              data-testid="main-tab-live"
            >
              <AlertTriangle className="w-5 h-5 mr-2" />
              LIVE
              {settings.live_running && (
                <Badge className="ml-2 bg-red-500/20 text-red-500 border-0 animate-pulse">RUNNING</Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* PAPER MODE TAB */}
          <TabsContent value="paper" className="mt-0">
            <div className="space-y-6">
              {/* Paper Status Bar */}
              <div className="p-4 bg-zinc-950 border border-yellow-900/30 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Shield className="w-5 h-5 text-yellow-500" />
                      <span className="text-lg font-semibold text-yellow-500">Paper Trading</span>
                    </div>
                    <Badge className={settings.paper_running 
                      ? 'bg-green-500/10 text-green-500 border-green-500/20' 
                      : 'bg-zinc-800 text-zinc-400'
                    }>
                      {settings.paper_running ? 'RUNNING' : 'STOPPED'}
                    </Badge>
                    {status.paper_heartbeat && settings.paper_running && (
                      <span className="text-xs text-zinc-500 font-mono">
                        Last: {format(new Date(status.paper_heartbeat), 'HH:mm:ss')}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {!settings.paper_running ? (
                      <Button onClick={handlePaperStart} disabled={paperLoading} className="bg-yellow-600 hover:bg-yellow-700 text-black font-medium">
                        <Play className="w-4 h-4 mr-2" />Start Paper
                      </Button>
                    ) : (
                      <Button onClick={handlePaperStop} disabled={paperLoading} variant="outline" className="border-yellow-900 text-yellow-500">
                        <Square className="w-4 h-4 mr-2" />Stop
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Paper Metrics */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
                  <div className="text-xs text-zinc-500 uppercase mb-2">Paper Equity</div>
                  <div className="text-2xl font-bold font-mono">{formatCurrency(paper_account?.equity || settings.paper_start_balance_usdt)}</div>
                </div>
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
                  <div className="text-xs text-zinc-500 uppercase mb-2">Paper Cash</div>
                  <div className="text-2xl font-bold font-mono">{formatCurrency(paper_account?.cash || settings.paper_start_balance_usdt)}</div>
                </div>
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
                  <div className="text-xs text-zinc-500 uppercase mb-2">Paper PnL</div>
                  <div className={`text-2xl font-bold font-mono ${(paper_account?.equity - settings.paper_start_balance_usdt) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {formatCurrency((paper_account?.equity || settings.paper_start_balance_usdt) - settings.paper_start_balance_usdt)}
                  </div>
                </div>
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
                  <div className="text-xs text-zinc-500 uppercase mb-2">Positionen</div>
                  <div className="text-2xl font-bold font-mono">{paper_account?.open_positions?.length || 0} / {settings.max_positions}</div>
                </div>
              </div>

              {/* Paper Daily Cap Progress */}
              {paperBalance?.daily_cap && (
                <div className="p-4 bg-zinc-950 border border-yellow-900/30 rounded-lg" data-testid="paper-daily-cap">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-yellow-500" />
                      <span className="text-sm font-medium text-yellow-500">Daily Trading Cap</span>
                    </div>
                    <div className="text-xs text-zinc-500">
                      Reset: 00:00 UTC
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">
                        Heute gehandelt: <span className="font-mono text-white">{formatCurrency(paperBalance.daily_cap.used)}</span>
                      </span>
                      <span className="text-zinc-400">
                        Limit: <span className="font-mono text-white">{formatCurrency(paperBalance.daily_cap.cap)}</span>
                      </span>
                    </div>
                    <div className="relative h-3 bg-zinc-800 rounded-full overflow-hidden">
                      <div 
                        className={`absolute left-0 top-0 h-full rounded-full transition-all duration-500 ${
                          (paperBalance.daily_cap.used / paperBalance.daily_cap.cap) >= 0.9 
                            ? 'bg-red-500' 
                            : (paperBalance.daily_cap.used / paperBalance.daily_cap.cap) >= 0.7 
                              ? 'bg-yellow-500' 
                              : 'bg-green-500'
                        }`}
                        style={{ width: `${Math.min(100, (paperBalance.daily_cap.used / paperBalance.daily_cap.cap) * 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className={`font-medium ${
                        paperBalance.daily_cap.remaining <= 0 ? 'text-red-400' : 'text-green-400'
                      }`}>
                        {paperBalance.daily_cap.remaining <= 0 
                          ? 'Tageslimit erreicht!' 
                          : `${formatCurrency(paperBalance.daily_cap.remaining)} verfügbar`
                        }
                      </span>
                      <span className="text-zinc-500">
                        {Math.round((paperBalance.daily_cap.used / paperBalance.daily_cap.cap) * 100)}% genutzt
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Paper Sub-Tabs */}
              <Tabs defaultValue="trades" className="w-full">
                <TabsList className="bg-zinc-950 border border-zinc-800">
                  <TabsTrigger value="trades"><History className="w-4 h-4 mr-2" />Trades</TabsTrigger>
                  <TabsTrigger value="logs"><FileText className="w-4 h-4 mr-2" />Logs</TabsTrigger>
                  <TabsTrigger value="settings"><Settings className="w-4 h-4 mr-2" />Settings</TabsTrigger>
                </TabsList>
                <div className="mt-4">
                  <TabsContent value="trades"><TradesTab currentMode="paper" /></TabsContent>
                  <TabsContent value="logs"><LogsTab logs={logs.filter(l => l.msg?.includes('[PAPER]') || !l.msg?.includes('[LIVE]'))} /></TabsContent>
                  <TabsContent value="settings"><SettingsTab /></TabsContent>
                </div>
              </Tabs>
            </div>
          </TabsContent>

          {/* LIVE MODE TAB */}
          <TabsContent value="live" className="mt-0">
            <div className="space-y-6">
              {/* Live Warning Banner */}
              {!settings.live_confirmed && (
                <div className="p-4 bg-red-950/30 border border-red-900 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="w-6 h-6 text-red-500" />
                      <div>
                        <div className="font-semibold text-red-500">Live Trading nicht aktiviert</div>
                        <div className="text-sm text-red-400">Bestätige Live Mode mit deinem Passwort um echtes Trading zu ermöglichen.</div>
                      </div>
                    </div>
                    <Button onClick={() => setShowLiveConfirm(true)} className="bg-red-600 hover:bg-red-700 text-white">
                      Live Mode aktivieren
                    </Button>
                  </div>
                </div>
              )}

              {/* Live Status Bar */}
              <div className={`p-4 rounded-lg ${settings.live_running ? 'bg-red-950/50 border-2 border-red-500 animate-pulse' : 'bg-zinc-950 border border-red-900/30'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className={`w-5 h-5 ${settings.live_running ? 'text-red-500 animate-bounce' : 'text-red-500'}`} />
                      <span className="text-lg font-semibold text-red-500">Live Trading</span>
                    </div>
                    <Badge className={settings.live_running 
                      ? 'bg-red-500 text-white border-0 animate-pulse' 
                      : settings.live_confirmed 
                        ? 'bg-green-500/10 text-green-500 border-green-500/20'
                        : 'bg-zinc-800 text-zinc-400'
                    }>
                      {settings.live_running ? 'ACTIVE - ECHTES GELD!' : settings.live_confirmed ? 'BEREIT' : 'NICHT AKTIVIERT'}
                    </Badge>
                    {status.live_heartbeat && settings.live_running && (
                      <span className="text-xs text-red-400 font-mono">
                        Last: {format(new Date(status.live_heartbeat), 'HH:mm:ss')}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {!settings.live_confirmed ? (
                      <Button onClick={() => setShowLiveConfirm(true)} className="bg-red-600 hover:bg-red-700">
                        <AlertTriangle className="w-4 h-4 mr-2" />Aktivieren
                      </Button>
                    ) : !settings.live_running ? (
                      <>
                        <Button onClick={handleLiveStart} disabled={liveLoading || !mexc_keys_connected} className="bg-red-600 hover:bg-red-700">
                          <Play className="w-4 h-4 mr-2" />Start Live
                        </Button>
                        <Button onClick={handleRevokeLive} variant="ghost" className="text-zinc-400">
                          Widerrufen
                        </Button>
                      </>
                    ) : (
                      <Button onClick={handleLiveStop} disabled={liveLoading} className="bg-white text-red-600 hover:bg-gray-200 font-bold">
                        <Square className="w-4 h-4 mr-2" />STOP LIVE
                      </Button>
                    )}
                  </div>
                </div>
                {settings.live_running && (
                  <div className="mt-3 p-2 bg-red-900/30 rounded text-center text-red-300 text-sm font-medium">
                    ⚠️ ACHTUNG: Echtes Geld wird gehandelt! Verluste sind real!
                  </div>
                )}
              </div>

              {/* Live Metrics - MEXC Wallet + Budget System */}
              {settings.live_confirmed ? (
                <div className="space-y-4">
                  {/* MEXC Spot Wallet (Read-Only) */}
                  <div className="bg-zinc-950 border border-green-900/30 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold flex items-center gap-2">
                        <Wallet className="w-5 h-5 text-green-500" />
                        MEXC Spot Wallet
                        <Badge className="bg-green-500/10 text-green-500 text-xs">READ-ONLY</Badge>
                      </h3>
                      <Button 
                        onClick={fetchLiveBalance} 
                        disabled={liveBalanceLoading}
                        variant="ghost" 
                        size="sm"
                        className="text-zinc-400"
                      >
                        <RefreshCw className={`w-4 h-4 ${liveBalanceLoading ? 'animate-spin' : ''}`} />
                      </Button>
                    </div>
                    
                    {liveBalanceError ? (
                      <div className="p-4 bg-red-950/30 border border-red-900 rounded text-red-400 text-sm">
                        {liveBalanceError}
                      </div>
                    ) : liveBalance ? (
                      <div className="grid grid-cols-4 gap-4">
                        <div className="p-3 bg-zinc-900 rounded-lg">
                          <div className="text-xs text-zinc-500 mb-1">USDT Free</div>
                          <div className="text-xl font-bold font-mono text-green-500">
                            {formatCurrency(liveBalance.budget?.usdt_free || liveBalance.cash || 0)}
                          </div>
                          <div className="text-xs text-zinc-600">Verfügbar zum Handeln</div>
                        </div>
                        <div className="p-3 bg-zinc-900 rounded-lg">
                          <div className="text-xs text-zinc-500 mb-1">USDT Locked</div>
                          <div className="text-xl font-bold font-mono text-orange-500">
                            {formatCurrency(liveBalance.locked || 0)}
                          </div>
                          <div className="text-xs text-zinc-600">In offenen Orders</div>
                        </div>
                        <div className="p-3 bg-zinc-900 rounded-lg">
                          <div className="text-xs text-zinc-500 mb-1">Total USDT</div>
                          <div className="text-xl font-bold font-mono text-white">
                            {formatCurrency(liveBalance.equity || 0)}
                          </div>
                          <div className="text-xs text-zinc-600">Free + Locked</div>
                        </div>
                        <div className="p-3 bg-zinc-900 rounded-lg">
                          <div className="text-xs text-zinc-500 mb-1">MEXC Status</div>
                          <div className="text-xl font-bold">
                            {mexc_keys_connected ? (
                              <span className="text-green-500 flex items-center gap-2"><Wifi className="w-5 h-5" />Verbunden</span>
                            ) : (
                              <span className="text-red-500 flex items-center gap-2"><WifiOff className="w-5 h-5" />Fehler</span>
                            )}
                          </div>
                          <div className="text-xs text-zinc-600">
                            {liveBalance.last_updated && format(new Date(liveBalance.last_updated), 'HH:mm:ss')}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center text-zinc-500 py-4">
                        <Activity className="w-6 h-6 mx-auto animate-spin mb-2" />
                        Lade Wallet-Daten...
                      </div>
                    )}
                  </div>
                  
                  {/* Budget System (Calculated) */}
                  <div className="bg-zinc-950 border border-blue-900/30 rounded-lg p-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
                      <Shield className="w-5 h-5 text-blue-500" />
                      Budget System
                      <span className="text-xs text-zinc-500 font-normal ml-2">
                        Schützt dein Wallet vor Übertrading
                      </span>
                    </h3>
                    
                    <div className="grid grid-cols-5 gap-4">
                      <div className="p-3 bg-blue-950/30 border border-blue-900/30 rounded-lg">
                        <div className="text-xs text-blue-400 mb-1">Reserve</div>
                        <div className="text-xl font-bold font-mono text-blue-400">
                          {formatCurrency(settings.reserve_usdt)}
                        </div>
                        <div className="text-xs text-blue-600">Wird nie angetastet</div>
                      </div>
                      <div className="p-3 bg-zinc-900 rounded-lg">
                        <div className="text-xs text-zinc-500 mb-1">Trading Budget</div>
                        <div className="text-xl font-bold font-mono text-white">
                          {formatCurrency(settings.trading_budget_usdt)}
                        </div>
                        <div className="text-xs text-zinc-600">Max. Gesamt-Exposure</div>
                      </div>
                      <div className="p-3 bg-zinc-900 rounded-lg">
                        <div className="text-xs text-zinc-500 mb-1">Used Budget</div>
                        <div className="text-xl font-bold font-mono text-orange-500">
                          {formatCurrency(liveBalance?.budget?.used_budget || 0)}
                        </div>
                        <div className="text-xs text-zinc-600">In Positionen</div>
                      </div>
                      <div className="p-3 bg-green-950/30 border border-green-900/30 rounded-lg">
                        <div className="text-xs text-green-400 mb-1">Available to Bot</div>
                        <div className={`text-xl font-bold font-mono ${
                          (liveBalance?.budget?.remaining_budget || 0) > 50 ? 'text-green-500' : 
                          (liveBalance?.budget?.remaining_budget || 0) > 0 ? 'text-yellow-500' : 'text-red-500'
                        }`}>
                          {formatCurrency(liveBalance?.budget?.remaining_budget || 0)}
                        </div>
                        <div className="text-xs text-green-600">Für neue Trades</div>
                      </div>
                      <div className="p-3 bg-zinc-900 rounded-lg">
                        <div className="text-xs text-zinc-500 mb-1">Max Order</div>
                        <div className="text-xl font-bold font-mono text-white">
                          {formatCurrency(settings.max_order_notional_usdt)}
                        </div>
                        <div className="text-xs text-zinc-600">Pro Trade</div>
                      </div>
                    </div>
                    
                    <div className="mt-3 p-2 bg-zinc-900 rounded text-xs text-zinc-500">
                      <strong>Berechnung:</strong> Available = min(USDT_Free - Reserve, Trading Budget - Used Budget)
                    </div>
                  </div>

                  {/* Live Daily Cap Progress */}
                  {liveBalance?.daily_cap && (
                    <div className="bg-zinc-950 border border-red-900/30 rounded-lg p-4" data-testid="live-daily-cap">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-red-500" />
                          <span className="text-sm font-medium text-red-500">Daily Trading Cap</span>
                          <Badge className="bg-red-500/10 text-red-400 text-xs">LIVE</Badge>
                        </div>
                        <div className="text-xs text-zinc-500">
                          Reset: 00:00 UTC
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-zinc-400">
                            Heute gehandelt: <span className="font-mono text-white">{formatCurrency(liveBalance.daily_cap.used)}</span>
                          </span>
                          <span className="text-zinc-400">
                            Limit: <span className="font-mono text-white">{formatCurrency(liveBalance.daily_cap.cap)}</span>
                          </span>
                        </div>
                        <div className="relative h-3 bg-zinc-800 rounded-full overflow-hidden">
                          <div 
                            className={`absolute left-0 top-0 h-full rounded-full transition-all duration-500 ${
                              (liveBalance.daily_cap.used / liveBalance.daily_cap.cap) >= 0.9 
                                ? 'bg-red-500' 
                                : (liveBalance.daily_cap.used / liveBalance.daily_cap.cap) >= 0.7 
                                  ? 'bg-yellow-500' 
                                  : 'bg-green-500'
                            }`}
                            style={{ width: `${Math.min(100, (liveBalance.daily_cap.used / liveBalance.daily_cap.cap) * 100)}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className={`font-medium ${
                            liveBalance.daily_cap.remaining <= 0 ? 'text-red-400' : 'text-green-400'
                          }`}>
                            {liveBalance.daily_cap.remaining <= 0 
                              ? '⚠️ Tageslimit erreicht - Keine weiteren Trades heute!' 
                              : `${formatCurrency(liveBalance.daily_cap.remaining)} verfügbar`
                            }
                          </span>
                          <span className="text-zinc-500">
                            {Math.round((liveBalance.daily_cap.used / liveBalance.daily_cap.cap) * 100)}% genutzt
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-8 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-zinc-500">
                  <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-zinc-700" />
                  <p>Live Mode muss zuerst aktiviert werden um Wallet-Daten anzuzeigen.</p>
                </div>
              )}

              {/* Live Sub-Tabs */}
              {settings.live_confirmed && (
                <Tabs defaultValue="trades" className="w-full">
                  <TabsList className="bg-zinc-950 border border-red-900/30">
                    <TabsTrigger value="trades" className="data-[state=active]:text-red-500"><History className="w-4 h-4 mr-2" />Live Trades</TabsTrigger>
                    <TabsTrigger value="logs" className="data-[state=active]:text-red-500"><FileText className="w-4 h-4 mr-2" />Live Logs</TabsTrigger>
                    <TabsTrigger value="settings" className="data-[state=active]:text-red-500"><Settings className="w-4 h-4 mr-2" />Settings</TabsTrigger>
                  </TabsList>
                  <div className="mt-4">
                    <TabsContent value="trades"><TradesTab currentMode="live" /></TabsContent>
                    <TabsContent value="logs"><LogsTab logs={logs.filter(l => l.msg?.includes('[LIVE]'))} /></TabsContent>
                    <TabsContent value="settings"><SettingsTab /></TabsContent>
                  </div>
                </Tabs>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* Live Mode Confirmation Dialog */}
        <LiveModeConfirm 
          open={showLiveConfirm} 
          onClose={() => setShowLiveConfirm(false)} 
          onConfirm={handleLiveConfirmed}
        />
      </div>
    </div>
  );
};

export default DashboardPage;
