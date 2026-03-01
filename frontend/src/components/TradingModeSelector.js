import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Bot, User, Shield, TrendingUp, Zap, AlertTriangle, CheckCircle, Info } from 'lucide-react';
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

  useEffect(() => {
    fetchProfiles();
  }, []);

  const fetchProfiles = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/ai/profiles`, getAuthHeaders());
      setProfiles(response.data.profiles || []);
    } catch (error) {
      console.error('Failed to fetch AI profiles:', error);
    }
  };

  const handleModeChange = async (newMode) => {
    setLoading(true);
    try {
      await axios.put(`${BACKEND_URL}/api/settings`, { trading_mode: newMode }, getAuthHeaders());
      toast.success(`Trading Modus geändert: ${newMode}`);
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
      
      {/* AI Status Panel (when AI mode active) */}
      {isAiMode && aiStatus && (
        <AIStatusPanel aiStatus={aiStatus} />
      )}
    </div>
  );
};

const AIStatusPanel = ({ aiStatus }) => {
  const { confidence, risk_score, reasoning, last_override, min_position, max_position, current_position } = aiStatus;
  
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
      <div className="flex items-center gap-2 mb-3">
        <Bot className="w-4 h-4 text-purple-500" />
        <span className="text-sm font-medium text-purple-400">AI Entscheidung</span>
      </div>
      
      <div className="grid grid-cols-3 gap-3 mb-3">
        {/* Confidence */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500 mb-1">Confidence</div>
          <div className={`text-xl font-bold font-mono ${getConfidenceColor(confidence || 0)}`}>
            {confidence?.toFixed(0) || 0}%
          </div>
        </div>
        
        {/* Risk Score */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500 mb-1">Risiko Score</div>
          <div className={`text-xl font-bold font-mono ${getRiskColor(risk_score || 0)}`}>
            {risk_score?.toFixed(0) || 0}/100
          </div>
        </div>
        
        {/* Position Size Range (NEW) */}
        <div className="p-2 bg-zinc-900/50 rounded">
          <div className="text-xs text-zinc-500 mb-1">Min-Max Order</div>
          <div className="text-lg font-bold font-mono text-purple-400">
            {formatCurrency(min_position)}-{formatCurrency(max_position)}
          </div>
          {current_position > 0 && (
            <div className="text-xs text-zinc-500">
              Aktuell: <span className="text-green-400">{formatCurrency(current_position)}</span>
            </div>
          )}
        </div>
      </div>
      
      {/* Reasoning */}
      {reasoning && reasoning.length > 0 && (
        <div className="space-y-1 mb-3">
          <div className="text-xs text-zinc-500">AI Reasoning:</div>
          <div className="max-h-24 overflow-y-auto space-y-0.5">
            {reasoning.slice(-5).map((reason, idx) => (
              <div key={idx} className="text-xs text-zinc-400 flex items-start gap-1">
                <span className="text-purple-500">•</span>
                <span>{reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Overrides */}
      {last_override?.overrides && last_override.overrides.length > 0 && (
        <div className="border-t border-purple-900/30 pt-3 mt-3">
          <div className="text-xs text-purple-400 mb-2 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            AI Overrides (Manuelle Settings überschrieben)
          </div>
          <div className="space-y-1">
            {last_override.overrides.map((override, idx) => (
              <div key={idx} className="text-xs flex items-center gap-2 bg-purple-900/20 p-1.5 rounded">
                <span className="text-zinc-500">{override.field}:</span>
                <span className="text-red-400 line-through">{override.manual}</span>
                <span className="text-zinc-500">→</span>
                <span className="text-green-400">{override.ai}</span>
                <span className="text-zinc-600 text-[10px]">({override.reason})</span>
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
