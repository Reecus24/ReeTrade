import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { 
  Activity, Save, Key, Wallet, DollarSign, Shield, TrendingUp, 
  AlertTriangle, HelpCircle, Info 
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

// Tooltip Component
const Tooltip = ({ text }) => (
  <div className="group relative inline-block ml-1">
    <HelpCircle className="w-3.5 h-3.5 text-zinc-600 cursor-help" />
    <div className="absolute z-50 hidden group-hover:block w-64 p-2 bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-300 shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-1">
      {text}
    </div>
  </div>
);

// Setting Card Component
const SettingCard = ({ label, tooltip, children, highlight }) => (
  <div className={`p-3 rounded-lg ${highlight ? 'bg-blue-950/30 border border-blue-900/30' : 'bg-zinc-900'}`}>
    <Label className={`flex items-center text-sm ${highlight ? 'text-blue-400' : 'text-zinc-400'}`}>
      {label}
      {tooltip && <Tooltip text={tooltip} />}
    </Label>
    <div className="mt-2">{children}</div>
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
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 text-zinc-600 animate-spin" />
      </div>
    );
  }

  if (!settings) return null;

  return (
    <div className="space-y-6" data-testid="settings-tab">
      {/* Budget & Reserve System */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <Shield className="w-6 h-6 text-blue-500" />
          <h3 className="text-lg font-semibold">Budget & Reserve System</h3>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          Schütze dein Wallet vor Übertrading. Der Bot kann nie mehr als erlaubt verwenden.
        </p>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SettingCard 
            label="Reserve (USDT)" 
            tooltip="Sicherheitsreserve die der Bot NIEMALS antastet. Wird vom verfügbaren Guthaben abgezogen bevor der Bot handeln kann."
            highlight
          >
            <Input
              type="number"
              step="100"
              value={settings.reserve_usdt || 0}
              onChange={(e) => setSettings({...settings, reserve_usdt: parseFloat(e.target.value) || 0})}
              className="bg-zinc-800 border-blue-900/50 text-white"
            />
            <div className="text-xs text-blue-600 mt-1">Haupt-Schutz für dein Wallet</div>
          </SettingCard>
          
          <SettingCard 
            label="Trading Budget (USDT)" 
            tooltip="Maximales Gesamt-Exposure. Der Bot hält nie mehr als diesen Betrag in offenen Positionen."
          >
            <Input
              type="number"
              step="50"
              value={settings.trading_budget_usdt || 500}
              onChange={(e) => setSettings({...settings, trading_budget_usdt: parseFloat(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Max. Gesamt-Exposure</div>
          </SettingCard>
          
          <SettingCard 
            label="Paper Start Balance (USDT)" 
            tooltip="Startkapital für den Paper Trading Modus. Simuliert dein verfügbares Kapital."
          >
            <Input
              type="number"
              step="100"
              value={settings.paper_start_balance_usdt || 500}
              onChange={(e) => setSettings({...settings, paper_start_balance_usdt: parseFloat(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Nur für Paper Mode</div>
          </SettingCard>
          
          <SettingCard 
            label="Max Order Size (USDT)" 
            tooltip="Maximale Größe einer einzelnen Order. Begrenzt das Risiko pro Trade."
          >
            <Input
              type="number"
              step="10"
              value={settings.max_order_notional_usdt || 50}
              onChange={(e) => setSettings({...settings, max_order_notional_usdt: parseFloat(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Pro einzelnem Trade</div>
          </SettingCard>
        </div>
        
        <div className="mt-4 p-3 bg-zinc-900 rounded-lg">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-zinc-500 mt-0.5" />
            <div className="text-xs text-zinc-500">
              <strong>Formel (Live):</strong> Available to Bot = min(USDT_Free - Reserve, Trading Budget - Used Budget)
            </div>
          </div>
        </div>
      </div>

      {/* Trading Fees & Costs */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <DollarSign className="w-6 h-6 text-yellow-500" />
          <h3 className="text-lg font-semibold">Gebühren & Slippage</h3>
          <Badge className="bg-yellow-500/10 text-yellow-500 text-xs">Paper Simulation</Badge>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          Diese Kosten werden bei Paper-Trades simuliert für realistische PnL-Berechnung.
        </p>
        
        <div className="grid grid-cols-3 gap-4">
          <SettingCard 
            label="Trading Fee (BPS)" 
            tooltip="BPS = Basis Points. 10 BPS = 0.10% = 1 USDT pro 1000 USDT Ordervolumen. MEXC Standardgebühr liegt bei 10 BPS."
          >
            <Input
              type="number"
              value={settings.fee_bps || 10}
              onChange={(e) => setSettings({...settings, fee_bps: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">10 BPS = 0.10%</div>
          </SettingCard>
          
          <SettingCard 
            label="Slippage (BPS)" 
            tooltip="Slippage = Preisabweichung zwischen Order und Ausführung. Bei Market Orders typisch 5-20 BPS."
          >
            <Input
              type="number"
              value={settings.slippage_bps || 5}
              onChange={(e) => setSettings({...settings, slippage_bps: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">5 BPS = 0.05%</div>
          </SettingCard>
          
          <SettingCard 
            label="Min. Order Size (USDT)" 
            tooltip="Minimale Ordergröße. Orders unter diesem Wert werden nicht ausgeführt (MEXC Minimum oft 5-10 USDT)."
          >
            <Input
              type="number"
              step="1"
              value={settings.min_notional_usdt || 10}
              onChange={(e) => setSettings({...settings, min_notional_usdt: parseFloat(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Exchange Minimum</div>
          </SettingCard>
        </div>
      </div>

      {/* Strategy Parameters */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <TrendingUp className="w-6 h-6 text-green-500" />
          <h3 className="text-lg font-semibold">Strategie-Parameter</h3>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          EMA Crossover Strategie mit RSI Filter. Der Bot kauft wenn EMA Fast über EMA Slow kreuzt und RSI Bedingungen erfüllt sind.
        </p>
        
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <SettingCard 
            label="EMA Fast" 
            tooltip="Exponential Moving Average (schnell). Kürzerer Zeitraum = reagiert schneller auf Preisänderungen. Standard: 50 Perioden."
          >
            <Input
              type="number"
              value={settings.ema_fast}
              onChange={(e) => setSettings({...settings, ema_fast: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Perioden (schnell)</div>
          </SettingCard>
          
          <SettingCard 
            label="EMA Slow" 
            tooltip="Exponential Moving Average (langsam). Längerer Zeitraum = glatter, zeigt Haupttrend. Standard: 200 Perioden."
          >
            <Input
              type="number"
              value={settings.ema_slow}
              onChange={(e) => setSettings({...settings, ema_slow: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Perioden (langsam)</div>
          </SettingCard>
          
          <SettingCard 
            label="RSI Periode" 
            tooltip="RSI = Relative Strength Index. Misst Stärke von Preisbewegungen. Standard: 14 Perioden."
          >
            <Input
              type="number"
              value={settings.rsi_period}
              onChange={(e) => setSettings({...settings, rsi_period: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Berechnungs-Fenster</div>
          </SettingCard>
          
          <SettingCard 
            label="RSI Minimum" 
            tooltip="Minimaler RSI Wert für Long-Entry. RSI unter 30 = überverkauft, über 70 = überkauft. Standard: 50 (neutraler Bereich)."
          >
            <Input
              type="number"
              value={settings.rsi_min}
              onChange={(e) => setSettings({...settings, rsi_min: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Min. für Entry</div>
          </SettingCard>
          
          <SettingCard 
            label="RSI Overbought" 
            tooltip="RSI Level ab dem keine neuen Longs eröffnet werden (überkauft). Standard: 75."
          >
            <Input
              type="number"
              value={settings.rsi_overbought}
              onChange={(e) => setSettings({...settings, rsi_overbought: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Überkauft-Level</div>
          </SettingCard>
        </div>
      </div>

      {/* Risk Management */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <AlertTriangle className="w-6 h-6 text-orange-500" />
          <h3 className="text-lg font-semibold">Risk Management</h3>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          Kontrolliere dein Risiko pro Trade und insgesamt. Diese Einstellungen schützen dein Kapital.
        </p>
        
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <SettingCard 
            label="Risk per Trade (%)" 
            tooltip="Maximaler Verlust pro Trade in % des Kapitals. Bei 1% und 10.000$ Kapital = max. 100$ Verlust pro Trade."
          >
            <Input
              type="number"
              step="0.1"
              value={settings.risk_per_trade * 100}
              onChange={(e) => setSettings({...settings, risk_per_trade: parseFloat(e.target.value) / 100})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Standard: 1%</div>
          </SettingCard>
          
          <SettingCard 
            label="Max. Positionen" 
            tooltip="Maximale Anzahl gleichzeitig offener Positionen. Begrenzt Gesamtrisiko und Margin-Nutzung."
          >
            <Input
              type="number"
              value={settings.max_positions}
              onChange={(e) => setSettings({...settings, max_positions: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Gleichzeitig offen</div>
          </SettingCard>
          
          <SettingCard 
            label="Max. Daily Loss (%)" 
            tooltip="Maximaler Tagesverlust in % des Startkapitals. Bot stoppt automatisch wenn erreicht."
          >
            <Input
              type="number"
              step="0.5"
              value={settings.max_daily_loss * 100}
              onChange={(e) => setSettings({...settings, max_daily_loss: parseFloat(e.target.value) / 100})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Stoppt Bot bei Erreichen</div>
          </SettingCard>
          
          <SettingCard 
            label="Take Profit (R:R)" 
            tooltip="Risk-to-Reward Verhältnis für Take Profit. Bei 2:1 und 100$ Risiko = 200$ Gewinnziel."
          >
            <Input
              type="number"
              step="0.5"
              value={settings.take_profit_rr}
              onChange={(e) => setSettings({...settings, take_profit_rr: parseFloat(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">Verhältnis Risiko:Gewinn</div>
          </SettingCard>
          
          <SettingCard 
            label="Cooldown (Candles)" 
            tooltip="Wartezeit nach einem Trade bevor der nächste Trade erlaubt ist. Verhindert Overtrading."
          >
            <Input
              type="number"
              value={settings.cooldown_candles}
              onChange={(e) => setSettings({...settings, cooldown_candles: parseInt(e.target.value)})}
              className="bg-zinc-800 border-zinc-700 text-white"
            />
            <div className="text-xs text-zinc-600 mt-1">15min Kerzen</div>
          </SettingCard>
          
          <div className="p-3 bg-zinc-900 rounded-lg flex items-center justify-between">
            <div>
              <Label className="text-zinc-400 flex items-center">
                ATR Stop Loss
                <Tooltip text="Verwendet Average True Range für dynamischen Stop Loss. Passt sich an Volatilität an." />
              </Label>
              <div className="text-xs text-zinc-600 mt-1">Dynamischer SL</div>
            </div>
            <Switch
              checked={settings.atr_stop}
              onCheckedChange={(checked) => setSettings({...settings, atr_stop: checked})}
              className="data-[state=checked]:bg-green-500"
            />
          </div>
        </div>
      </div>

      {/* MEXC API Keys */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Key className="w-6 h-6 text-purple-500" />
            <h3 className="text-lg font-semibold">MEXC API Keys</h3>
          </div>
          <Badge className={keysConnected ? 'bg-green-500/10 text-green-500' : 'bg-zinc-800 text-zinc-500'}>
            {keysConnected ? 'Verbunden' : 'Nicht konfiguriert'}
          </Badge>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          Verbinde dein MEXC Konto für Live Trading. Keys werden verschlüsselt gespeichert.
        </p>

        {!showKeysInput ? (
          <Button
            onClick={() => setShowKeysInput(true)}
            className="bg-zinc-900 text-white border border-zinc-800 hover:bg-zinc-800"
          >
            {keysConnected ? 'Keys aktualisieren' : 'Keys hinzufügen'}
          </Button>
        ) : (
          <div className="space-y-4 max-w-md">
            <div>
              <Label className="text-zinc-400">API Key</Label>
              <Input
                type="password"
                value={mexcKeys.api_key}
                onChange={(e) => setMexcKeys({...mexcKeys, api_key: e.target.value})}
                placeholder="mx0v..."
                className="mt-2 bg-zinc-900 border-zinc-800 text-white"
              />
            </div>
            <div>
              <Label className="text-zinc-400">API Secret</Label>
              <Input
                type="password"
                value={mexcKeys.api_secret}
                onChange={(e) => setMexcKeys({...mexcKeys, api_secret: e.target.value})}
                placeholder="••••••••"
                className="mt-2 bg-zinc-900 border-zinc-800 text-white"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleSaveKeys} disabled={saving} className="bg-purple-600 hover:bg-purple-700 text-white">
                Keys speichern
              </Button>
              <Button onClick={() => setShowKeysInput(false)} variant="ghost" className="text-zinc-400">
                Abbrechen
              </Button>
            </div>
            <p className="text-xs text-zinc-500 flex items-center gap-1">
              <Shield className="w-3 h-3" />
              Keys werden mit AES-256 verschlüsselt und niemals angezeigt
            </p>
          </div>
        )}
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={saving}
          className="bg-white text-black hover:bg-gray-200 font-medium px-6"
        >
          <Save className="w-4 h-4 mr-2" />
          {saving ? 'Speichern...' : 'Alle Einstellungen speichern'}
        </Button>
      </div>
    </div>
  );
};

export default SettingsTab;
