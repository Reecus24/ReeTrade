import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Key, Search, Coins, TrendingUp, RefreshCw, Check, Zap, MessageCircle, Link, Unlink
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
  const [keysConnected, setKeysConnected] = useState(false);
  const [spotConnected, setSpotConnected] = useState(false);
  const [showKeysInput, setShowKeysInput] = useState(false);
  
  // Telegram State
  const [telegramStatus, setTelegramStatus] = useState({ bot_configured: false, user_linked: false });
  const [telegramCode, setTelegramCode] = useState('');
  const [linkingTelegram, setLinkingTelegram] = useState(false);
  
  // Coin Selection State
  const [availableSpotCoins, setAvailableSpotCoins] = useState([]);
  const [selectedSpotCoins, setSelectedSpotCoins] = useState([]);
  const [spotSelectAll, setSpotSelectAll] = useState(true);
  const [spotSearch, setSpotSearch] = useState('');
  const [loadingCoins, setLoadingCoins] = useState(false);
  
  // Settings
  const [settings, setSettings] = useState({
    min_notional_usdt: 10,
    max_notional_usdt: 50,
    max_positions: 5
  });

  useEffect(() => {
    fetchKeysStatus();
    fetchSettings();
    fetchTelegramStatus();
  }, []);

  useEffect(() => {
    if (keysConnected || spotConnected) {
      fetchAvailableCoins();
    }
  }, [keysConnected, spotConnected]);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/settings`, getAuthHeaders());
      const data = response.data;
      setSettings({
        min_notional_usdt: data.live_min_notional_usdt || data.min_notional_usdt || 10,
        max_notional_usdt: data.live_max_order_usdt || data.max_notional_usdt || 50,
        max_positions: data.max_positions || 5
      });
      setSelectedSpotCoins(data.selected_spot_coins || []);
      setSpotSelectAll(data.spot_trade_all !== false);
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
      setSpotConnected(response.data.connected);
    } catch (error) {}
  };

  const fetchTelegramStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/telegram/status`, getAuthHeaders());
      setTelegramStatus(response.data);
    } catch (error) {
      console.error('Telegram status error:', error);
    }
  };

  const linkTelegram = async () => {
    if (!telegramCode.trim()) {
      toast.error('Bitte Code eingeben');
      return;
    }
    
    setLinkingTelegram(true);
    try {
      await axios.post(`${BACKEND_URL}/api/telegram/link`, {
        code: telegramCode.trim()
      }, getAuthHeaders());
      
      setTelegramStatus(prev => ({ ...prev, user_linked: true }));
      setTelegramCode('');
      toast.success('TELEGRAM VERKNÜPFT!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'FEHLER BEIM VERKNÜPFEN');
    } finally {
      setLinkingTelegram(false);
    }
  };

  const unlinkTelegram = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/telegram/unlink`, {}, getAuthHeaders());
      setTelegramStatus(prev => ({ ...prev, user_linked: false }));
      toast.success('TELEGRAM GETRENNT');
    } catch (error) {
      toast.error('FEHLER');
    }
  };

  const testTelegram = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/telegram/test`, {}, getAuthHeaders());
      toast.success('TEST GESENDET');
    } catch (error) {
      toast.error('TEST FEHLGESCHLAGEN');
    }
  };

  const fetchAvailableCoins = async () => {
    setLoadingCoins(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/coins/available`, getAuthHeaders());
      setAvailableSpotCoins(response.data.spot_coins || []);
    } catch (error) {
      console.error('Coins fetch error:', error);
    } finally {
      setLoadingCoins(false);
    }
  };

  const handleSaveKeys = async () => {
    if (!mexcKeys.api_key || !mexcKeys.api_secret) {
      toast.error('BEIDE KEYS ERFORDERLICH');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${BACKEND_URL}/api/keys/mexc`, mexcKeys, getAuthHeaders());
      toast.success('MEXC KEYS GESPEICHERT');
      setMexcKeys({ api_key: '', api_secret: '' });
      setShowKeysInput(false);
      fetchKeysStatus();
    } catch (error) {
      toast.error('SPEICHERFEHLER');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${BACKEND_URL}/api/settings`, {
        selected_spot_coins: spotSelectAll ? [] : selectedSpotCoins,
        spot_trade_all: spotSelectAll,
        min_notional_usdt: settings.min_notional_usdt,
        max_notional_usdt: settings.max_notional_usdt,
        max_positions: settings.max_positions
      }, getAuthHeaders());
      toast.success('EINSTELLUNGEN GESPEICHERT');
    } catch (error) {
      toast.error('SPEICHERFEHLER');
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

  const filteredSpotCoins = availableSpotCoins.filter(coin => 
    coin.toLowerCase().includes(spotSearch.toLowerCase())
  );

  if (loading) {
    return (
      <div className="p-8 text-center">
        <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-zinc-500 font-mono-cyber text-sm">LOADING...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings-tab">
      
      {/* MEXC API Keys */}
      <div className="cyber-panel p-6 box-glow-cyan">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center bg-cyan-500/20 border border-cyan-500/50">
              <Key className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-cyan-400 tracking-widest uppercase">MEXC API Keys</h3>
              <p className="text-xs text-zinc-500 font-mono-cyber">SPOT TRADING ACCESS</p>
            </div>
          </div>
          <Badge className={`cyber-badge ${spotConnected ? 'bg-green-500/20 text-green-400 border border-green-500/50' : 'bg-red-500/20 text-red-400 border border-red-500/50'}`}>
            {spotConnected ? 'CONNECTED' : 'OFFLINE'}
          </Badge>
        </div>
        
        {!showKeysInput ? (
          <Button 
            onClick={() => setShowKeysInput(true)} 
            className="w-full cyber-btn"
            data-testid="show-keys-btn"
          >
            {spotConnected ? 'UPDATE KEYS' : 'ADD KEYS'}
          </Button>
        ) : (
          <div className="space-y-4">
            <Input
              placeholder="API Key"
              value={mexcKeys.api_key}
              onChange={(e) => setMexcKeys(prev => ({ ...prev, api_key: e.target.value }))}
              className="cyber-input"
              data-testid="api-key-input"
            />
            <Input
              type="password"
              placeholder="API Secret"
              value={mexcKeys.api_secret}
              onChange={(e) => setMexcKeys(prev => ({ ...prev, api_secret: e.target.value }))}
              className="cyber-input"
              data-testid="api-secret-input"
            />
            <div className="flex gap-3">
              <Button 
                onClick={handleSaveKeys} 
                disabled={saving} 
                className="flex-1 cyber-btn bg-green-500/10 border-green-500 text-green-400 hover:bg-green-500/20"
                data-testid="save-keys-btn"
              >
                SAVE
              </Button>
              <Button 
                onClick={() => setShowKeysInput(false)} 
                className="cyber-btn bg-red-500/10 border-red-500 text-red-400 hover:bg-red-500/20"
              >
                CANCEL
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Telegram Integration */}
      <div className="cyber-panel p-6 box-glow-purple">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
              <MessageCircle className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-purple-400 tracking-widest uppercase">Telegram</h3>
              <p className="text-xs text-zinc-500 font-mono-cyber">NOTIFICATIONS</p>
            </div>
          </div>
          <Badge className={`cyber-badge ${telegramStatus.user_linked ? 'bg-green-500/20 text-green-400 border border-green-500/50' : 'bg-zinc-500/20 text-zinc-400 border border-zinc-500/50'}`}>
            {telegramStatus.user_linked ? 'LINKED' : 'OFFLINE'}
          </Badge>
        </div>
        
        {telegramStatus.user_linked ? (
          <div className="space-y-4">
            <div className="p-4 bg-green-500/5 border border-green-500/30">
              <p className="text-sm text-green-400 flex items-center gap-2 font-mono-cyber">
                <Check className="w-4 h-4" />
                TELEGRAM ACCOUNT LINKED
              </p>
            </div>
            
            <div className="text-xs text-zinc-500 font-mono-cyber space-y-1">
              <p>BEFEHLE: /status, /profit, /balance, /trades, /ki</p>
              <p>ALERTS: Trade Open/Close, Daily Summary</p>
            </div>
            
            <div className="flex gap-3">
              <Button 
                onClick={testTelegram}
                className="flex-1 cyber-btn"
                data-testid="test-telegram-btn"
              >
                TEST MESSAGE
              </Button>
              <Button 
                onClick={unlinkTelegram}
                className="cyber-btn bg-red-500/10 border-red-500 text-red-400 hover:bg-red-500/20"
                data-testid="unlink-telegram-btn"
              >
                <Unlink className="w-4 h-4" />
              </Button>
            </div>
          </div>
        ) : telegramStatus.bot_configured ? (
          <div className="space-y-4">
            <div className="space-y-2 text-sm text-zinc-400 font-mono-cyber">
              <p>1. Öffne <strong className="text-purple-400">@ReeTrade_Bot</strong> in Telegram</p>
              <p>2. Sende <code className="text-cyan-400 bg-black/30 px-1">/link</code></p>
              <p>3. Gib den Code hier ein:</p>
            </div>
            
            <div className="flex gap-2">
              <Input
                value={telegramCode}
                onChange={(e) => setTelegramCode(e.target.value.toUpperCase())}
                placeholder="CODE EINGEBEN"
                className="flex-1 bg-black/50 border-purple-500/30 text-purple-300 font-mono text-lg tracking-widest text-center uppercase"
                maxLength={6}
                data-testid="telegram-code-input"
              />
              <Button 
                onClick={linkTelegram}
                disabled={linkingTelegram || !telegramCode.trim()}
                className="cyber-btn bg-purple-500/20 border-purple-500 text-purple-400 hover:bg-purple-500/30"
                data-testid="link-telegram-btn"
              >
                <Link className="w-4 h-4 mr-2" />
                {linkingTelegram ? '...' : 'LINK'}
              </Button>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-zinc-900/50 border border-zinc-800">
            <p className="text-xs text-zinc-600 font-mono-cyber text-center">
              TELEGRAM BOT NICHT KONFIGURIERT (Server)
            </p>
          </div>
        )}
      </div>

      {/* Trading Settings */}
      <div className="cyber-panel p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 flex items-center justify-center bg-yellow-500/20 border border-yellow-500/50">
            <Coins className="w-5 h-5 text-yellow-400" />
          </div>
          <div>
            <h3 className="font-cyber text-sm text-yellow-400 tracking-widest uppercase">Trading Config</h3>
            <p className="text-xs text-zinc-500 font-mono-cyber">SYSTEM PARAMETERS</p>
          </div>
        </div>
        
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs text-zinc-500 mb-2 font-mono-cyber">MIN ORDER (USDT)</label>
            <Input
              type="number"
              value={settings.min_notional_usdt || 10}
              onChange={(e) => setSettings(prev => ({ ...prev, min_notional_usdt: parseFloat(e.target.value) || 10 }))}
              className="cyber-input"
              data-testid="min-order-input"
            />
          </div>
          
          <div>
            <label className="block text-xs text-zinc-500 mb-2 font-mono-cyber">MAX ORDER (USDT)</label>
            <Input
              type="number"
              value={settings.max_notional_usdt || 50}
              onChange={(e) => setSettings(prev => ({ ...prev, max_notional_usdt: parseFloat(e.target.value) || 50 }))}
              className="cyber-input"
              data-testid="max-order-input"
            />
          </div>
          
          <div>
            <label className="block text-xs text-zinc-500 mb-2 font-mono-cyber">MAX POSITIONS</label>
            <Input
              type="number"
              value={settings.max_positions || 5}
              onChange={(e) => setSettings(prev => ({ ...prev, max_positions: parseInt(e.target.value) || 5 }))}
              className="cyber-input"
              data-testid="max-positions-input"
            />
          </div>
        </div>
        
        <div className="p-4 bg-cyan-500/5 border border-cyan-500/20">
          <p className="text-xs text-cyan-400 font-mono-cyber">
            <Zap className="w-3 h-3 inline mr-1" />
            RL-KI berechnet Position Size automatisch zwischen MIN und MAX | Keine doppelten Coins
          </p>
        </div>
      </div>

      {/* SPOT Coin Selection */}
      <div className="cyber-panel p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center bg-green-500/20 border border-green-500/50">
              <TrendingUp className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-green-400 tracking-widest uppercase">SPOT Coins</h3>
              <p className="text-xs text-zinc-500 font-mono-cyber">TRADABLE ASSETS</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-500 font-mono-cyber">TRADE ALL</span>
            <Switch
              checked={spotSelectAll}
              onCheckedChange={setSpotSelectAll}
              data-testid="spot-select-all-toggle"
            />
          </div>
        </div>
        
        {!spotSelectAll && (
          <>
            <div className="flex items-center gap-2 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-600" />
                <Input
                  placeholder="SEARCH COIN..."
                  value={spotSearch}
                  onChange={(e) => setSpotSearch(e.target.value)}
                  className="cyber-input pl-10"
                  data-testid="spot-search-input"
                />
              </div>
              <Button 
                className="cyber-btn"
                onClick={fetchAvailableCoins}
                disabled={loadingCoins}
              >
                <RefreshCw className={`w-4 h-4 ${loadingCoins ? 'animate-spin' : ''}`} />
              </Button>
            </div>
            
            <ScrollArea className="h-48 border border-cyan-500/20 bg-black/50 p-2">
              {loadingCoins ? (
                <div className="text-center text-zinc-600 py-8 font-mono-cyber">LOADING...</div>
              ) : filteredSpotCoins.length === 0 ? (
                <div className="text-center text-zinc-600 py-8 font-mono-cyber">
                  {keysConnected ? 'NO COINS FOUND' : 'CONNECT API KEYS FIRST'}
                </div>
              ) : (
                <div className="grid grid-cols-4 gap-2">
                  {filteredSpotCoins.map(coin => (
                    <div
                      key={coin}
                      onClick={() => toggleSpotCoin(coin)}
                      className={`p-2 cursor-pointer text-xs font-mono transition-all ${
                        selectedSpotCoins.includes(coin)
                          ? 'bg-green-500/20 border border-green-500 text-green-400'
                          : 'bg-zinc-900 border border-zinc-800 text-zinc-500 hover:border-cyan-500/50'
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
            
            <p className="mt-2 text-xs text-zinc-600 font-mono-cyber">
              {selectedSpotCoins.length} / {availableSpotCoins.length} SELECTED
            </p>
          </>
        )}
        
        {spotSelectAll && (
          <div className="p-4 bg-green-500/5 border border-green-500/20 text-center">
            <p className="text-green-400 font-mono-cyber text-sm">
              RL-KI TRADES ALL AVAILABLE SPOT COINS ({availableSpotCoins.length || '~100'})
            </p>
          </div>
        )}
      </div>

      {/* Save Button */}
      <Button 
        onClick={handleSaveSettings} 
        disabled={saving} 
        className="w-full cyber-btn bg-cyan-500/10 border-cyan-500 text-cyan-400 hover:bg-cyan-500/20 py-4"
        data-testid="save-settings-btn"
      >
        {saving ? 'SAVING...' : 'SAVE CONFIGURATION'}
      </Button>
    </div>
  );
};

export default SettingsTab;
