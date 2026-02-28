import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Play, Square, AlertTriangle, Activity, Database, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';
import LiveModeConfirm from '@/components/LiveModeConfirm';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    headers: {
      Authorization: `Bearer ${token}`
    }
  };
};

const OverviewTab = ({ status, onRefresh }) => {
  const [loading, setLoading] = useState(false);
  const [showLiveDialog, setShowLiveDialog] = useState(false);
  const [balanceData, setBalanceData] = useState(null);
  const [balanceError, setBalanceError] = useState(null);
  const [balanceLoading, setBalanceLoading] = useState(false);

  // Fetch balance based on mode
  const fetchBalance = async () => {
    if (!status?.settings) return;
    
    setBalanceLoading(true);
    setBalanceError(null);
    
    try {
      const response = await axios.get(`${BACKEND_URL}/api/account/balance`, getAuthHeaders());
      setBalanceData(response.data);
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Balance konnte nicht geladen werden';
      setBalanceError(errorMsg);
      setBalanceData(null);
      
      if (status.settings.mode === 'live') {
        toast.error(`MEXC Fehler: ${errorMsg}`);
      }
    } finally {
      setBalanceLoading(false);
    }
  };

  // Fetch balance when mode changes or on mount
  useEffect(() => {
    if (status?.settings) {
      fetchBalance();
    }
  }, [status?.settings?.mode]);

  if (!status) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="loading-indicator">
        <Activity className="w-8 h-8 text-zinc-600 animate-spin" />
      </div>
    );
  }

  const { settings, paper_account, heartbeat, is_alive } = status;

  const handleStartBot = async () => {
    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bot/start`, {}, getAuthHeaders());
      toast.success('Bot gestartet');
      onRefresh();
    } catch (error) {
      toast.error('Fehler beim Starten');
    } finally {
      setLoading(false);
    }
  };

  const handleStopBot = async () => {
    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bot/stop`, {}, getAuthHeaders());
      toast.success('Bot gestoppt');
      onRefresh();
    } catch (error) {
      toast.error('Fehler beim Stoppen');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestLive = async () => {
    setShowLiveDialog(true);
  };

  const handleDisableLive = async () => {
    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bot/live/disable`, {}, getAuthHeaders());
      toast.success('Paper Mode aktiviert');
      onRefresh();
    } catch (error) {
      toast.error('Fehler beim Umschalten');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD'
    }).format(value || 0);
  };

  const daily_pnl = paper_account ? (paper_account.equity - 10000) : 0;
  const daily_pnl_pct = (daily_pnl / 10000) * 100;

  return (
    <div className="space-y-6" data-testid="overview-tab">
      {/* Status Bar */}
      <div className="flex items-center justify-between p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-400">Status:</span>
            <Badge
              className={settings.bot_running ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-zinc-800 text-zinc-400'}
              data-testid="bot-status-badge"
            >
              {settings.bot_running ? 'RUNNING' : 'STOPPED'}
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-400">Mode:</span>
            <Badge
              className={settings.mode === 'live' ? 'bg-red-500/10 text-red-500 border-red-500/20 animate-pulse' : 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'}
              data-testid="bot-mode-badge"
            >
              {settings.mode === 'live' ? 'LIVE' : 'PAPER'}
            </Badge>
          </div>

          {heartbeat && (
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-xs text-zinc-500 font-mono">
                {format(new Date(heartbeat), 'HH:mm:ss')}
              </span>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          {!settings.bot_running ? (
            <Button
              onClick={handleStartBot}
              disabled={loading}
              className="bg-white text-black hover:bg-gray-200 font-medium"
              data-testid="start-bot-button"
            >
              <Play className="w-4 h-4 mr-2" />
              Start
            </Button>
          ) : (
            <Button
              onClick={handleStopBot}
              disabled={loading}
              className="bg-zinc-900 text-white border border-zinc-800 hover:bg-zinc-800"
              data-testid="stop-bot-button"
            >
              <Square className="w-4 h-4 mr-2" />
              Stop
            </Button>
          )}

          {settings.mode === 'paper' && !settings.live_confirmed && (
            <Button
              onClick={handleRequestLive}
              className="bg-red-900/20 text-red-500 border border-red-900/50 hover:bg-red-900/40"
              data-testid="request-live-button"
            >
              <AlertTriangle className="w-4 h-4 mr-2" />
              Go Live
            </Button>
          )}

          {settings.mode === 'live' && (
            <Button
              onClick={handleDisableLive}
              className="bg-zinc-900 text-white border border-zinc-800 hover:bg-zinc-800"
              data-testid="disable-live-button"
            >
              Back to Paper
            </Button>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="metric-equity">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Equity</div>
          <div className="text-2xl font-bold font-mono">{formatCurrency(paper_account?.equity || 10000)}</div>
        </div>

        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="metric-cash">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Cash</div>
          <div className="text-2xl font-bold font-mono">{formatCurrency(paper_account?.cash || 10000)}</div>
        </div>

        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="metric-pnl">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">PnL</div>
          <div className={`text-2xl font-bold font-mono ${daily_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {formatCurrency(daily_pnl)}
          </div>
          <div className={`text-xs ${daily_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {daily_pnl_pct >= 0 ? '+' : ''}{daily_pnl_pct.toFixed(2)}%
          </div>
        </div>

        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="metric-positions">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Open Positions</div>
          <div className="text-2xl font-bold font-mono">{paper_account?.open_positions?.length || 0} / {settings.max_positions}</div>
        </div>
      </div>

      {/* Open Positions */}
      {paper_account?.open_positions && paper_account.open_positions.length > 0 && (
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6" data-testid="open-positions-table">
          <h3 className="text-lg font-semibold mb-4">Offene Positionen</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 text-zinc-500 font-medium">Symbol</th>
                  <th className="text-left py-2 text-zinc-500 font-medium">Side</th>
                  <th className="text-right py-2 text-zinc-500 font-medium">Entry</th>
                  <th className="text-right py-2 text-zinc-500 font-medium">Qty</th>
                  <th className="text-right py-2 text-zinc-500 font-medium">Stop Loss</th>
                  <th className="text-right py-2 text-zinc-500 font-medium">Take Profit</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {paper_account.open_positions.map((pos, idx) => (
                  <tr key={idx} className="border-b border-zinc-900 last:border-0" data-testid={`position-${idx}`}>
                    <td className="py-3">{pos.symbol}</td>
                    <td className="py-3">
                      <span className="inline-flex items-center px-2 py-0.5 text-xs uppercase tracking-wider font-bold bg-green-500/10 text-green-500 border border-green-500/20 rounded">
                        {pos.side}
                      </span>
                    </td>
                    <td className="text-right py-3">${pos.entry_price.toFixed(4)}</td>
                    <td className="text-right py-3">{pos.qty.toFixed(4)}</td>
                    <td className="text-right py-3 text-red-500">${pos.stop_loss.toFixed(4)}</td>
                    <td className="text-right py-3 text-green-500">${pos.take_profit.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Live Mode Confirmation Dialog */}
      <LiveModeConfirm
        open={showLiveDialog}
        onClose={() => setShowLiveDialog(false)}
        onConfirm={() => {
          setShowLiveDialog(false);
          onRefresh();
        }}
      />
    </div>
  );
};

export default OverviewTab;
