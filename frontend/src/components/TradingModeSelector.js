import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Bot, User, Shield, TrendingUp, Zap, AlertTriangle, Info, Wallet, Target, Activity } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

const PROFILE_ICONS = {
  manual: User,
  ai_conservative: Shield,
  ai_moderate: TrendingUp,
  ai_aggressive: Zap
};

const PROFILE_COLORS = {
  manual: 'text-blue-500',
  ai_conservative: 'text-green-500',
  ai_moderate: 'text-yellow-500',
  ai_aggressive: 'text-red-500'
};

const TradingModeSelector = ({ currentMode, onModeChange, aiStatus }) => {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [previewData, setPreviewData] = useState(null);

  useEffect(() => {
    fetchProfiles();
  }, []);

  // Fetch AI preview when mode changes
  useEffect(() => {
    if (currentMode) {
      fetchAIPreview(currentMode);
    }
  }, [currentMode]);

  const fetchProfiles = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/ai/profiles`, getAuthHeaders());
      setProfiles(response.data.profiles || []);
    } catch (error) {
      console.error('Failed to fetch AI profiles:', error);
    }
  };

  const fetchAIPreview = async (mode) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/ai/preview/${mode}`, getAuthHeaders());
      setPreviewData(response.data);
    } catch (error) {
      console.error('Failed to fetch AI preview:', error);
    }
  };

  const handleModeChange = async (newMode) => {
    setLoading(true);
    try {
      // First fetch preview to show immediately
      await fetchAIPreview(newMode);
      
      // Then save to backend
      await axios.put(`${BACKEND_URL}/api/settings`, { trading_mode: newMode }, getAuthHeaders());
      
      const profile = profiles.find(p => p.mode === newMode);
      toast.success(`Trading Modus: ${profile?.name || newMode}`);
      onModeChange(newMode);
    } catch (error) {
      toast.error('Fehler beim Ändern des Modus');
    } finally {
      setLoading(false);
    }
  };

  const isAiMode = currentMode && currentMode !== 'manual';
  const CurrentIcon = PROFILE_ICONS[currentMode] || User;
  const currentProfile = profiles.find(p => p.mode === currentMode);

  // Use preview data if available, otherwise fall back to aiStatus
  const displayData = previewData || {
    position_pct_range: aiStatus?.position_pct_range || '0%',
    position_usd_min: aiStatus?.min_position || 0,
    position_usd_max: aiStatus?.max_position || 0,
    usdt_free: aiStatus?.usdt_free || 0,
    trading_budget_remaining: aiStatus?.trading_budget_remaining || 0,
    confidence: aiStatus?.confidence || 0,
    risk_score: aiStatus?.risk_score || 0,
    reasoning: aiStatus?.reasoning || [],
    sl_atr_multiplier: aiStatus?.sl_atr_multiplier || '',
    tp_rr_range: aiStatus?.tp_rr_range || '',
    max_positions: aiStatus?.max_positions || 0
  };

  return (
    <div className="space-y-3">
      {/* Mode Selector */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <CurrentIcon className={`w-5 h-5 ${PROFILE_COLORS[currentMode] || 'text-zinc-400'}`} />
          <span className="text-sm font-medium text-zinc-400">Trading Modus:</span>
        </div>
        
        <Select value={currentMode || 'manual'} onValueChange={handleModeChange} disabled={loading}>
          <SelectTrigger className="w-56 bg-zinc-900 border-zinc-700">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {profiles.map((profile) => {
              const Icon = PROFILE_ICONS[profile.mode] || User;
              return (
                <SelectItem key={profile.mode} value={profile.mode}>
                  <div className="flex items-center gap-2">
                    <span>{profile.emoji || ''}</span>
                    <Icon className={`w-4 h-4 ${PROFILE_COLORS[profile.mode]}`} />
                    <span>{profile.name}</span>
                    {profile.position_pct_range && profile.position_pct_range !== 'Manuell' && (
                      <span className="text-xs text-zinc-500 ml-2">
                        ({profile.position_pct_range})
                      </span>
                    )}
                  </div>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
        
        {isAiMode && (
          <Badge className="bg-purple-500/20 text-purple-400 border-0">
            <Bot className="w-3 h-3 mr-1" />
            AI Active
          </Badge>
        )}
        
        <button 
          onClick={() => setShowDetails(!showDetails)}
          className="text-zinc-500 hover:text-zinc-300"
        >
          <Info className="w-4 h-4" />
        </button>
      </div>
      
      {/* Profile Details */}
      {showDetails && currentProfile && (
        <div className="p-3 bg-zinc-900/50 rounded-lg border border-zinc-800">
          <div className="text-sm text-zinc-400 mb-2">{currentProfile.description}</div>
          <div className="flex flex-wrap gap-2">
            {currentProfile.features?.map((feature, idx) => (
              <Badge key={idx} variant="outline" className="text-xs bg-zinc-800 border-zinc-700">
                {feature}
              </Badge>
            ))}
          </div>
        </div>
      )}
      
      {/* AI Status Panel - always show when AI mode or previewData available */}
      {(isAiMode || previewData) && displayData && (
        <AIStatusPanelV2 
          data={displayData} 
          isAiMode={isAiMode}
          tradingBudget={previewData?.trading_budget}
        />
      )}
    </div>
  );
};

/**
 * AI Status Panel V2 - New Position Sizing Display
 * Shows: Position Size as % of Available USDT + Calculated Order
 */
const AIStatusPanelV2 = ({ data, isAiMode, tradingBudget }) => {
  const { 
    position_pct_range,
    position_usd_min,
    position_usd_max,
    usdt_free,
    trading_budget_remaining,
    sl_atr_multiplier,
    tp_rr_range,
    max_positions,
    risk_per_trade,
    allowed_regimes,
    min_adx,
    reasoning
  } = data;
  
  const formatCurrency = (val) => `$${(val || 0).toFixed(2)}`;
  
  // Calculate midpoint position size for display
  const avgPositionUsd = ((position_usd_min || 0) + (position_usd_max || 0)) / 2;

  return (
    <div className="p-4 bg-purple-950/20 border border-purple-900/30 rounded-lg" data-testid="ai-status-panel-v2">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-purple-500" />
          <span className="text-sm font-medium text-purple-400">
            {isAiMode ? 'AI V2 - Dynamische Positionsgröße' : 'Vorschau'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <Wallet className="w-3 h-3" />
          Verfügbar: <span className="text-green-400 font-mono">{formatCurrency(usdt_free)}</span>
        </div>
      </div>
      
      {/* Main Position Size Display - NEW FORMAT */}
      <div className="p-4 bg-gradient-to-r from-purple-900/30 to-zinc-900/50 rounded-lg border border-purple-800/30 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Target className="w-4 h-4 text-purple-400" />
          <span className="text-sm text-zinc-400">Position Size</span>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          {/* Percentage of Available USDT */}
          <div>
            <div className="text-xs text-zinc-500 mb-1">% vom verfügbaren USDT</div>
            <div className="text-2xl font-bold font-mono text-purple-400">
              {position_pct_range || '0%'}
            </div>
          </div>
          
          {/* Calculated Order Size */}
          <div>
            <div className="text-xs text-zinc-500 mb-1">Berechnete Order</div>
            <div className="text-2xl font-bold font-mono text-green-400">
              {formatCurrency(avgPositionUsd)}
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              Range: {formatCurrency(position_usd_min)} - {formatCurrency(position_usd_max)}
            </div>
          </div>
        </div>
        
        {/* Budget Cap Info */}
        {tradingBudget && (
          <div className="mt-3 pt-3 border-t border-zinc-800 flex items-center justify-between text-xs">
            <span className="text-zinc-500">
              Trading Budget (Cap): <span className="text-white font-mono">${tradingBudget}</span>
            </span>
            <span className="text-zinc-500">
              Verbleibend: <span className="text-yellow-400 font-mono">{formatCurrency(trading_budget_remaining)}</span>
            </span>
          </div>
        )}
      </div>
      
      {/* Risk Parameters Grid */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        {/* Stop Loss (ATR-based) */}
        <div className="p-3 bg-zinc-900/50 rounded-lg">
          <div className="text-xs text-zinc-500 mb-1">Stop Loss</div>
          <div className="text-lg font-bold font-mono text-red-400">
            {sl_atr_multiplier || 'ATR'}
          </div>
          <div className="text-xs text-zinc-600">Dynamisch</div>
        </div>
        
        {/* Take Profit (R:R based) */}
        <div className="p-3 bg-zinc-900/50 rounded-lg">
          <div className="text-xs text-zinc-500 mb-1">Take Profit</div>
          <div className="text-lg font-bold font-mono text-green-400">
            {tp_rr_range || 'R:R'}
          </div>
          <div className="text-xs text-zinc-600">Risk:Reward</div>
        </div>
        
        {/* Max Positions */}
        <div className="p-3 bg-zinc-900/50 rounded-lg">
          <div className="text-xs text-zinc-500 mb-1">Max Pos.</div>
          <div className="text-lg font-bold font-mono text-white">
            {max_positions || 0}
          </div>
          <div className="text-xs text-zinc-600">Gleichzeitig</div>
        </div>
        
        {/* Min ADX */}
        <div className="p-3 bg-zinc-900/50 rounded-lg">
          <div className="text-xs text-zinc-500 mb-1">Min ADX</div>
          <div className="text-lg font-bold font-mono text-yellow-400">
            {min_adx || 0}
          </div>
          <div className="text-xs text-zinc-600">Trend-Stärke</div>
        </div>
      </div>
      
      {/* Risk Per Trade & Regimes */}
      <div className="flex items-center justify-between text-xs mb-3">
        {risk_per_trade && (
          <div className="flex items-center gap-2">
            <Activity className="w-3 h-3 text-zinc-500" />
            <span className="text-zinc-500">Risk/Trade:</span>
            <span className="text-orange-400 font-mono">{risk_per_trade}</span>
          </div>
        )}
        {allowed_regimes && allowed_regimes.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-zinc-500">Erlaubt:</span>
            {allowed_regimes.map((regime, idx) => (
              <Badge key={idx} className={`text-xs ${
                regime === 'bullish' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
              } border-0`}>
                {regime.toUpperCase()}
              </Badge>
            ))}
          </div>
        )}
      </div>
      
      {/* AI Reasoning */}
      {reasoning && reasoning.length > 0 && (
        <div className="pt-3 border-t border-zinc-800">
          <div className="text-xs text-zinc-500 mb-2">AI Info:</div>
          <div className="max-h-24 overflow-y-auto space-y-1">
            {reasoning.map((reason, idx) => (
              <div key={idx} className="text-xs text-zinc-400 flex items-start gap-2">
                <span className="text-purple-500 mt-0.5">•</span>
                <span>{reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Legacy AIStatusPanel for backwards compatibility
const AIStatusPanel = AIStatusPanelV2;

export { TradingModeSelector, AIStatusPanel, AIStatusPanelV2 };
export default TradingModeSelector;
