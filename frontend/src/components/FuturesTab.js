import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Switch } from './ui/switch';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { TrendingUp, TrendingDown, AlertTriangle, Zap, Shield, DollarSign, Activity } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function FuturesTab({ token, settings, onSettingsUpdate }) {
  const [loading, setLoading] = useState(false);
  const [futuresStatus, setFuturesStatus] = useState(null);
  const [error, setError] = useState(null);
  const [localSettings, setLocalSettings] = useState({
    futures_enabled: settings?.futures_enabled || false,
    futures_default_leverage: settings?.futures_default_leverage || 5,
    futures_max_leverage: settings?.futures_max_leverage || 10,
    futures_risk_per_trade: (settings?.futures_risk_per_trade || 0.02) * 100,
    futures_allow_shorts: settings?.futures_allow_shorts !== false
  });

  useEffect(() => {
    if (settings?.futures_enabled) {
      fetchFuturesStatus();
    }
  }, [settings?.futures_enabled]);

  const fetchFuturesStatus = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/api/futures/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setFuturesStatus(res.data);
      // Check for error in response (not HTTP error)
      if (res.data?.error) {
        setError(res.data.error);
      } else {
        setError(null);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Fehler beim Laden des Futures-Status');
    } finally {
      setLoading(false);
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
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Aktivieren von Futures');
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
      setError(err.response?.data?.detail || 'Fehler beim Deaktivieren von Futures');
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
          risk_per_trade: localSettings.futures_risk_per_trade / 100,
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
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Schließen der Positionen');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="futures-tab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-500" />
            Futures Trading
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            Handel mit Hebel - Long & Short Positionen
          </p>
        </div>
        <Badge 
          variant={localSettings.futures_enabled ? "default" : "secondary"}
          className={localSettings.futures_enabled ? "bg-green-600" : "bg-gray-600"}
        >
          {localSettings.futures_enabled ? "AKTIV" : "DEAKTIVIERT"}
        </Badge>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive" className="bg-red-900/50 border-red-700">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Risk Warning */}
      <Alert className="bg-amber-900/30 border-amber-700">
        <AlertTriangle className="h-4 w-4 text-amber-500" />
        <AlertDescription className="text-amber-200">
          <strong>Warnung:</strong> Futures-Trading mit Hebel birgt ein hohes Verlustrisiko. 
          Du kannst mehr als dein eingesetztes Kapital verlieren. Nutze nur Geld, das du bereit bist zu verlieren.
        </AlertDescription>
      </Alert>

      {/* Enable/Disable Toggle */}
      <Card className="bg-gray-800/50 border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Futures aktivieren
          </CardTitle>
          <CardDescription>
            Ermöglicht dem Bot, Futures-Positionen mit Hebel zu eröffnen
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white font-medium">
                {localSettings.futures_enabled ? 'Futures Trading ist aktiv' : 'Futures Trading ist deaktiviert'}
              </p>
              <p className="text-gray-400 text-sm">
                {localSettings.futures_enabled 
                  ? 'Die KI kann zwischen SPOT und FUTURES wählen'
                  : 'Nur SPOT-Trading wird verwendet'}
              </p>
            </div>
            <Switch
              checked={localSettings.futures_enabled}
              onCheckedChange={(checked) => {
                if (checked) {
                  handleEnableFutures();
                } else {
                  handleDisableFutures();
                }
              }}
              disabled={loading}
              data-testid="futures-toggle"
            />
          </div>
        </CardContent>
      </Card>

      {/* Futures Account Status */}
      {localSettings.futures_enabled && futuresStatus && (
        <Card className="bg-gray-800/50 border-gray-700">
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
                <p className="text-xl font-bold text-white">
                  ${futuresStatus.account?.available_balance?.toFixed(2) || '0.00'}
                </p>
              </div>
              <div className="bg-gray-900/50 p-3 rounded-lg">
                <p className="text-gray-400 text-xs">Gesperrt</p>
                <p className="text-xl font-bold text-white">
                  ${futuresStatus.account?.frozen_balance?.toFixed(2) || '0.00'}
                </p>
              </div>
              <div className="bg-gray-900/50 p-3 rounded-lg">
                <p className="text-gray-400 text-xs">Unrealisiert PnL</p>
                <p className={`text-xl font-bold ${
                  (futuresStatus.account?.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  ${futuresStatus.account?.unrealized_pnl?.toFixed(2) || '0.00'}
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
              <Activity className="w-5 h-5 text-purple-400" />
              Offene Futures Positionen
            </CardTitle>
            <Button 
              variant="destructive" 
              size="sm"
              onClick={handleCloseAllPositions}
              disabled={loading}
              data-testid="close-all-futures-btn"
            >
              Alle schließen
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {futuresStatus.positions.map((pos, idx) => (
                <div 
                  key={idx} 
                  className="bg-gray-900/50 p-4 rounded-lg flex items-center justify-between"
                  data-testid={`futures-position-${pos.symbol}`}
                >
                  <div className="flex items-center gap-3">
                    {pos.position_type === 'LONG' ? (
                      <TrendingUp className="w-5 h-5 text-green-400" />
                    ) : (
                      <TrendingDown className="w-5 h-5 text-red-400" />
                    )}
                    <div>
                      <p className="text-white font-medium">{pos.symbol}</p>
                      <p className="text-gray-400 text-sm">
                        {pos.position_type} {pos.leverage}x | Qty: {pos.quantity}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`font-bold ${pos.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      ${pos.unrealized_pnl?.toFixed(2)}
                    </p>
                    <p className="text-gray-400 text-xs">
                      Entry: ${pos.entry_price?.toFixed(4)}
                    </p>
                    <p className="text-gray-400 text-xs">
                      Liq: ${pos.liquidation_price?.toFixed(4)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Settings */}
      {localSettings.futures_enabled && (
        <Card className="bg-gray-800/50 border-gray-700">
          <CardHeader>
            <CardTitle className="text-lg text-white">Futures Einstellungen</CardTitle>
            <CardDescription>
              Konfiguriere Hebel und Risiko-Parameter für Futures-Trading
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Default Leverage */}
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
                data-testid="default-leverage-slider"
              />
              <p className="text-gray-400 text-xs mt-1">
                Der Hebel, den die KI standardmäßig verwendet
              </p>
            </div>

            {/* Max Leverage */}
            <div>
              <div className="flex justify-between mb-2">
                <label className="text-white text-sm">Maximaler Hebel</label>
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
                data-testid="max-leverage-slider"
              />
              <p className="text-gray-400 text-xs mt-1">
                Der maximale Hebel, den die KI niemals überschreitet
              </p>
            </div>

            {/* Risk per Trade */}
            <div>
              <div className="flex justify-between mb-2">
                <label className="text-white text-sm">Risiko pro Trade</label>
                <span className="text-blue-400 font-bold">{localSettings.futures_risk_per_trade.toFixed(1)}%</span>
              </div>
              <Slider
                value={[localSettings.futures_risk_per_trade]}
                onValueChange={([v]) => setLocalSettings(prev => ({ ...prev, futures_risk_per_trade: v }))}
                min={0.5}
                max={5}
                step={0.5}
                className="w-full"
                data-testid="risk-per-trade-slider"
              />
              <p className="text-gray-400 text-xs mt-1">
                Maximaler Verlust pro Futures-Trade als % des Kapitals
              </p>
            </div>

            {/* Allow Shorts */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-white font-medium">Short-Positionen erlauben</p>
                <p className="text-gray-400 text-sm">
                  Erlaube der KI, auf fallende Kurse zu setzen
                </p>
              </div>
              <Switch
                checked={localSettings.futures_allow_shorts}
                onCheckedChange={(checked) => setLocalSettings(prev => ({ ...prev, futures_allow_shorts: checked }))}
                data-testid="allow-shorts-toggle"
              />
            </div>

            {/* Save Button */}
            <Button 
              onClick={handleSaveSettings}
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700"
              data-testid="save-futures-settings-btn"
            >
              {loading ? 'Speichern...' : 'Einstellungen speichern'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Leverage Info */}
      <Card className="bg-gray-800/50 border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg text-white">Hebel-Übersicht</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="bg-green-900/30 p-3 rounded-lg border border-green-700">
              <p className="text-green-400 font-bold text-lg">2-3x</p>
              <p className="text-gray-400 text-xs">Konservativ</p>
              <p className="text-gray-500 text-xs">Liquidation: ~35%</p>
            </div>
            <div className="bg-yellow-900/30 p-3 rounded-lg border border-yellow-700">
              <p className="text-yellow-400 font-bold text-lg">5x</p>
              <p className="text-gray-400 text-xs">Moderat</p>
              <p className="text-gray-500 text-xs">Liquidation: ~20%</p>
            </div>
            <div className="bg-orange-900/30 p-3 rounded-lg border border-orange-700">
              <p className="text-orange-400 font-bold text-lg">10x</p>
              <p className="text-gray-400 text-xs">Aggressiv</p>
              <p className="text-gray-500 text-xs">Liquidation: ~10%</p>
            </div>
            <div className="bg-red-900/30 p-3 rounded-lg border border-red-700">
              <p className="text-red-400 font-bold text-lg">20x</p>
              <p className="text-gray-400 text-xs">Sehr Riskant</p>
              <p className="text-gray-500 text-xs">Liquidation: ~5%</p>
            </div>
          </div>
          <p className="text-gray-400 text-xs mt-4 text-center">
            Liquidation = Preis-Bewegung gegen deine Position, bei der du alles verlierst
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
