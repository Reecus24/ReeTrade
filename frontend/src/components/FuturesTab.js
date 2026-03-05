import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Switch } from './ui/switch';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { ScrollArea } from './ui/scroll-area';
import { 
  TrendingUp, TrendingDown, AlertTriangle, Zap, Shield, DollarSign, 
  Activity, RefreshCw, History, Target, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import { format } from 'date-fns';
import { de } from 'date-fns/locale';

const API = process.env.REACT_APP_BACKEND_URL;

export default function FuturesTab({ token, settings, onSettingsUpdate }) {
  const [loading, setLoading] = useState(false);
  const [futuresStatus, setFuturesStatus] = useState(null);
  const [futuresTrades, setFuturesTrades] = useState([]);
  const [error, setError] = useState(null);
  const [testResults, setTestResults] = useState(null);
  const [localSettings, setLocalSettings] = useState({
    futures_enabled: settings?.futures_enabled || false,
    futures_default_leverage: settings?.futures_default_leverage || 5,
    futures_max_leverage: settings?.futures_max_leverage || 10,
    futures_allow_shorts: settings?.futures_allow_shorts !== false
  });

  useEffect(() => {
    if (settings?.futures_enabled) {
      fetchFuturesStatus();
      fetchFuturesTrades();
    }
  }, [settings?.futures_enabled]);

  const fetchFuturesStatus = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/api/futures/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setFuturesStatus(res.data);
      if (res.data?.error) {
        setError(res.data.error);
      } else {
        setError(null);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  };

  const fetchFuturesTrades = async () => {
    try {
      const res = await axios.get(`${API}/api/trades?market_type=futures&limit=50`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setFuturesTrades(res.data.trades || []);
    } catch (err) {
      console.error('Futures trades fetch error:', err);
    }
  };

  const handleEnableFutures = async () => {
    try {
      setLoading(true);
      await axios.post(`${API}/api/futures/enable`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLocalSettings(prev => ({ ...prev, futures_enabled: true }));
      onSettingsUpdate?.();
      fetchFuturesStatus();
      fetchFuturesTrades();
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Aktivieren');
    } finally {
      setLoading(false);
    }
  };

  const handleDisableFutures = async () => {
    try {
      setLoading(true);
      await axios.post(`${API}/api/futures/disable`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLocalSettings(prev => ({ ...prev, futures_enabled: false }));
      setFuturesStatus(null);
      onSettingsUpdate?.();
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Deaktivieren');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      setLoading(true);
      await axios.put(`${API}/api/futures/settings`, null, {
        params: {
          default_leverage: localSettings.futures_default_leverage,
          max_leverage: localSettings.futures_max_leverage,
          allow_shorts: localSettings.futures_allow_shorts
        },
        headers: { Authorization: `Bearer ${token}` }
      });
      onSettingsUpdate?.();
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Speichern');
    } finally {
      setLoading(false);
    }
  };

  const handleCloseAllPositions = async () => {
    if (!window.confirm('Wirklich ALLE Futures-Positionen schließen?')) return;
    
    try {
      setLoading(true);
      await axios.post(`${API}/api/futures/close-all`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchFuturesStatus();
      fetchFuturesTrades();
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Schließen');
    } finally {
      setLoading(false);
    }
  };

  const handleTestFutures = async () => {
    try {
      setLoading(true);
      setTestResults(null);
      const res = await axios.get(`${API}/api/futures/test`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTestResults(res.data);
      if (res.data.all_passed) {
        setError(null);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Test fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (val) => {
    if (val === undefined || val === null) return '$0.00';
    return `$${parseFloat(val).toFixed(2)}`;
  };

  return (
    <div className="space-y-6" data-testid="futures-tab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-500" />
            FUTURES Trading
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            Hebel-Trading mit Long & Short - Alles automatisch von KI optimiert
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleTestFutures}
            disabled={loading}
            className="bg-purple-900/30 border-purple-700 hover:bg-purple-800"
          >
            🔬 API Test
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => { fetchFuturesStatus(); fetchFuturesTrades(); }}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <Badge 
            className={localSettings.futures_enabled ? "bg-green-600" : "bg-gray-600"}
          >
            {localSettings.futures_enabled ? "AKTIV" : "DEAKTIVIERT"}
          </Badge>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive" className="bg-red-900/50 border-red-700">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <p className="font-medium">{error}</p>
            {error.includes('Access Denied') || error.includes('Berechtigung') || error.includes('whitelisted') ? (
              <div className="mt-2 text-xs space-y-1">
                <p>🔧 <strong>Lösung:</strong></p>
                <ol className="list-decimal list-inside space-y-1 text-red-200">
                  <li>Gehe zu <a href="https://www.mexc.com/user/security/api" target="_blank" rel="noopener noreferrer" className="underline">MEXC API Einstellungen</a></li>
                  <li>Stelle sicher, dass "Futures Trading" aktiviert ist</li>
                  <li>Prüfe die IP-Whitelist (oder deaktiviere sie zum Testen)</li>
                  <li>Erstelle ggf. einen neuen API-Key mit Futures Berechtigung</li>
                </ol>
              </div>
            ) : null}
          </AlertDescription>
        </Alert>
      )}

      {/* Test Results */}
      {testResults && (
        <Card className={`border-2 ${testResults.all_passed ? 'border-green-600 bg-green-900/20' : 'border-red-600 bg-red-900/20'}`}>
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              {testResults.all_passed ? '✅' : '❌'} API-Test Ergebnisse
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              {Object.entries(testResults.tests || {}).map(([name, result]) => (
                <div key={name} className="flex items-center justify-between p-2 bg-zinc-900 rounded">
                  <span className="text-white">{name.toUpperCase()}</span>
                  <div className="flex items-center gap-2">
                    {result.success ? (
                      <Badge className="bg-green-600">✓ OK</Badge>
                    ) : (
                      <Badge className="bg-red-600">✗ Fehler</Badge>
                    )}
                    {result.error && <span className="text-red-400 text-xs">{result.error.substring(0, 50)}</span>}
                    {result.count !== undefined && <span className="text-zinc-400 text-xs">({result.count} Contracts)</span>}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Enable/Disable & Settings */}
      <Card className="bg-gray-800/50 border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Futures Konfiguration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
            <div>
              <p className="text-white font-medium">Futures Trading aktivieren</p>
              <p className="text-gray-400 text-sm">KI entscheidet automatisch wann Futures sinnvoll sind</p>
            </div>
            <Switch
              checked={localSettings.futures_enabled}
              onCheckedChange={(checked) => {
                if (checked) handleEnableFutures();
                else handleDisableFutures();
              }}
              disabled={loading}
              data-testid="futures-toggle"
            />
          </div>

          {localSettings.futures_enabled && (
            <>
              {/* Auto-Info */}
              <div className="p-3 bg-purple-900/30 border border-purple-700 rounded-lg">
                <p className="text-sm text-purple-300">
                  <strong>🤖 Vollautomatisch:</strong> Die KI setzt Stop-Loss & Take-Profit automatisch 
                  basierend auf ATR und Markt-Regime. Du musst nichts manuell einstellen!
                </p>
              </div>

              {/* Leverage Settings */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white text-sm">Standard Hebel</label>
                    <span className="text-yellow-400 font-bold">{localSettings.futures_default_leverage}x</span>
                  </div>
                  <Slider
                    value={[localSettings.futures_default_leverage]}
                    onValueChange={([v]) => setLocalSettings(prev => ({ ...prev, futures_default_leverage: v }))}
                    min={2}
                    max={localSettings.futures_max_leverage}
                    step={1}
                    className="w-full"
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white text-sm">Max Hebel</label>
                    <span className="text-orange-400 font-bold">{localSettings.futures_max_leverage}x</span>
                  </div>
                  <Slider
                    value={[localSettings.futures_max_leverage]}
                    onValueChange={([v]) => setLocalSettings(prev => ({ 
                      ...prev, 
                      futures_max_leverage: v,
                      futures_default_leverage: Math.min(prev.futures_default_leverage, v)
                    }))}
                    min={2}
                    max={20}
                    step={1}
                    className="w-full"
                  />
                </div>
              </div>

              {/* Allow Shorts */}
              <div className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                <div>
                  <p className="text-white font-medium">Short-Positionen erlauben</p>
                  <p className="text-gray-400 text-sm">KI kann auf fallende Kurse setzen (BEARISH)</p>
                </div>
                <Switch
                  checked={localSettings.futures_allow_shorts}
                  onCheckedChange={(checked) => setLocalSettings(prev => ({ ...prev, futures_allow_shorts: checked }))}
                />
              </div>

              <Button 
                onClick={handleSaveSettings}
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                Einstellungen speichern
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {/* Futures Account Status */}
      {localSettings.futures_enabled && futuresStatus?.account && (
        <Card className="bg-gray-800/50 border-yellow-900/50">
          <CardHeader>
            <CardTitle className="text-lg text-white flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-green-400" />
              Futures Konto
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-900/50 p-3 rounded-lg">
                <p className="text-gray-400 text-xs">Verfügbar</p>
                <p className="text-xl font-bold text-green-400">
                  {formatCurrency(futuresStatus.account?.available_balance)}
                </p>
              </div>
              <div className="bg-gray-900/50 p-3 rounded-lg">
                <p className="text-gray-400 text-xs">In Positionen</p>
                <p className="text-xl font-bold text-orange-400">
                  {formatCurrency(futuresStatus.account?.frozen_balance)}
                </p>
              </div>
              <div className="bg-gray-900/50 p-3 rounded-lg">
                <p className="text-gray-400 text-xs">Unrealisiert PnL</p>
                <p className={`text-xl font-bold ${
                  (futuresStatus.account?.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {formatCurrency(futuresStatus.account?.unrealized_pnl)}
                </p>
              </div>
              <div className="bg-gray-900/50 p-3 rounded-lg">
                <p className="text-gray-400 text-xs">Offene Positionen</p>
                <p className="text-xl font-bold text-white">
                  {futuresStatus.open_positions || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Open Positions */}
      {localSettings.futures_enabled && futuresStatus?.positions?.length > 0 && (
        <Card className="bg-gray-800/50 border-gray-700">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-400" />
              Offene Futures Positionen
            </CardTitle>
            <Button 
              variant="destructive" 
              size="sm"
              onClick={handleCloseAllPositions}
              disabled={loading}
            >
              Alle schließen
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {futuresStatus.positions.map((pos, idx) => (
                <div 
                  key={idx} 
                  className="bg-gray-900/50 p-4 rounded-lg"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {pos.position_type === 'LONG' ? (
                        <ArrowUpRight className="w-5 h-5 text-green-400" />
                      ) : (
                        <ArrowDownRight className="w-5 h-5 text-red-400" />
                      )}
                      <div>
                        <p className="text-white font-medium">{pos.symbol}</p>
                        <p className="text-gray-400 text-sm">
                          {pos.position_type} {pos.leverage}x | Margin: {formatCurrency(pos.margin)}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`font-bold text-lg ${pos.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {pos.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(pos.unrealized_pnl)}
                      </p>
                      <p className="text-gray-400 text-xs">
                        Entry: ${pos.entry_price?.toFixed(4)} | Liq: ${pos.liquidation_price?.toFixed(4)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Futures Trade History */}
      <Card className="bg-gray-800/50 border-orange-900/30">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <History className="w-5 h-5 text-orange-400" />
            FUTURES History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {futuresTrades.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Noch keine Futures-Trades</p>
              <p className="text-sm">Die KI wird automatisch Futures nutzen wenn es sinnvoll ist</p>
            </div>
          ) : (
            <ScrollArea className="h-64">
              <div className="space-y-2">
                {futuresTrades.map((trade, idx) => (
                  <div 
                    key={idx}
                    className={`p-3 rounded-lg border ${
                      trade.pnl >= 0 
                        ? 'bg-green-950/20 border-green-900/50' 
                        : 'bg-red-950/20 border-red-900/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {trade.side === 'BUY' || trade.side === 'LONG' ? (
                          <ArrowUpRight className="w-4 h-4 text-green-400" />
                        ) : (
                          <ArrowDownRight className="w-4 h-4 text-red-400" />
                        )}
                        <div>
                          <p className="text-white font-mono text-sm">{trade.symbol}</p>
                          <p className="text-gray-500 text-xs">
                            {trade.ts ? format(new Date(trade.ts), 'dd.MM HH:mm', { locale: de }) : '-'}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {trade.pnl >= 0 ? '+' : ''}{formatCurrency(trade.pnl)}
                        </p>
                        <p className="text-gray-500 text-xs">
                          {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct?.toFixed(1)}%
                        </p>
                      </div>
                    </div>
                    {trade.reason && (
                      <p className="text-xs text-gray-500 mt-1 truncate">{trade.reason}</p>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      {/* Risk Warning */}
      <Alert className="bg-amber-900/30 border-amber-700">
        <AlertTriangle className="h-4 w-4 text-amber-500" />
        <AlertDescription className="text-amber-200">
          <strong>Automatisches Trading:</strong> Die KI setzt Stop-Loss, Take-Profit und Hebel automatisch 
          basierend auf Marktbedingungen. Bei BEARISH Markt werden Shorts bevorzugt, bei BULLISH Longs.
        </AlertDescription>
      </Alert>
    </div>
  );
}
