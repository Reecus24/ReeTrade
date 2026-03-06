import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Button } from './ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./ui/alert-dialog";
import { toast } from 'sonner';
import { 
  Brain, AlertTriangle, 
  Target, Activity, Zap, Clock, RefreshCw, RotateCcw
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
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [resetting, setResetting] = useState(false);

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

  const handleResetRL = async () => {
    setResetting(true);
    try {
      const res = await axios.post(`${API}/api/rl/reset`, {}, getAuthHeaders());
      toast.success('RL-KI wurde erfolgreich zurückgesetzt!', {
        description: `Alte Stats: ${res.data.old_stats.trades} Trades, ${(res.data.old_stats.win_rate * 100).toFixed(1)}% Win-Rate`
      });
      setShowResetDialog(false);
      // Refresh data
      await fetchData();
    } catch (err) {
      toast.error('Reset fehlgeschlagen', {
        description: err.response?.data?.detail || 'Unbekannter Fehler'
      });
    } finally {
      setResetting(false);
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
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowResetDialog(true)}
            className="text-red-400 hover:text-red-300 hover:bg-red-500/10 font-mono-cyber"
            data-testid="reset-rl-btn"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            RESET
          </Button>
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

      {/* Exit Statistics Panel */}
      {rlStatus?.exit_stats && (
        <div className="cyber-panel p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-orange-500/20 border border-orange-500/50">
              <Target className="w-5 h-5 text-orange-400" />
            </div>
            <h3 className="font-cyber text-sm text-orange-400 tracking-widest uppercase">EXIT ANALYTICS</h3>
          </div>
          
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-black/50 border border-purple-500/20 p-3 text-center">
              <p className="text-xl font-cyber text-purple-400">{rlStatus.exit_stats.exploration_sells || 0}</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">EXPLORATION SELLS</p>
            </div>
            <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
              <p className="text-xl font-cyber text-cyan-400">{rlStatus.exit_stats.exploitation_sells || 0}</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">EXPLOITATION SELLS</p>
            </div>
            <div className="bg-black/50 border border-red-500/20 p-3 text-center">
              <p className="text-xl font-cyber text-red-400">{rlStatus.exit_stats.emergency_sells || 0}</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">EMERGENCY SELLS</p>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-black/30 p-3 border border-zinc-800">
              <p className="text-[10px] text-zinc-500 font-mono-cyber">AVG SELL PROB</p>
              <p className="text-lg font-mono-cyber text-white">{(rlStatus.exit_stats.avg_sell_probability_pct || 0).toFixed(2)}%</p>
            </div>
            <div className="bg-black/30 p-3 border border-zinc-800">
              <p className="text-[10px] text-zinc-500 font-mono-cyber">EXPLOITATION RATIO</p>
              <p className="text-lg font-mono-cyber text-cyan-400">{(rlStatus.exit_stats.exploitation_ratio || 0).toFixed(1)}%</p>
            </div>
            <div className="bg-black/30 p-3 border border-zinc-800">
              <p className="text-[10px] text-zinc-500 font-mono-cyber">AVG HOLD (EXPLORATION)</p>
              <p className="text-lg font-mono-cyber text-purple-400">{(rlStatus.exit_stats.avg_hold_time_exploration_s || 0).toFixed(0)}s</p>
            </div>
            <div className="bg-black/30 p-3 border border-zinc-800">
              <p className="text-[10px] text-zinc-500 font-mono-cyber">AVG HOLD (EXPLOITATION)</p>
              <p className="text-lg font-mono-cyber text-cyan-400">{(rlStatus.exit_stats.avg_hold_time_exploitation_s || 0).toFixed(0)}s</p>
            </div>
          </div>
          
          <p className="text-[10px] text-zinc-600 font-mono-cyber mt-3 italic">
            Exploration-Check alle {rlStatus.exit_stats.exploration_check_interval_s || 30}s | 
            Ziel: Exploitation Ratio {'>'} 50% = KI nutzt gelerntes Wissen
          </p>
        </div>
      )}

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

      {/* RL-KI Erklärung */}
      <div className="cyber-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 flex items-center justify-center bg-blue-500/20 border border-blue-500/50">
            <Brain className="w-5 h-5 text-blue-400" />
          </div>
          <h3 className="font-cyber text-sm text-blue-400 tracking-widest uppercase">WIE LERNT DIE KI?</h3>
        </div>
        
        <div className="space-y-4 text-base">
          <p className="text-zinc-300">
            Die KI verwendet ein <strong className="text-purple-400">Neural Network</strong>, das aus Erfahrung lernt.
            Es gibt keine festen Regeln - die KI entwickelt ihre eigene Strategie.
          </p>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-black/50 border border-green-500/20">
              <p className="text-green-400 font-semibold mb-2">Bei Gewinn:</p>
              <p className="text-sm text-zinc-400">
                "Diese Marktbedingungen → KAUFEN war richtig"
                <br/>→ KI merkt sich das Muster
              </p>
            </div>
            <div className="p-4 bg-black/50 border border-red-500/20">
              <p className="text-red-400 font-semibold mb-2">Bei Verlust:</p>
              <p className="text-sm text-zinc-400">
                "Diese Marktbedingungen → KAUFEN war falsch"
                <br/>→ KI vermeidet ähnliche Situationen
              </p>
            </div>
          </div>
          
          <p className="text-sm text-zinc-500 text-center mt-4">
            Mit jedem Trade wird das Neural Network angepasst - die KI wird immer besser.
          </p>
        </div>
      </div>

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
      {(rlStatus?.total_trades || 0) < 10 && (
        <div className="p-4 border border-yellow-500/30 bg-yellow-500/5">
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-yellow-400" />
            <div>
              <p className="text-base text-yellow-400 font-mono-cyber">LERNPHASE AKTIV</p>
              <p className="text-sm text-zinc-400 font-mono-cyber">
                Noch {10 - (rlStatus?.total_trades || 0)} Trades bis KI voll einsatzbereit
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Reset Confirmation Dialog */}
      <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
        <AlertDialogContent className="bg-zinc-900 border border-red-500/30">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-400 font-cyber flex items-center gap-2">
              <RotateCcw className="w-5 h-5" />
              RL-KI ZURÜCKSETZEN
            </AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400 font-mono-cyber space-y-3">
              <p>⚠️ <strong>ACHTUNG:</strong> Dies löscht ALLE Daten!</p>
              <ul className="list-disc list-inside text-sm space-y-1">
                <li>Replay Buffer ({rlStatus?.memory_size || 0} Erfahrungen)</li>
                <li>Neural Networks (alle gelernten Gewichte)</li>
                <li>Trade-Statistiken ({rlStatus?.total_trades || 0} Trades)</li>
                <li className="text-red-400">Trade-Historie in der Datenbank</li>
                <li>Win-Rate ({winRate.toFixed(1)}%)</li>
              </ul>
              <p className="text-green-400">✅ Ein Backup wird automatisch erstellt.</p>
              <p>Die KI startet dann mit 100% Exploration und lernt von Grund auf neu.</p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-zinc-800 text-zinc-400 border-zinc-700 hover:bg-zinc-700">
              Abbrechen
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleResetRL}
              disabled={resetting}
              className="bg-red-500/20 text-red-400 border border-red-500 hover:bg-red-500/30"
            >
              {resetting ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  RESET LÄUFT...
                </>
              ) : (
                <>
                  <RotateCcw className="w-4 h-4 mr-2" />
                  JA, ZURÜCKSETZEN
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
