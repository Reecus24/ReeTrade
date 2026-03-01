import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { 
  Save, Key, Shield, TrendingUp, HelpCircle, Wallet, Clock 
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

const Tip = ({ text }) => (
  <div className="group relative inline-block ml-1">
    <HelpCircle className="w-3 h-3 text-zinc-600 cursor-help" />
    <div className="absolute z-50 hidden group-hover:block w-56 p-2 bg-zinc-800 border border-zinc-700 rounded text-xs text-zinc-300 shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-1">
      {text}
    </div>
  </div>
);

const Field = ({ label, tip, children, highlight, unit }) => (
  <div className={`p-3 rounded-lg ${highlight ? 'bg-blue-950/30 border border-blue-900/30' : 'bg-zinc-900'}`}>
    <Label className={`flex items-center text-xs ${highlight ? 'text-blue-400' : 'text-zinc-500'}`}>
      {label}{unit && <span className="text-zinc-600 ml-1">({unit})</span>}
      {tip && <Tip text={tip} />}
    </Label>
    <div className="mt-1.5">{children}</div>
  </div>
);

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
      toast.error('Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  };

  const fetchKeysStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/keys/mexc/status`, getAuthHeaders());
      setKeysConnected(response.data.connected);
    } catch (error) {}
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
      toast.error('Fehler');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) {
    return <div className="p-4 text-center text-zinc-500">Laden...</div>;
  }

  return (
    <div className="space-y-6">
      {/* MEXC API Keys */}
      <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Key className="w-5 h-5 text-blue-500" />
            MEXC API Keys
          </h3>
          <Badge className={keysConnected ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}>
            {keysConnected ? 'Verbunden' : 'Nicht konfiguriert'}
          </Badge>
        </div>
        
        {!showKeysInput ? (
          <Button onClick={() => setShowKeysInput(true)} variant="outline" className="w-full">
            {keysConnected ? 'Keys aktualisieren' : 'Keys hinzufügen'}
          </Button>
        ) : (
          <div className="space-y-3">
            <Input
              placeholder="API Key"
              value={mexcKeys.api_key}
              onChange={(e) => setMexcKeys(prev => ({ ...prev, api_key: e.target.value }))}
              className="bg-zinc-900 border-zinc-700"
            />
            <Input
              type="password"
              placeholder="API Secret"
              value={mexcKeys.api_secret}
              onChange={(e) => setMexcKeys(prev => ({ ...prev, api_secret: e.target.value }))}
              className="bg-zinc-900 border-zinc-700"
            />
            <div className="flex gap-2">
              <Button onClick={handleSaveKeys} disabled={saving} className="flex-1 bg-blue-600 hover:bg-blue-700">
                Speichern
              </Button>
              <Button onClick={() => setShowKeysInput(false)} variant="outline">
                Abbrechen
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Live Budget Settings */}
      <div className="p-4 bg-zinc-950 border border-red-900/30 rounded-lg">
        <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
          <Wallet className="w-5 h-5 text-red-500" />
          Budget Einstellungen
        </h3>
        
        <div className="grid grid-cols-2 gap-4">
          <Field 
            label="Reserve" 
            unit="USDT"
            highlight
            tip="Sicherheitsreserve - Bot tastet diesen Betrag nie an"
          >
            <Input
              type="number"
              value={settings.reserve_usdt || 0}
              onChange={(e) => setSettings(prev => ({ ...prev, reserve_usdt: parseFloat(e.target.value) || 0 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field 
            label="Trading Budget" 
            unit="USDT"
            tip="Maximales Gesamt-Exposure für alle Positionen"
          >
            <Input
              type="number"
              value={settings.trading_budget_usdt || 500}
              onChange={(e) => setSettings(prev => ({ ...prev, trading_budget_usdt: parseFloat(e.target.value) || 500 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field 
            label="Daily Cap" 
            unit="USDT"
            tip="Maximales Handelsvolumen pro Tag (Reset 00:00 UTC)"
          >
            <Input
              type="number"
              value={settings.live_daily_cap_usdt || 200}
              onChange={(e) => setSettings(prev => ({ ...prev, live_daily_cap_usdt: parseFloat(e.target.value) || 200 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field 
            label="Max Order" 
            unit="USDT"
            tip="Maximale Größe pro einzelnem Trade"
          >
            <Input
              type="number"
              value={settings.live_max_order_usdt || 50}
              onChange={(e) => setSettings(prev => ({ ...prev, live_max_order_usdt: parseFloat(e.target.value) || 50 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field 
            label="Min Notional" 
            unit="USDT"
            tip="Minimale Order-Größe (MEXC Mindestanforderung)"
          >
            <Input
              type="number"
              value={settings.live_min_notional_usdt || 10}
              onChange={(e) => setSettings(prev => ({ ...prev, live_min_notional_usdt: parseFloat(e.target.value) || 10 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
        </div>
      </div>

      {/* Strategy Settings */}
      <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-green-500" />
          Strategie Parameter
        </h3>
        
        <div className="grid grid-cols-3 gap-4">
          <Field label="EMA Fast" tip="Schneller Moving Average (Standard: 50)">
            <Input
              type="number"
              value={settings.ema_fast || 50}
              onChange={(e) => setSettings(prev => ({ ...prev, ema_fast: parseInt(e.target.value) || 50 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field label="EMA Slow" tip="Langsamer Moving Average (Standard: 200)">
            <Input
              type="number"
              value={settings.ema_slow || 200}
              onChange={(e) => setSettings(prev => ({ ...prev, ema_slow: parseInt(e.target.value) || 200 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field label="RSI Periode" tip="Relative Strength Index Periode">
            <Input
              type="number"
              value={settings.rsi_period || 14}
              onChange={(e) => setSettings(prev => ({ ...prev, rsi_period: parseInt(e.target.value) || 14 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field label="RSI Min" tip="Minimaler RSI für Entry">
            <Input
              type="number"
              value={settings.rsi_min || 50}
              onChange={(e) => setSettings(prev => ({ ...prev, rsi_min: parseInt(e.target.value) || 50 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field label="RSI Overbought" tip="RSI Obergrenze (kein Entry)">
            <Input
              type="number"
              value={settings.rsi_overbought || 75}
              onChange={(e) => setSettings(prev => ({ ...prev, rsi_overbought: parseInt(e.target.value) || 75 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
        </div>
      </div>

      {/* Risk Settings */}
      <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-yellow-500" />
          Risiko Management
        </h3>
        
        <div className="grid grid-cols-3 gap-4">
          <Field label="Max Positionen" tip="Maximale gleichzeitige Positionen">
            <Input
              type="number"
              value={settings.max_positions || 3}
              onChange={(e) => setSettings(prev => ({ ...prev, max_positions: parseInt(e.target.value) || 3 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field label="Take Profit R:R" tip="Risk-Reward Ratio für Take Profit">
            <Input
              type="number"
              step="0.5"
              value={settings.take_profit_rr || 2.0}
              onChange={(e) => setSettings(prev => ({ ...prev, take_profit_rr: parseFloat(e.target.value) || 2.0 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
          
          <Field label="Cooldown" unit="Candles" tip="Wartezeit nach Trade (15m Candles)">
            <Input
              type="number"
              value={settings.cooldown_candles || 3}
              onChange={(e) => setSettings(prev => ({ ...prev, cooldown_candles: parseInt(e.target.value) || 3 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
            />
          </Field>
        </div>
      </div>

      {/* Save Button */}
      <Button 
        onClick={handleSave} 
        disabled={saving} 
        className="w-full bg-red-600 hover:bg-red-700"
      >
        <Save className="w-4 h-4 mr-2" />
        {saving ? 'Speichern...' : 'Einstellungen speichern'}
      </Button>
    </div>
  );
};

export default SettingsTab;
