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
import { Bot, User, Shield, TrendingUp, Zap, AlertTriangle, Info } from 'lucide-react';
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
    min_order: aiStatus?.min_position || 0,
    max_order: aiStatus?.max_position || 0,
    current_order: aiStatus?.current_position || 0,
    confidence: aiStatus?.confidence || 0,
    risk_score: aiStatus?.risk_score || 0,
    reasoning: aiStatus?.reasoning || []
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
                    <Icon className={`w-4 h-4 ${PROFILE_COLORS[profile.mode]}`} />
                    <span>{profile.name}</span>
                    <span className="text-xs text-zinc-500 ml-2">
                      (${profile.min_order?.toFixed(0)}-${profile.max_order?.toFixed(0)})
                    </span>
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
        <AIStatusPanel 
          data={displayData} 
          isAiMode={isAiMode}
          tradingBudget={previewData?.trading_budget}
        />
      )}
    </div>
  );
};

const AIStatusPanel = ({ data, isAiMode, tradingBudget }) => {
  const { confidence, risk_score, reasoning, min_order, max_order, current_order, stop_loss_pct, take_profit_pct, max_positions } = data;
  
  const getConfidenceColor = (conf) => {
    if (conf >= 70) return 'text-green-500';
    if (conf >= 40) return 'text-yellow-500';
    return 'text-red-500';
  };
  
  const getRiskColor = (risk) => {
    if (risk <= 30) return 'text-green-500';
    if (risk <= 60) return 'text-yellow-500';
    return 'text-red-500';
  };

  const formatCurrency = (val) => `$${(val || 0).toFixed(0)}`;

  return (
    <div className="p-4 bg-purple-950/20 border border-purple-900/30 rounded-lg" data-testid="ai-status-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-purple-500" />
          <span className="text-sm font-medium text-purple-400">
            {isAiMode ? 'AI Entscheidung' : 'Vorschau'}
          </span>
        </div>
        {tradingBudget && (
          <span className="text-xs text-zinc-500">
            Trading Budget: ${tradingBudget}
          </span>
        )}
      </div>
      
      <div className="grid grid-cols-4 gap-3 mb-3">
        {/* Min-Max Order */}
        <div className="p-2 bg-zinc-900/50 rounded col-span-2">
          <div className="text-xs text-zinc-500 mb-1">Min-Max Order</div>
          <div className="text-xl font-bold font-mono text-purple-400">
            {formatCurrency(min_order)} - {formatCurrency(max_order)}
          </div>
          {current_order > 0 && (
            <div className="text-xs text-zinc-500 mt-1">
              Aktuell: <span className="text-green-400">{formatCurrency(current_order)}</span>
            </div>
          )}
        </div>
        
        {/* Confidence */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500 mb-1">Confidence</div>
          <div className={`text-xl font-bold font-mono ${getConfidenceColor(confidence || 0)}`}>
            {confidence?.toFixed(0) || 0}%
          </div>
        </div>
        
        {/* Risk Score */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500 mb-1">Risiko</div>
          <div className={`text-xl font-bold font-mono ${getRiskColor(risk_score || 0)}`}>
            {risk_score?.toFixed(0) || 0}/100
          </div>
        </div>
      </div>
      
      {/* Additional Info Row */}
      {(stop_loss_pct || take_profit_pct || max_positions) && (
        <div className="grid grid-cols-3 gap-3 mb-3">
          {stop_loss_pct && (
            <div className="p-2 bg-zinc-900/50 rounded">
              <div className="text-xs text-zinc-500 mb-1">Stop Loss</div>
              <div className="text-lg font-bold font-mono text-red-400">
                -{stop_loss_pct?.toFixed(1)}%
              </div>
            </div>
          )}
          {take_profit_pct && (
            <div className="p-2 bg-zinc-900/50 rounded">
              <div className="text-xs text-zinc-500 mb-1">Take Profit</div>
              <div className="text-lg font-bold font-mono text-green-400">
                +{take_profit_pct?.toFixed(1)}%
              </div>
            </div>
          )}
          {max_positions && (
            <div className="p-2 bg-zinc-900/50 rounded">
              <div className="text-xs text-zinc-500 mb-1">Max Positionen</div>
              <div className="text-lg font-bold font-mono text-white">
                {max_positions}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Reasoning */}
      {reasoning && reasoning.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-zinc-500">AI Info:</div>
          <div className="max-h-20 overflow-y-auto space-y-0.5">
            {reasoning.slice(-4).map((reason, idx) => (
              <div key={idx} className="text-xs text-zinc-400 flex items-start gap-1">
                <span className="text-purple-500">•</span>
                <span>{reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export { TradingModeSelector, AIStatusPanel };
export default TradingModeSelector;
