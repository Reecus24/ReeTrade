import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Activity, Save, Key } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    headers: {
      Authorization: `Bearer ${token}`
    }
  };
};

const SettingsTab = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [mexcKeys, setMexcKeys] = useState({ api_key: '', api_secret: '' });
  const [keysConnected, setKeysConnected] = useState(false);
  const [showKeysInput, setShowKeysInput] = useState(false);

  useEffect(() => {
    fetchSettings();
    fetchKeysStatus();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/settings`, getAuthHeaders());
      setSettings(response.data);
    } catch (error) {
      toast.error('Fehler beim Laden der Einstellungen');
    } finally {
      setLoading(false);
    }
  };

  const fetchKeysStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/keys/mexc/status`, getAuthHeaders());
      setKeysConnected(response.data.connected);
    } catch (error) {
      console.error('Keys status error:', error);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${BACKEND_URL}/api/settings`, settings, getAuthHeaders());
      toast.success('Einstellungen gespeichert');
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveKeys = async () => {
    if (!mexcKeys.api_key || !mexcKeys.api_secret) {
      toast.error('Bitte beide Keys eingeben');
      return;
    }

    setSaving(true);
    try {
      await axios.post(`${BACKEND_URL}/api/keys/mexc`, mexcKeys, getAuthHeaders());
      toast.success('MEXC Keys gespeichert');
      setMexcKeys({ api_key: '', api_secret: '' });
      setShowKeysInput(false);
      fetchKeysStatus();
    } catch (error) {
      toast.error('Fehler beim Speichern der Keys');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className=\"flex items-center justify-center h-64\">
        <Activity className=\"w-8 h-8 text-zinc-600 animate-spin\" />
      </div>
    );
  }

  if (!settings) return null;

  return (
    <div className=\"space-y-6\" data-testid=\"settings-tab\">
      {/* Strategy Settings */}
      <div className=\"bg-zinc-950 border border-zinc-800 rounded-lg p-6\">
        <h3 className=\"text-lg font-semibold mb-4 flex items-center gap-2\">
          <Activity className=\"w-5 h-5\" />
          Strategie-Parameter
        </h3>
        <div className=\"grid grid-cols-2 md:grid-cols-3 gap-4\">
          <div>
            <Label htmlFor=\"ema_fast\" className=\"text-zinc-400\">EMA Fast</Label>
            <Input
              id=\"ema_fast\"
              type=\"number\"
              value={settings.ema_fast}
              onChange={(e) => setSettings({...settings, ema_fast: parseInt(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
              data-testid=\"setting-ema-fast\"
            />
          </div>
          <div>
            <Label htmlFor=\"ema_slow\" className=\"text-zinc-400\">EMA Slow</Label>
            <Input
              id=\"ema_slow\"
              type=\"number\"
              value={settings.ema_slow}
              onChange={(e) => setSettings({...settings, ema_slow: parseInt(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
              data-testid=\"setting-ema-slow\"
            />
          </div>
          <div>
            <Label htmlFor=\"rsi_period\" className=\"text-zinc-400\">RSI Period</Label>
            <Input
              id=\"rsi_period\"
              type=\"number\"
              value={settings.rsi_period}
              onChange={(e) => setSettings({...settings, rsi_period: parseInt(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
              data-testid=\"setting-rsi-period\"
            />
          </div>
          <div>
            <Label htmlFor=\"rsi_min\" className=\"text-zinc-400\">RSI Min</Label>
            <Input
              id=\"rsi_min\"
              type=\"number\"
              value={settings.rsi_min}
              onChange={(e) => setSettings({...settings, rsi_min: parseInt(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
            />
          </div>
          <div>
            <Label htmlFor=\"rsi_overbought\" className=\"text-zinc-400\">RSI Overbought</Label>
            <Input
              id=\"rsi_overbought\"
              type=\"number\"
              value={settings.rsi_overbought}
              onChange={(e) => setSettings({...settings, rsi_overbought: parseInt(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
            />
          </div>
        </div>
      </div>

      {/* Risk Management */}
      <div className=\"bg-zinc-950 border border-zinc-800 rounded-lg p-6\">
        <h3 className=\"text-lg font-semibold mb-4\">Risk Management</h3>
        <div className=\"grid grid-cols-2 md:grid-cols-3 gap-4\">
          <div>
            <Label htmlFor=\"risk_per_trade\" className=\"text-zinc-400\">Risk per Trade (%)</Label>
            <Input
              id=\"risk_per_trade\"
              type=\"number\"
              step=\"0.01\"
              value={settings.risk_per_trade * 100}
              onChange={(e) => setSettings({...settings, risk_per_trade: parseFloat(e.target.value) / 100})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
              data-testid=\"setting-risk-per-trade\"
            />
          </div>
          <div>
            <Label htmlFor=\"max_positions\" className=\"text-zinc-400\">Max Positions</Label>
            <Input
              id=\"max_positions\"
              type=\"number\"
              value={settings.max_positions}
              onChange={(e) => setSettings({...settings, max_positions: parseInt(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
              data-testid=\"setting-max-positions\"
            />
          </div>
          <div>
            <Label htmlFor=\"max_daily_loss\" className=\"text-zinc-400\">Max Daily Loss (%)</Label>
            <Input
              id=\"max_daily_loss\"
              type=\"number\"
              step=\"0.01\"
              value={settings.max_daily_loss * 100}
              onChange={(e) => setSettings({...settings, max_daily_loss: parseFloat(e.target.value) / 100})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
              data-testid=\"setting-max-daily-loss\"
            />
          </div>
          <div>
            <Label htmlFor=\"take_profit_rr\" className=\"text-zinc-400\">Take Profit R:R</Label>
            <Input
              id=\"take_profit_rr\"
              type=\"number\"
              step=\"0.1\"
              value={settings.take_profit_rr}
              onChange={(e) => setSettings({...settings, take_profit_rr: parseFloat(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
            />
          </div>
          <div>
            <Label htmlFor=\"cooldown_candles\" className=\"text-zinc-400\">Cooldown Candles</Label>
            <Input
              id=\"cooldown_candles\"
              type=\"number\"
              value={settings.cooldown_candles}
              onChange={(e) => setSettings({...settings, cooldown_candles: parseInt(e.target.value)})}
              className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
              data-testid=\"setting-cooldown-candles\"
            />
          </div>
          <div className=\"flex items-center space-x-3 mt-6\">
            <Switch
              id=\"atr_stop\"
              checked={settings.atr_stop}
              onCheckedChange={(checked) => setSettings({...settings, atr_stop: checked})}
              className=\"data-[state=checked]:bg-white\"
            />
            <Label htmlFor=\"atr_stop\" className=\"text-zinc-400 cursor-pointer\">ATR Stop</Label>
          </div>
        </div>
      </div>

      {/* MEXC API Keys */}
      <div className=\"bg-zinc-950 border border-zinc-800 rounded-lg p-6\">
        <div className=\"flex items-center justify-between mb-4\">
          <h3 className=\"text-lg font-semibold flex items-center gap-2\">
            <Key className=\"w-5 h-5\" />
            MEXC API Keys
          </h3>
          <span className={`text-sm px-3 py-1 rounded ${keysConnected ? 'bg-green-500/10 text-green-500' : 'bg-zinc-800 text-zinc-500'}`}>
            {keysConnected ? 'Verbunden' : 'Nicht konfiguriert'}
          </span>
        </div>

        {!showKeysInput ? (
          <Button
            onClick={() => setShowKeysInput(true)}
            className=\"bg-zinc-900 text-white border border-zinc-800 hover:bg-zinc-800\"
            data-testid=\"show-keys-input-button\"
          >
            {keysConnected ? 'Keys aktualisieren' : 'Keys hinzuf\u00fcgen'}
          </Button>
        ) : (
          <div className=\"space-y-4\">
            <div>
              <Label htmlFor=\"api_key\" className=\"text-zinc-400\">API Key</Label>
              <Input
                id=\"api_key\"
                type=\"password\"
                value={mexcKeys.api_key}
                onChange={(e) => setMexcKeys({...mexcKeys, api_key: e.target.value})}
                placeholder=\"MEXC API Key\"
                className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
                data-testid=\"mexc-api-key-input\"
              />
            </div>
            <div>
              <Label htmlFor=\"api_secret\" className=\"text-zinc-400\">API Secret</Label>
              <Input
                id=\"api_secret\"
                type=\"password\"
                value={mexcKeys.api_secret}
                onChange={(e) => setMexcKeys({...mexcKeys, api_secret: e.target.value})}
                placeholder=\"MEXC API Secret\"
                className=\"mt-2 bg-zinc-900 border-zinc-800 text-white\"
                data-testid=\"mexc-api-secret-input\"
              />
            </div>
            <div className=\"flex gap-2\">
              <Button
                onClick={handleSaveKeys}
                disabled={saving}
                className=\"bg-white text-black hover:bg-gray-200\"
                data-testid=\"save-mexc-keys-button\"
              >
                Keys speichern
              </Button>
              <Button
                onClick={() => setShowKeysInput(false)}
                className=\"bg-zinc-900 text-white border border-zinc-800 hover:bg-zinc-800\"
              >
                Abbrechen
              </Button>
            </div>
            <p className="text-xs text-zinc-500">
              ⚠️ Keys werden verschlüsselt gespeichert und niemals angezeigt
            </p>
          </div>
        )}
      </div>

      {/* Save Button */}
      <div className=\"flex justify-end\">
        <Button
          onClick={handleSave}
          disabled={saving}
          className=\"bg-white text-black hover:bg-gray-200 font-medium\"
          data-testid=\"save-settings-button\"
        >
          <Save className=\"w-4 h-4 mr-2\" />
          {saving ? 'Speichern...' : 'Einstellungen speichern'}
        </Button>
      </div>
    </div>
  );
};

export default SettingsTab;
