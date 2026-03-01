import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { 
  Activity, Play, Square, AlertTriangle, Settings, FileText, History,
  Wifi, WifiOff, RefreshCw, LogOut, Wallet, DollarSign, Clock, Bot
} from 'lucide-react';
import { format } from 'date-fns';
import TradesTab from '@/components/TradesTab';
import SettingsTab from '@/components/SettingsTab';
import LogsTab from '@/components/LogsTab';
import LiveModeConfirm from '@/components/LiveModeConfirm';
import BotStatusPanel from '@/components/BotStatusPanel';
import PositionsPanel from '@/components/PositionsPanel';
import TradingModeSelector from '@/components/TradingModeSelector';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

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
    await fetchBalance();
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

  const { settings, live_account, mexc_keys_connected, mexc_error } = status;

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">ReeTrade Terminal</h1>
            <p className="text-zinc-500">Live Trading Bot</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 rounded-lg" title={mexc_error || ''}>
              {mexc_keys_connected ? (
                <><Wifi className="w-4 h-4 text-green-500" /><span className="text-sm text-green-500">MEXC Connected</span></>
              ) : (
                <><WifiOff className="w-4 h-4 text-red-500" /><span className="text-sm text-red-500">{mexc_error ? 'Keys ungültig' : 'Keys fehlen'}</span></>
              )}
            </div>
            <Button onClick={onLogout} variant="ghost" size="sm" className="text-zinc-400">
              <LogOut className="w-4 h-4 mr-2" />Logout
            </Button>
          </div>
        </div>

        {/* Live Warning Banner - Not Confirmed */}
        {!settings.live_confirmed && (
          <div className="p-4 bg-red-950/30 border border-red-900 rounded-lg mb-6">
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
        <div className={`p-4 rounded-lg mb-6 ${settings.live_running ? 'bg-red-950/50 border-2 border-red-500 animate-pulse' : 'bg-zinc-950 border border-red-900/30'}`}>
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

        {/* Trading Mode Selector (Manual / AI) */}
        {settings.live_confirmed && (
          <div className="bg-zinc-950 border border-purple-900/30 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Bot className="w-5 h-5 text-purple-500" />
              <span className="font-semibold text-purple-400">Trading Modus</span>
            </div>
            <TradingModeSelector 
              currentMode={settings.trading_mode || 'manual'}
              onModeChange={(mode) => {
                setStatus(prev => ({
                  ...prev,
                  settings: { ...prev.settings, trading_mode: mode }
                }));
              }}
              aiStatus={{
                confidence: settings.ai_confidence,
                risk_score: settings.ai_risk_score,
                reasoning: settings.ai_reasoning,
                last_override: settings.ai_last_override,
                min_position: settings.ai_min_position,
                max_position: settings.ai_max_position,
                current_position: settings.ai_current_position
              }}
            />
          </div>
        )}

        {/* MEXC Wallet + Budget System */}
        {settings.live_confirmed ? (
          <div className="space-y-4 mb-6">
            {/* MEXC Spot Wallet */}
            <div className="bg-zinc-950 border border-green-900/30 rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Wallet className="w-5 h-5 text-green-500" />
                  MEXC Spot Wallet
                  <Badge className="bg-green-500/10 text-green-500 text-xs">SYNCED</Badge>
                </h3>
                <Button 
                  onClick={fetchBalance} 
                  disabled={balanceLoading}
                  variant="ghost" 
                  size="sm"
                  className="text-zinc-400"
                >
                  <RefreshCw className={`w-4 h-4 ${balanceLoading ? 'animate-spin' : ''}`} />
                </Button>
              </div>
              
              {balanceError ? (
                <div className="p-4 bg-red-950/30 border border-red-900 rounded text-red-400 text-sm">
                  {balanceError}
                </div>
              ) : balance ? (
                <div className="grid grid-cols-4 gap-4">
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500 mb-1">USDT Free</div>
                    <div className="text-xl font-bold font-mono text-green-500">
                      {formatCurrency(balance.budget?.usdt_free || balance.cash || 0)}
                    </div>
                  </div>
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500 mb-1">USDT Locked</div>
                    <div className="text-xl font-bold font-mono text-orange-500">
                      {formatCurrency(balance.locked || 0)}
                    </div>
                  </div>
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500 mb-1">Total USDT</div>
                    <div className="text-xl font-bold font-mono text-white">
                      {formatCurrency(balance.equity || 0)}
                    </div>
                  </div>
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500 mb-1">Positionen</div>
                    <div className="text-xl font-bold font-mono">
                      {balance.open_positions_count || 0} / {settings.max_positions}
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
            
            {/* Budget System */}
            {balance && (
              <div className="bg-zinc-950 border border-blue-900/30 rounded-lg p-4">
                <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
                  <DollarSign className="w-5 h-5 text-blue-500" />
                  Budget System
                </h3>
                
                <div className="grid grid-cols-5 gap-4">
                  <div className="p-3 bg-blue-950/30 border border-blue-900/30 rounded-lg">
                    <div className="text-xs text-blue-400 mb-1">Reserve</div>
                    <div className="text-xl font-bold font-mono text-blue-400">
                      {formatCurrency(settings.reserve_usdt)}
                    </div>
                  </div>
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500 mb-1">Trading Budget</div>
                    <div className="text-xl font-bold font-mono text-white">
                      {formatCurrency(settings.trading_budget_usdt)}
                    </div>
                  </div>
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500 mb-1">Used Budget</div>
                    <div className="text-xl font-bold font-mono text-orange-500">
                      {formatCurrency(balance.budget?.used_budget || 0)}
                    </div>
                  </div>
                  <div className="p-3 bg-green-950/30 border border-green-900/30 rounded-lg">
                    <div className="text-xs text-green-400 mb-1">Available</div>
                    <div className="text-xl font-bold font-mono text-green-500">
                      {formatCurrency(balance.budget?.remaining_budget || 0)}
                    </div>
                  </div>
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500 mb-1">Max Order</div>
                    <div className="text-xl font-bold font-mono text-white">
                      {formatCurrency(settings.live_max_order_usdt)}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Daily Cap Progress */}
            {balance?.daily_cap && (
              <div className="bg-zinc-950 border border-red-900/30 rounded-lg p-4" data-testid="live-daily-cap">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-red-500" />
                    <span className="text-sm font-medium text-red-500">Daily Trading Cap</span>
                  </div>
                  <div className="text-xs text-zinc-500">Reset: 00:00 UTC</div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-400">
                      Heute gehandelt: <span className="font-mono text-white">{formatCurrency(balance.daily_cap.used)}</span>
                    </span>
                    <span className="text-zinc-400">
                      Limit: <span className="font-mono text-white">{formatCurrency(balance.daily_cap.cap)}</span>
                    </span>
                  </div>
                  <div className="relative h-3 bg-zinc-800 rounded-full overflow-hidden">
                    <div 
                      className={`absolute left-0 top-0 h-full rounded-full transition-all ${
                        (balance.daily_cap.used / balance.daily_cap.cap) >= 0.9 ? 'bg-red-500' : 
                        (balance.daily_cap.used / balance.daily_cap.cap) >= 0.7 ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min(100, (balance.daily_cap.used / balance.daily_cap.cap) * 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className={balance.daily_cap.remaining <= 0 ? 'text-red-400' : 'text-green-400'}>
                      {balance.daily_cap.remaining <= 0 
                        ? '⚠️ Tageslimit erreicht!' 
                        : `${formatCurrency(balance.daily_cap.remaining)} verfügbar`
                      }
                    </span>
                    <span className="text-zinc-500">
                      {Math.round((balance.daily_cap.used / balance.daily_cap.cap) * 100)}% genutzt
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="p-8 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-zinc-500 mb-6">
            <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-zinc-700" />
            <p>Live Mode muss zuerst aktiviert werden um Wallet-Daten anzuzeigen.</p>
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

        {/* Sub-Tabs */}
        {settings.live_confirmed && (
          <Tabs defaultValue="history" className="w-full mt-6">
            <TabsList className="bg-zinc-950 border border-red-900/30">
              <TabsTrigger value="history" className="data-[state=active]:text-red-500">
                <History className="w-4 h-4 mr-2" />History
              </TabsTrigger>
              <TabsTrigger value="logs" className="data-[state=active]:text-red-500">
                <FileText className="w-4 h-4 mr-2" />Logs
              </TabsTrigger>
              <TabsTrigger value="settings" className="data-[state=active]:text-red-500">
                <Settings className="w-4 h-4 mr-2" />Settings
              </TabsTrigger>
            </TabsList>
            <div className="mt-4">
              <TabsContent value="history"><TradesTab /></TabsContent>
              <TabsContent value="logs"><LogsTab logs={logs.filter(l => l.msg?.includes('[LIVE]'))} /></TabsContent>
              <TabsContent value="settings"><SettingsTab /></TabsContent>
            </div>
          </Tabs>
        )}

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
