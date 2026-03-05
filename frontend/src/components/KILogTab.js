import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { 
  Brain, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, 
  BookOpen, Target, Activity, Zap, Clock, RefreshCw
} from 'lucide-react';
import { format } from 'date-fns';
import { de } from 'date-fns/locale';

const API = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

export default function KILogTab() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [rlStatus, setRlStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [kiRes, rlRes] = await Promise.all([
        axios.get(`${API}/api/ki/stats`, getAuthHeaders()),
        axios.get(`${API}/api/rl/status`, getAuthHeaders())
      ]);
      setStats(kiRes.data);
      setRlStatus(rlRes.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin mx-auto mb-4" />
          <p className="text-zinc-500 font-mono-cyber">LOADING AI DATA...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 border border-red-500/30 bg-red-500/5">
        <AlertTriangle className="w-5 h-5 text-red-400 inline mr-2" />
        <span className="text-red-400 font-mono-cyber">{error}</span>
      </div>
    );
  }

  const explorationPct = rlStatus?.exploration_pct || 100;
  const learningPct = 100 - explorationPct;
  const winRate = (rlStatus?.win_rate || 0) * 100;

  return (
    <div className="space-y-6" data-testid="ki-log-tab">
      {/* RL Status Header */}
      <div className="cyber-panel p-6 box-glow-purple">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
              <Brain className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h2 className="font-cyber text-xl text-white tracking-wider">
                NEURAL <span className="text-purple-400">NETWORK</span>
              </h2>
              <p className="text-xs text-zinc-500 font-mono-cyber">REINFORCEMENT LEARNING ENGINE</p>
            </div>
          </div>
          <Badge className={`cyber-badge ${rlStatus?.is_learning ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50 animate-pulse' : 'bg-green-500/20 text-green-400 border border-green-500/50'}`}>
            {rlStatus?.is_learning ? 'LEARNING' : 'TRAINED'}
          </Badge>
        </div>

        {/* Learning Progress */}
        <div className="mb-6">
          <div className="flex justify-between text-xs mb-2 font-mono-cyber">
            <span className="text-zinc-500">NEURAL TRAINING PROGRESS</span>
            <span className="text-cyan-400">{learningPct.toFixed(0)}%</span>
          </div>
          <div className="cyber-progress h-3">
            <div 
              className="h-full"
              style={{ 
                width: `${learningPct}%`,
                background: 'linear-gradient(90deg, #bf00ff, #00f0ff)'
              }}
            />
          </div>
          <div className="flex justify-between text-[10px] mt-2 text-zinc-600 font-mono-cyber">
            <span>EXPLORATION: {explorationPct.toFixed(0)}%</span>
            <span>EXPLOITATION: {learningPct.toFixed(0)}%</span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-black/50 border border-cyan-500/20 p-4 text-center">
            <Activity className="w-5 h-5 text-cyan-400 mx-auto mb-2" />
            <p className="text-2xl font-cyber text-white">{rlStatus?.total_trades || 0}</p>
            <p className="text-[10px] text-zinc-600 font-mono-cyber">TOTAL TRADES</p>
          </div>
          <div className="bg-black/50 border border-purple-500/20 p-4 text-center">
            <Brain className="w-5 h-5 text-purple-400 mx-auto mb-2" />
            <p className="text-2xl font-cyber text-purple-400">{rlStatus?.memory_size || 0}</p>
            <p className="text-[10px] text-zinc-600 font-mono-cyber">MEMORY</p>
          </div>
          <div className="bg-black/50 border border-green-500/20 p-4 text-center">
            <Target className="w-5 h-5 text-green-400 mx-auto mb-2" />
            <p className={`text-2xl font-cyber ${winRate >= 50 ? 'text-green-400 glow-green' : 'text-red-400'}`}>
              {winRate.toFixed(1)}%
            </p>
            <p className="text-[10px] text-zinc-600 font-mono-cyber">WIN RATE</p>
          </div>
          <div className="bg-black/50 border border-yellow-500/20 p-4 text-center">
            <Zap className="w-5 h-5 text-yellow-400 mx-auto mb-2" />
            <p className="text-2xl font-cyber text-yellow-400">
              {rlStatus?.winning_trades || 0}
            </p>
            <p className="text-[10px] text-zinc-600 font-mono-cyber">WINS</p>
          </div>
        </div>
      </div>

      {/* Active Episodes */}
      {rlStatus?.active_episodes && rlStatus.active_episodes.length > 0 && (
        <div className="cyber-panel p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-cyan-500/20 border border-cyan-500/50">
              <Activity className="w-5 h-5 text-cyan-400" />
            </div>
            <h3 className="font-cyber text-sm text-cyan-400 tracking-widest uppercase">ACTIVE EPISODES</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {rlStatus.active_episodes.map(symbol => (
              <span key={symbol} className="px-3 py-2 bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-mono-cyber text-sm">
                {symbol}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Learned Parameters */}
      {stats?.learned_params && (
        <div className="cyber-panel p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-blue-500/20 border border-blue-500/50">
              <BookOpen className="w-5 h-5 text-blue-400" />
            </div>
            <h3 className="font-cyber text-sm text-blue-400 tracking-widest uppercase">LEARNED PARAMETERS</h3>
          </div>
          
          <div className="grid grid-cols-5 gap-3">
            <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
              <p className="text-[10px] text-zinc-600 font-mono-cyber mb-1">RSI MIN</p>
              <p className="text-xl font-cyber text-cyan-400">
                {stats.learned_params.rsi_min?.toFixed(0) || 45}
              </p>
            </div>
            <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
              <p className="text-[10px] text-zinc-600 font-mono-cyber mb-1">RSI MAX</p>
              <p className="text-xl font-cyber text-cyan-400">
                {stats.learned_params.rsi_max?.toFixed(0) || 70}
              </p>
            </div>
            <div className="bg-black/50 border border-green-500/20 p-3 text-center">
              <p className="text-[10px] text-zinc-600 font-mono-cyber mb-1">ADX MIN</p>
              <p className="text-xl font-cyber text-green-400">
                {stats.learned_params.adx_min?.toFixed(0) || 20}
              </p>
            </div>
            <div className="bg-black/50 border border-yellow-500/20 p-3 text-center">
              <p className="text-[10px] text-zinc-600 font-mono-cyber mb-1">VOL MIN</p>
              <p className="text-lg font-cyber text-yellow-400">
                ${(stats.learned_params.volume_threshold / 1000)?.toFixed(0) || 500}k
              </p>
            </div>
            <div className="bg-black/50 border border-orange-500/20 p-3 text-center">
              <p className="text-[10px] text-zinc-600 font-mono-cyber mb-1">ATR MULT</p>
              <p className="text-xl font-cyber text-orange-400">
                {stats.learned_params.atr_multiplier?.toFixed(1) || 2.0}x
              </p>
            </div>
          </div>
          <p className="text-[10px] text-zinc-600 mt-3 text-center font-mono-cyber">
            VALUES AUTO-ADJUSTED BY REINFORCEMENT LEARNING
          </p>
        </div>
      )}

      {/* Learning Log */}
      <div className="cyber-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
            <Clock className="w-5 h-5 text-purple-400" />
          </div>
          <h3 className="font-cyber text-sm text-purple-400 tracking-widest uppercase">AI LEARNING LOG</h3>
        </div>
        
        <ScrollArea className="h-64">
          {stats?.recent_lessons && stats.recent_lessons.length > 0 ? (
            <div className="space-y-2">
              {stats.recent_lessons.slice().reverse().map((lesson, idx) => (
                <div 
                  key={idx} 
                  className={`p-3 border ${
                    lesson.type === 'KI_TAKEOVER' 
                      ? 'bg-purple-500/10 border-purple-500/30'
                      : lesson.type === 'MISTAKE_LEARNING'
                      ? 'bg-red-500/10 border-red-500/30'
                      : 'bg-black/50 border-cyan-500/20'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      {lesson.type === 'KI_TAKEOVER' && <Brain className="w-4 h-4 text-purple-400" />}
                      {lesson.type === 'MISTAKE_LEARNING' && <AlertTriangle className="w-4 h-4 text-red-400" />}
                      {lesson.type === 'INITIAL_LEARNING' && <BookOpen className="w-4 h-4 text-cyan-400" />}
                      <span className="text-sm font-mono-cyber text-zinc-300">
                        {lesson.message || lesson.type}
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-600 font-mono-cyber">
                      {lesson.time ? format(new Date(lesson.time), 'HH:mm', { locale: de }) : ''}
                    </span>
                  </div>
                  {lesson.adjustments && lesson.adjustments.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {lesson.adjustments.map((adj, i) => (
                        <Badge key={i} className="cyber-badge bg-zinc-900 text-zinc-500 border border-zinc-700 text-[10px]">
                          {adj}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <Brain className="w-12 h-12 mx-auto mb-4 text-purple-500/30" />
              <p className="text-zinc-600 font-mono-cyber">NO LEARNING ENTRIES YET</p>
              <p className="text-[10px] text-zinc-700 mt-1 font-mono-cyber">
                AI starts learning after first trades
              </p>
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Recent Mistakes */}
      {stats?.recent_mistakes && stats.recent_mistakes.length > 0 && (
        <div className="cyber-panel p-6" style={{borderColor: 'rgba(255,0,68,0.3)'}}>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-red-500/20 border border-red-500/50">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <h3 className="font-cyber text-sm text-red-400 tracking-widest uppercase">RECENT MISTAKES</h3>
          </div>
          
          <div className="space-y-3">
            {stats.recent_mistakes.map((mistake, idx) => (
              <div key={idx} className="p-3 bg-red-500/5 border border-red-500/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-cyber text-red-400">{mistake.symbol}</span>
                  <span className="text-sm text-red-300 font-mono-cyber">
                    {mistake.pnl_percent?.toFixed(1)}%
                  </span>
                </div>
                <p className="text-xs text-zinc-500 font-mono-cyber">
                  <span className="text-zinc-400">LESSON:</span> {mistake.lesson_learned}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Boot Phase Warning */}
      {(rlStatus?.total_trades || 0) < 20 && (
        <div className="p-4 border border-yellow-500/30 bg-yellow-500/5">
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-yellow-400" />
            <div>
              <p className="text-sm text-yellow-400 font-mono-cyber">BOOT PHASE ACTIVE</p>
              <p className="text-xs text-zinc-600 font-mono-cyber">
                {20 - (rlStatus?.total_trades || 0)} trades remaining until full neural training
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
