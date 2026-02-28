import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Activity, Save, Key, Shield, TrendingUp, AlertTriangle, HelpCircle, 
  Settings2, Wallet, Clock 
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

// Tooltip Component
const Tip = ({ text }) => (
  <div className="group relative inline-block ml-1">
    <HelpCircle className="w-3 h-3 text-zinc-600 cursor-help" />
    <div className="absolute z-50 hidden group-hover:block w-56 p-2 bg-zinc-800 border border-zinc-700 rounded text-xs text-zinc-300 shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-1">
      {text}
    </div>
  </div>
);

// Setting Field Component
const Field = ({ label, tip, children, highlight, unit }) => (
  <div className={`p-3 rounded-lg ${highlight ? 'bg-blue-950/30 border border-blue-900/30' : 'bg-zinc-900'}`}>
    <Label className={`flex items-center text-xs ${highlight ? 'text-blue-400' : 'text-zinc-500'}`}>
      {label}{unit && <span className="text-zinc-600 ml-1">({unit})</span>}
      {tip && <Tip text={tip} />}
    </Label>
    <div className="mt-1.5">{children}</div>
  </div>
);

const SettingsTab = ({ mode = 'paper' }) => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState(mode);
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
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-6 h-6 text-zinc-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings-tab">
      {/* Mode Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-3 bg-zinc-950 border border-zinc-800">
          <TabsTrigger value="paper" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
            <Shield className="w-4 h-4 mr-2" />Paper Settings
          </TabsTrigger>
          <TabsTrigger value="live" className="data-[state=active]:bg-red-500/10 data-[state=active]:text-red-500">
            <AlertTriangle className="w-4 h-4 mr-2" />Live Settings
          </TabsTrigger>
          <TabsTrigger value="strategy" className="data-[state=active]:bg-green-500/10 data-[state=active]:text-green-500">
            <TrendingUp className="w-4 h-4 mr-2" />Strategie
          </TabsTrigger>
        </TabsList>

        {/* ========== PAPER SETTINGS ========== */}
        <TabsContent value="paper" className="mt-6 space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-yellow-500" />
            <h3 className="font-semibold text-yellow-500">Paper Trading Einstellungen</h3>
            <Badge className="bg-yellow-500/10 text-yellow-500 text-xs">Kein echtes Geld</Badge>
          </div>
          
          {/* Paper Budget */}
          <div className="bg-zinc-950 border border-yellow-900/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Wallet className="w-4 h-4" />Paper Budget
            </h4>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Start Balance" tip="Simuliertes Startkapital für Paper Trading" unit="USDT">
                <Input
                  type="number" step="100"
                  value={settings.paper_start_balance_usdt || 500}
                  onChange={(e) => setSettings({...settings, paper_start_balance_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Max Order" tip="Maximale Größe einer einzelnen Paper Order" unit="USDT">
                <Input
                  type="number" step="10"
                  value={settings.paper_max_order_usdt || 50}
                  onChange={(e) => setSettings({...settings, paper_max_order_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Min Order" tip="Exchange Minimum Ordergröße" unit="USDT">
                <Input
                  type="number" step="1"
                  value={settings.min_notional_usdt || 10}
                  onChange={(e) => setSettings({...settings, min_notional_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
            </div>
          </div>

          {/* Paper Daily Cap */}
          <div className="bg-zinc-950 border border-yellow-900/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4" />Paper Daily Trading Cap
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Daily Cap" tip="Max. Handelsvolumen pro Tag (UTC Reset um 00:00)" unit="USDT" highlight>
                <Input
                  type="number" step="50"
                  value={settings.paper_daily_cap_usdt || 200}
                  onChange={(e) => setSettings({...settings, paper_daily_cap_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-blue-900/50 h-9"
                />
              </Field>
              <div className="p-3 bg-zinc-900 rounded-lg">
                <div className="text-xs text-zinc-500">Erklärung</div>
                <div className="text-sm text-zinc-400 mt-1">
                  Bot stoppt neue Trades wenn Tageslimit erreicht. Reset täglich 00:00 UTC.
                </div>
              </div>
            </div>
          </div>

          {/* Paper Fees */}
          <div className="bg-zinc-950 border border-yellow-900/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              💰 Simulierte Gebühren
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Trading Fee" tip="Handelsgebühr. 10 BPS = 0.10% pro Trade" unit="BPS">
                <Input
                  type="number"
                  value={settings.paper_fee_bps || 10}
                  onChange={(e) => setSettings({...settings, paper_fee_bps: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Slippage" tip="Preisabweichung bei Ausführung. 5 BPS = 0.05%" unit="BPS">
                <Input
                  type="number"
                  value={settings.paper_slippage_bps || 5}
                  onChange={(e) => setSettings({...settings, paper_slippage_bps: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
            </div>
          </div>
        </TabsContent>

        {/* ========== LIVE SETTINGS ========== */}
        <TabsContent value="live" className="mt-6 space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            <h3 className="font-semibold text-red-500">Live Trading Einstellungen</h3>
            <Badge className="bg-red-500/10 text-red-500 text-xs">ECHTES GELD</Badge>
          </div>
          
          {/* MEXC Keys */}
          <div className="bg-zinc-950 border border-red-900/30 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                <Key className="w-4 h-4" />MEXC API Keys
              </h4>
              <Badge className={keysConnected ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}>
                {keysConnected ? 'Verbunden' : 'Nicht konfiguriert'}
              </Badge>
            </div>
            
            {!showKeysInput ? (
              <Button onClick={() => setShowKeysInput(true)} variant="outline" size="sm" className="border-zinc-700">
                {keysConnected ? 'Keys aktualisieren' : 'Keys hinzufügen'}
              </Button>
            ) : (
              <div className="space-y-3">
                <Input
                  type="password"
                  placeholder="API Key"
                  value={mexcKeys.api_key}
                  onChange={(e) => setMexcKeys({...mexcKeys, api_key: e.target.value})}
                  className="bg-zinc-900 border-zinc-800 h-9"
                />
                <Input
                  type="password"
                  placeholder="API Secret"
                  value={mexcKeys.api_secret}
                  onChange={(e) => setMexcKeys({...mexcKeys, api_secret: e.target.value})}
                  className="bg-zinc-900 border-zinc-800 h-9"
                />
                <div className="flex gap-2">
                  <Button onClick={handleSaveKeys} size="sm" className="bg-red-600 hover:bg-red-700">Speichern</Button>
                  <Button onClick={() => setShowKeysInput(false)} size="sm" variant="ghost">Abbrechen</Button>
                </div>
              </div>
            )}
          </div>

          {/* Live Budget & Reserve */}
          <div className="bg-zinc-950 border border-red-900/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-blue-500" />Live Budget & Reserve
            </h4>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Reserve" tip="Sicherheitsreserve - Bot fasst diesen Betrag NIEMALS an" unit="USDT" highlight>
                <Input
                  type="number" step="100"
                  value={settings.reserve_usdt || 0}
                  onChange={(e) => setSettings({...settings, reserve_usdt: parseFloat(e.target.value) || 0})}
                  className="bg-zinc-800 border-blue-900/50 h-9"
                />
              </Field>
              <Field label="Trading Budget" tip="Max. Gesamt-Exposure (alle offenen Positionen zusammen)" unit="USDT">
                <Input
                  type="number" step="50"
                  value={settings.trading_budget_usdt || 500}
                  onChange={(e) => setSettings({...settings, trading_budget_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Max Order" tip="Maximale Größe einer einzelnen Live Order" unit="USDT">
                <Input
                  type="number" step="10"
                  value={settings.live_max_order_usdt || 50}
                  onChange={(e) => setSettings({...settings, live_max_order_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Min Order" tip="Minimale Größe pro Trade (kleinere Signale werden ignoriert)" unit="USDT">
                <Input
                  type="number" step="5"
                  value={settings.live_min_notional_usdt || 10}
                  onChange={(e) => setSettings({...settings, live_min_notional_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
            </div>
          </div>

          {/* Live Daily Cap */}
          <div className="bg-zinc-950 border border-red-900/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4" />Live Daily Trading Cap
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Daily Cap" tip="Max. Handelsvolumen pro Tag im Live Mode" unit="USDT" highlight>
                <Input
                  type="number" step="50"
                  value={settings.live_daily_cap_usdt || 200}
                  onChange={(e) => setSettings({...settings, live_daily_cap_usdt: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-blue-900/50 h-9"
                />
              </Field>
              <div className="p-3 bg-red-950/30 border border-red-900/30 rounded-lg">
                <div className="text-xs text-red-400">⚠️ Live Schutz</div>
                <div className="text-sm text-red-300 mt-1">
                  Begrenzt tägliches Risiko mit echtem Geld.
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* ========== STRATEGY SETTINGS ========== */}
        <TabsContent value="strategy" className="mt-6 space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-green-500" />
            <h3 className="font-semibold text-green-500">Strategie & Risk Management</h3>
            <Badge className="bg-green-500/10 text-green-500 text-xs">Gilt für beide Modi</Badge>
          </div>
          
          {/* EMA Strategy */}
          <div className="bg-zinc-950 border border-green-900/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-zinc-400 mb-3">📈 EMA Crossover Strategie</h4>
            <div className="grid grid-cols-5 gap-3">
              <Field label="EMA Fast" tip="Schneller gleitender Durchschnitt (kürzerer Zeitraum)">
                <Input
                  type="number"
                  value={settings.ema_fast || 50}
                  onChange={(e) => setSettings({...settings, ema_fast: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="EMA Slow" tip="Langsamer gleitender Durchschnitt (längerer Zeitraum)">
                <Input
                  type="number"
                  value={settings.ema_slow || 200}
                  onChange={(e) => setSettings({...settings, ema_slow: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="RSI Period" tip="Relative Strength Index Berechnungsfenster">
                <Input
                  type="number"
                  value={settings.rsi_period || 14}
                  onChange={(e) => setSettings({...settings, rsi_period: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="RSI Min" tip="Minimum RSI für Long Entry">
                <Input
                  type="number"
                  value={settings.rsi_min || 50}
                  onChange={(e) => setSettings({...settings, rsi_min: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="RSI Overbought" tip="RSI Level ab dem keine Longs eröffnet werden">
                <Input
                  type="number"
                  value={settings.rsi_overbought || 75}
                  onChange={(e) => setSettings({...settings, rsi_overbought: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
            </div>
          </div>

          {/* Risk Management */}
          <div className="bg-zinc-950 border border-orange-900/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-500" />Risk Management
            </h4>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Risk per Trade" tip="Max. Verlust pro Trade in % des Kapitals" unit="%">
                <Input
                  type="number" step="0.1"
                  value={(settings.risk_per_trade || 0.01) * 100}
                  onChange={(e) => setSettings({...settings, risk_per_trade: parseFloat(e.target.value) / 100})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Max Positionen" tip="Max. gleichzeitig offene Positionen">
                <Input
                  type="number"
                  value={settings.max_positions || 3}
                  onChange={(e) => setSettings({...settings, max_positions: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Max Daily Loss" tip="Bot stoppt bei diesem Tagesverlust" unit="%">
                <Input
                  type="number" step="0.5"
                  value={(settings.max_daily_loss || 0.03) * 100}
                  onChange={(e) => setSettings({...settings, max_daily_loss: parseFloat(e.target.value) / 100})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Take Profit R:R" tip="Risk-to-Reward Verhältnis für Take Profit">
                <Input
                  type="number" step="0.5"
                  value={settings.take_profit_rr || 2}
                  onChange={(e) => setSettings({...settings, take_profit_rr: parseFloat(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <Field label="Cooldown" tip="Wartezeit nach Trade (15min Kerzen)" unit="Candles">
                <Input
                  type="number"
                  value={settings.cooldown_candles || 3}
                  onChange={(e) => setSettings({...settings, cooldown_candles: parseInt(e.target.value)})}
                  className="bg-zinc-800 border-zinc-700 h-9"
                />
              </Field>
              <div className="p-3 bg-zinc-900 rounded-lg flex items-center justify-between">
                <div>
                  <Label className="text-xs text-zinc-500">ATR Stop Loss</Label>
                  <div className="text-xs text-zinc-600">Dynamischer SL</div>
                </div>
                <Switch
                  checked={settings.atr_stop}
                  onCheckedChange={(checked) => setSettings({...settings, atr_stop: checked})}
                  className="data-[state=checked]:bg-green-500"
                />
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Save Button */}
      <div className="flex justify-end pt-4 border-t border-zinc-800">
        <Button onClick={handleSave} disabled={saving} className="bg-white text-black hover:bg-gray-200 px-6">
          <Save className="w-4 h-4 mr-2" />
          {saving ? 'Speichern...' : 'Einstellungen speichern'}
        </Button>
      </div>
    </div>
  );
};

export default SettingsTab;
