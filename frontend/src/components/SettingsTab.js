import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Key, Search, Coins, TrendingUp, TrendingDown, RefreshCw, Check, X
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

const SettingsTab = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [mexcKeys, setMexcKeys] = useState({ api_key: '', api_secret: '' });
  const [futuresKeys, setFuturesKeys] = useState({ api_key: '', api_secret: '' });
  const [keysConnected, setKeysConnected] = useState(false);
  const [spotConnected, setSpotConnected] = useState(false);
  const [futuresConnected, setFuturesConnected] = useState(false);
  const [showKeysInput, setShowKeysInput] = useState(false);
  const [showFuturesKeysInput, setShowFuturesKeysInput] = useState(false);
  
  // Coin Selection State
  const [availableSpotCoins, setAvailableSpotCoins] = useState([]);
  const [availableFuturesCoins, setAvailableFuturesCoins] = useState([]);
  const [selectedSpotCoins, setSelectedSpotCoins] = useState([]);
  const [selectedFuturesCoins, setSelectedFuturesCoins] = useState([]);
  const [spotSelectAll, setSpotSelectAll] = useState(true);
  const [futuresSelectAll, setFuturesSelectAll] = useState(true);
  const [spotSearch, setSpotSearch] = useState('');
  const [futuresSearch, setFuturesSearch] = useState('');
  const [loadingCoins, setLoadingCoins] = useState(false);
  
  // Settings
  const [settings, setSettings] = useState({
    min_notional_usdt: 10,
    max_positions: 5
  });

  useEffect(() => {
    fetchKeysStatus();
    fetchSettings();
  }, []);

  useEffect(() => {
    if (keysConnected || spotConnected) {
      fetchAvailableCoins();
    }
  }, [keysConnected, spotConnected]);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/settings`, getAuthHeaders());
      setSettings(response.data);
      setSelectedSpotCoins(response.data.selected_spot_coins || []);
      setSelectedFuturesCoins(response.data.selected_futures_coins || []);
      setSpotSelectAll(response.data.spot_trade_all !== false);
      setFuturesSelectAll(response.data.futures_trade_all !== false);
    } catch (error) {
      console.error('Settings fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchKeysStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/keys/mexc/status`, getAuthHeaders());
      setKeysConnected(response.data.connected);
      setSpotConnected(response.data.spot_connected || response.data.connected);
      setFuturesConnected(response.data.futures_connected || false);
    } catch (error) {}
  };

  const fetchAvailableCoins = async () => {
    setLoadingCoins(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/coins/available`, getAuthHeaders());
      setAvailableSpotCoins(response.data.spot_coins || []);
      setAvailableFuturesCoins(response.data.futures_coins || []);
    } catch (error) {
      console.error('Coins fetch error:', error);
      toast.error('Fehler beim Laden der Coins');
    } finally {
      setLoadingCoins(false);
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
      toast.success('MEXC SPOT Keys gespeichert');
      setMexcKeys({ api_key: '', api_secret: '' });
      setShowKeysInput(false);
      fetchKeysStatus();
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveFuturesKeys = async () => {
    if (!futuresKeys.api_key || !futuresKeys.api_secret) {
      toast.error('Bitte beide Futures Keys eingeben');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${BACKEND_URL}/api/keys/mexc/futures`, futuresKeys, getAuthHeaders());
      toast.success('MEXC FUTURES Keys gespeichert');
      setFuturesKeys({ api_key: '', api_secret: '' });
      setShowFuturesKeysInput(false);
      fetchKeysStatus();
    } catch (error) {
      toast.error('Fehler beim Speichern der Futures Keys');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${BACKEND_URL}/api/settings`, {
        selected_spot_coins: spotSelectAll ? [] : selectedSpotCoins,
        selected_futures_coins: futuresSelectAll ? [] : selectedFuturesCoins,
        spot_trade_all: spotSelectAll,
        futures_trade_all: futuresSelectAll,
        min_notional_usdt: settings.min_notional_usdt,
        max_positions: settings.max_positions
      }, getAuthHeaders());
      toast.success('Einstellungen gespeichert');
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  };

  const toggleSpotCoin = (coin) => {
    setSelectedSpotCoins(prev => 
      prev.includes(coin) 
        ? prev.filter(c => c !== coin)
        : [...prev, coin]
    );
  };

  const toggleFuturesCoin = (coin) => {
    setSelectedFuturesCoins(prev => 
      prev.includes(coin) 
        ? prev.filter(c => c !== coin)
        : [...prev, coin]
    );
  };

  const filteredSpotCoins = availableSpotCoins.filter(coin => 
    coin.toLowerCase().includes(spotSearch.toLowerCase())
  );

  const filteredFuturesCoins = availableFuturesCoins.filter(coin => 
    coin.toLowerCase().includes(futuresSearch.toLowerCase())
  );

  if (loading) {
    return <div className="p-4 text-center text-zinc-500">Laden...</div>;
  }

  return (
    <div className="space-y-6" data-testid="settings-tab">
      {/* MEXC API Keys */}
      <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Key className="w-5 h-5 text-blue-500" />
            MEXC SPOT API Keys
          </h3>
          <Badge className={spotConnected ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}>
            {spotConnected ? 'Verbunden' : 'Nicht konfiguriert'}
          </Badge>
        </div>
        
        {!showKeysInput ? (
          <Button 
            onClick={() => setShowKeysInput(true)} 
            variant="outline" 
            className="w-full"
            data-testid="show-keys-btn"
          >
            {spotConnected ? 'SPOT Keys aktualisieren' : 'SPOT Keys hinzufügen'}
          </Button>
        ) : (
          <div className="space-y-3">
            <Input
              placeholder="API Key"
              value={mexcKeys.api_key}
              onChange={(e) => setMexcKeys(prev => ({ ...prev, api_key: e.target.value }))}
              className="bg-zinc-900 border-zinc-700"
              data-testid="api-key-input"
            />
            <Input
              type="password"
              placeholder="API Secret"
              value={mexcKeys.api_secret}
              onChange={(e) => setMexcKeys(prev => ({ ...prev, api_secret: e.target.value }))}
              className="bg-zinc-900 border-zinc-700"
              data-testid="api-secret-input"
            />
            <div className="flex gap-2">
              <Button 
                onClick={handleSaveKeys} 
                disabled={saving} 
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                data-testid="save-keys-btn"
              >
                Speichern
              </Button>
              <Button onClick={() => setShowKeysInput(false)} variant="outline">
                Abbrechen
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* MEXC FUTURES API Keys - Separate */}
      <div className="p-4 bg-zinc-950 border border-purple-900/50 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Key className="w-5 h-5 text-purple-500" />
            MEXC FUTURES API Keys
            <span className="text-xs text-zinc-500">(separater Key)</span>
          </h3>
          <Badge className={futuresConnected ? 'bg-green-500/10 text-green-500' : 'bg-yellow-500/10 text-yellow-500'}>
            {futuresConnected ? 'Verbunden' : 'Nicht konfiguriert'}
          </Badge>
        </div>
        
        <p className="text-sm text-zinc-400 mb-3">
          Für Futures-Trading benötigst du einen separaten API-Key mit <strong>Futures-Berechtigung</strong>.
        </p>
        
        {!showFuturesKeysInput ? (
          <Button 
            onClick={() => setShowFuturesKeysInput(true)} 
            variant="outline" 
            className="w-full border-purple-800 hover:bg-purple-900/20"
            data-testid="show-futures-keys-btn"
          >
            {futuresConnected ? 'FUTURES Keys aktualisieren' : 'FUTURES Keys hinzufügen'}
          </Button>
        ) : (
          <div className="space-y-3">
            <Input
              placeholder="Futures API Key"
              value={futuresKeys.api_key}
              onChange={(e) => setFuturesKeys(prev => ({ ...prev, api_key: e.target.value }))}
              className="bg-zinc-900 border-purple-800"
              data-testid="futures-api-key-input"
            />
            <Input
              type="password"
              placeholder="Futures API Secret"
              value={futuresKeys.api_secret}
              onChange={(e) => setFuturesKeys(prev => ({ ...prev, api_secret: e.target.value }))}
              className="bg-zinc-900 border-purple-800"
              data-testid="futures-api-secret-input"
            />
            <div className="flex gap-2">
              <Button 
                onClick={handleSaveFuturesKeys} 
                disabled={saving} 
                className="flex-1 bg-purple-600 hover:bg-purple-700"
                data-testid="save-futures-keys-btn"
              >
                Futures Keys speichern
              </Button>
              <Button onClick={() => setShowFuturesKeysInput(false)} variant="outline">
                Abbrechen
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Basic Settings */}
      <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
          <Coins className="w-5 h-5 text-yellow-500" />
          Trading Einstellungen
        </h3>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-zinc-400 mb-1 block">Min Order (USDT)</label>
            <Input
              type="number"
              value={settings.min_notional_usdt || 10}
              onChange={(e) => setSettings(prev => ({ ...prev, min_notional_usdt: parseFloat(e.target.value) || 10 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
              data-testid="min-order-input"
            />
            <p className="text-xs text-zinc-500 mt-1">Minimale Order-Größe</p>
          </div>
          
          <div>
            <label className="text-sm text-zinc-400 mb-1 block">Max Positionen</label>
            <Input
              type="number"
              value={settings.max_positions || 5}
              onChange={(e) => setSettings(prev => ({ ...prev, max_positions: parseInt(e.target.value) || 5 }))}
              className="bg-zinc-800 border-zinc-700 font-mono"
              data-testid="max-positions-input"
            />
            <p className="text-xs text-zinc-500 mt-1">Gleichzeitig offene Positionen</p>
          </div>
        </div>
        
        <div className="mt-4 p-3 bg-blue-950/30 border border-blue-900/30 rounded-lg">
          <p className="text-sm text-blue-300">
            💡 <strong>Position Sizing:</strong> Die KI berechnet automatisch die optimale Position als % deines <strong>Gesamt-Portfolios</strong> (nicht mehr vom Budget).
          </p>
        </div>
      </div>

      {/* SPOT Coin Selection */}
      <div className="p-4 bg-zinc-950 border border-green-900/30 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-500" />
            SPOT Coins
          </h3>
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-400">Alle handeln</span>
            <Switch
              checked={spotSelectAll}
              onCheckedChange={setSpotSelectAll}
              data-testid="spot-select-all-toggle"
            />
          </div>
        </div>
        
        {!spotSelectAll && (
          <>
            <div className="flex items-center gap-2 mb-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder="Coin suchen..."
                  value={spotSearch}
                  onChange={(e) => setSpotSearch(e.target.value)}
                  className="pl-9 bg-zinc-900 border-zinc-700"
                  data-testid="spot-search-input"
                />
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={fetchAvailableCoins}
                disabled={loadingCoins}
              >
                <RefreshCw className={`w-4 h-4 ${loadingCoins ? 'animate-spin' : ''}`} />
              </Button>
            </div>
            
            <ScrollArea className="h-48 border border-zinc-800 rounded-lg p-2">
              {loadingCoins ? (
                <div className="text-center text-zinc-500 py-8">Lade Coins...</div>
              ) : filteredSpotCoins.length === 0 ? (
                <div className="text-center text-zinc-500 py-8">
                  {keysConnected ? 'Keine Coins gefunden' : 'Bitte erst API Keys verbinden'}
                </div>
              ) : (
                <div className="grid grid-cols-4 gap-2">
                  {filteredSpotCoins.map(coin => (
                    <div
                      key={coin}
                      onClick={() => toggleSpotCoin(coin)}
                      className={`p-2 rounded cursor-pointer text-sm font-mono transition-all ${
                        selectedSpotCoins.includes(coin)
                          ? 'bg-green-900/50 border border-green-500 text-green-400'
                          : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:border-zinc-600'
                      }`}
                      data-testid={`spot-coin-${coin}`}
                    >
                      <div className="flex items-center justify-between">
                        <span>{coin.replace('USDT', '')}</span>
                        {selectedSpotCoins.includes(coin) && <Check className="w-3 h-3" />}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
            
            <div className="mt-2 text-sm text-zinc-500">
              {selectedSpotCoins.length} von {availableSpotCoins.length} Coins ausgewählt
            </div>
          </>
        )}
        
        {spotSelectAll && (
          <div className="p-3 bg-green-950/30 rounded-lg text-center">
            <p className="text-green-400">
              ✅ Bot handelt mit <strong>ALLEN</strong> verfügbaren SPOT Coins ({availableSpotCoins.length || '~100'})
            </p>
          </div>
        )}
      </div>

      {/* FUTURES Coin Selection */}
      <div className="p-4 bg-zinc-950 border border-orange-900/30 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-orange-500" />
            FUTURES Coins (Hebel)
          </h3>
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-400">Alle handeln</span>
            <Switch
              checked={futuresSelectAll}
              onCheckedChange={setFuturesSelectAll}
              data-testid="futures-select-all-toggle"
            />
          </div>
        </div>
        
        {!futuresSelectAll && (
          <>
            <div className="flex items-center gap-2 mb-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder="Coin suchen..."
                  value={futuresSearch}
                  onChange={(e) => setFuturesSearch(e.target.value)}
                  className="pl-9 bg-zinc-900 border-zinc-700"
                  data-testid="futures-search-input"
                />
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={fetchAvailableCoins}
                disabled={loadingCoins}
              >
                <RefreshCw className={`w-4 h-4 ${loadingCoins ? 'animate-spin' : ''}`} />
              </Button>
            </div>
            
            <ScrollArea className="h-48 border border-zinc-800 rounded-lg p-2">
              {loadingCoins ? (
                <div className="text-center text-zinc-500 py-8">Lade Coins...</div>
              ) : filteredFuturesCoins.length === 0 ? (
                <div className="text-center text-zinc-500 py-8">
                  {keysConnected ? 'Keine Futures Coins gefunden' : 'Bitte erst API Keys verbinden'}
                </div>
              ) : (
                <div className="grid grid-cols-4 gap-2">
                  {filteredFuturesCoins.map(coin => (
                    <div
                      key={coin}
                      onClick={() => toggleFuturesCoin(coin)}
                      className={`p-2 rounded cursor-pointer text-sm font-mono transition-all ${
                        selectedFuturesCoins.includes(coin)
                          ? 'bg-orange-900/50 border border-orange-500 text-orange-400'
                          : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:border-zinc-600'
                      }`}
                      data-testid={`futures-coin-${coin}`}
                    >
                      <div className="flex items-center justify-between">
                        <span>{coin.replace('_USDT', '')}</span>
                        {selectedFuturesCoins.includes(coin) && <Check className="w-3 h-3" />}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
            
            <div className="mt-2 text-sm text-zinc-500">
              {selectedFuturesCoins.length} von {availableFuturesCoins.length} Coins ausgewählt
            </div>
          </>
        )}
        
        {futuresSelectAll && (
          <div className="p-3 bg-orange-950/30 rounded-lg text-center">
            <p className="text-orange-400">
              ✅ Bot handelt mit <strong>ALLEN</strong> verfügbaren FUTURES Coins ({availableFuturesCoins.length || '~50'})
            </p>
          </div>
        )}
      </div>

      {/* Save Button */}
      <Button 
        onClick={handleSaveSettings} 
        disabled={saving} 
        className="w-full bg-blue-600 hover:bg-blue-700"
        data-testid="save-settings-btn"
      >
        {saving ? 'Speichern...' : 'Einstellungen speichern'}
      </Button>
    </div>
  );
};

export default SettingsTab;
