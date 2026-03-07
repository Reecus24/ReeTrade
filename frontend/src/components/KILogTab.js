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
  const [coinStats, setCoinStats] = useState(null);
  const [mfeAnalysis, setMfeAnalysis] = useState(null);
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
      const [kiRes, rlRes, coinRes, mfeRes] = await Promise.all([
        axios.get(`${API}/api/ki/stats`, getAuthHeaders()),
        axios.get(`${API}/api/rl/status`, getAuthHeaders()),
        axios.get(`${API}/api/coin-stats`, getAuthHeaders()).catch(() => ({ data: null })),
        axios.get(`${API}/api/mfe-mae-analysis`, getAuthHeaders()).catch(() => ({ data: null }))
      ]);
      setStats(kiRes.data);
      setRlStatus(rlRes.data);
      setCoinStats(coinRes.data);
      setMfeAnalysis(mfeRes.data);
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

      {/* Exit Statistics Panel - VOLLSTÄNDIGE EXIT-ANALYSE */}
      {rlStatus?.exit_stats && (
        <div className="cyber-panel p-6 space-y-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-orange-500/20 border border-orange-500/50">
              <Target className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-orange-400 tracking-widest uppercase">EXIT SOURCE BREAKDOWN</h3>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Analyse der Exit-Gründe</p>
            </div>
          </div>
          
          {/* EXIT SOURCE BREAKDOWN - Prozentuale Verteilung */}
          <div className="space-y-3">
            {/* Time Limit Bar - KRITISCH wenn >70% */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono-cyber">
                <span className={`${(rlStatus.exit_stats.pct_time_limit || 0) > 70 ? 'text-red-400' : 'text-yellow-400'}`}>
                  ⏰ TIME LIMIT (10min Hard Exit)
                </span>
                <span className={`${(rlStatus.exit_stats.pct_time_limit || 0) > 70 ? 'text-red-400 font-bold' : 'text-yellow-400'}`}>
                  {rlStatus.exit_stats.pct_time_limit || 0}%
                </span>
              </div>
              <div className="h-4 bg-black/50 border border-zinc-800 overflow-hidden">
                <div 
                  className={`h-full transition-all ${(rlStatus.exit_stats.pct_time_limit || 0) > 70 ? 'bg-red-500' : 'bg-yellow-500/70'}`}
                  style={{ width: `${rlStatus.exit_stats.pct_time_limit || 0}%` }}
                />
              </div>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">
                Ø Hold: {rlStatus.exit_stats.avg_hold_time_time_limit_s || 600}s | Anzahl: {rlStatus.exit_stats.time_limit_sells || 0}
              </p>
            </div>
            
            {/* Exploitation Bar - POSITIV */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono-cyber">
                <span className="text-cyan-400">🧠 EXPLOITATION (KI-Entscheidung)</span>
                <span className="text-cyan-400">{rlStatus.exit_stats.pct_exploitation || 0}%</span>
              </div>
              <div className="h-4 bg-black/50 border border-zinc-800 overflow-hidden">
                <div 
                  className="h-full bg-cyan-500/70 transition-all"
                  style={{ width: `${rlStatus.exit_stats.pct_exploitation || 0}%` }}
                />
              </div>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">
                Ø Hold: {rlStatus.exit_stats.avg_hold_time_exploitation_s || 0}s | Anzahl: {rlStatus.exit_stats.exploitation_sells || 0}
              </p>
            </div>
            
            {/* Exploration Bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono-cyber">
                <span className="text-purple-400">🎲 RANDOM EXPLORATION</span>
                <span className="text-purple-400">{rlStatus.exit_stats.pct_exploration || 0}%</span>
              </div>
              <div className="h-4 bg-black/50 border border-zinc-800 overflow-hidden">
                <div 
                  className="h-full bg-purple-500/70 transition-all"
                  style={{ width: `${rlStatus.exit_stats.pct_exploration || 0}%` }}
                />
              </div>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">
                Ø Hold: {rlStatus.exit_stats.avg_hold_time_exploration_s || 0}s | Anzahl: {rlStatus.exit_stats.exploration_sells || 0}
              </p>
            </div>
            
            {/* Emergency Bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono-cyber">
                <span className="text-red-400">🚨 EMERGENCY</span>
                <span className="text-red-400">{rlStatus.exit_stats.pct_emergency || 0}%</span>
              </div>
              <div className="h-4 bg-black/50 border border-zinc-800 overflow-hidden">
                <div 
                  className="h-full bg-red-500/70 transition-all"
                  style={{ width: `${rlStatus.exit_stats.pct_emergency || 0}%` }}
                />
              </div>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">
                Ø Hold: {rlStatus.exit_stats.avg_hold_time_emergency_s || 0}s | Anzahl: {rlStatus.exit_stats.emergency_sells || 0}
              </p>
            </div>
          </div>
          
          {/* Warning wenn Time Limit > 70% */}
          {(rlStatus.exit_stats.pct_time_limit || 0) > 70 && (
            <div className="p-3 border border-red-500/50 bg-red-500/10">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <p className="text-sm text-red-400 font-mono-cyber">
                  WARNUNG: {rlStatus.exit_stats.pct_time_limit}% der Trades werden durch das 10-Minuten Zeitlimit beendet.
                  Die KI trifft kaum aktive Exit-Entscheidungen!
                </p>
              </div>
            </div>
          )}
          
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-4 gap-3 mt-4">
            <div className="bg-black/50 border border-zinc-800 p-3 text-center">
              <p className="text-lg font-cyber text-white">{rlStatus.exit_stats.total_all_exits || 0}</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">TOTAL EXITS</p>
            </div>
            <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
              <p className="text-lg font-cyber text-cyan-400">{rlStatus.exit_stats.avg_hold_time_total_s || 0}s</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Ø HOLD TIME</p>
            </div>
            <div className="bg-black/50 border border-green-500/20 p-3 text-center">
              <p className={`text-lg font-cyber ${(rlStatus.exit_stats.exploitation_ratio || 0) > 50 ? 'text-green-400' : 'text-yellow-400'}`}>
                {rlStatus.exit_stats.exploitation_ratio || 0}%
              </p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">EXPLOITATION RATIO</p>
            </div>
            <div className="bg-black/50 border border-purple-500/20 p-3 text-center">
              <p className="text-lg font-cyber text-purple-400">{(rlStatus.exit_stats.avg_sell_probability_pct || 0).toFixed(2)}%</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Ø SELL PROB</p>
            </div>
          </div>
          
          {/* Hold Time Distribution */}
          {rlStatus.exit_stats.hold_distribution && (
            <div className="mt-4">
              <p className="text-xs text-zinc-500 font-mono-cyber mb-2">HOLD TIME DISTRIBUTION</p>
              <div className="flex gap-1">
                {Object.entries(rlStatus.exit_stats.hold_distribution).map(([bucket, count]) => (
                  <div key={bucket} className="flex-1 text-center">
                    <div 
                      className="bg-cyan-500/30 border border-cyan-500/20 transition-all"
                      style={{ 
                        height: `${Math.max(4, (count / (rlStatus.exit_stats.total_all_exits || 1)) * 100)}px`,
                        minHeight: '4px'
                      }}
                    />
                    <p className="text-[9px] text-zinc-600 font-mono-cyber mt-1">{bucket}</p>
                    <p className="text-[10px] text-cyan-400 font-mono-cyber">{count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Interpretation */}
          <div className="mt-4 p-3 bg-black/30 border border-zinc-800">
            <p className="text-xs text-zinc-500 font-mono-cyber mb-1">INTERPRETATION</p>
            <p className="text-xs text-zinc-400 font-mono-cyber">
              {(rlStatus.exit_stats.pct_time_limit || 0) > 70 
                ? '⚠️ Die KI ist zu PASSIV. Sie sollte lernen, profitable Trades VOR dem Hard Exit zu schließen.'
                : (rlStatus.exit_stats.exploitation_ratio || 0) > 50
                  ? '✅ Die KI nutzt aktiv gelerntes Wissen für Exit-Entscheidungen. Exploitation > Exploration = gutes Zeichen!'
                  : '🎓 Die KI befindet sich noch in der Lernphase. Exploration wird mit der Zeit abnehmen.'
              }
            </p>
          </div>
        </div>
      )}

      {/* Recent Exit Decision Logs - Für Transparenz */}
      {rlStatus?.exit_stats?.recent_exit_logs && rlStatus.exit_stats.recent_exit_logs.length > 0 && (
        <div className="cyber-panel p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-zinc-500/20 border border-zinc-500/50">
              <Clock className="w-5 h-5 text-zinc-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-zinc-400 tracking-widest uppercase">EXIT DECISION LOG</h3>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Letzte Exit-Entscheidungen der KI</p>
            </div>
          </div>
          
          <ScrollArea className="h-48">
            <div className="space-y-2">
              {rlStatus.exit_stats.recent_exit_logs.slice().reverse().map((log, idx) => (
                <div 
                  key={idx} 
                  className={`p-2 text-xs font-mono-cyber border ${
                    log.decision === 'SELL' 
                      ? 'bg-red-500/5 border-red-500/20' 
                      : 'bg-black/30 border-zinc-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`font-bold ${log.decision === 'SELL' ? 'text-red-400' : 'text-zinc-400'}`}>
                      {log.symbol} → {log.decision}
                    </span>
                    <span className="text-zinc-600">
                      {log.timestamp ? new Date(log.timestamp).toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit', second: '2-digit'}) : ''}
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-[10px]">
                    <div>
                      <span className="text-zinc-600">Hold:</span>
                      <span className="text-zinc-300 ml-1">{log.hold_seconds}s</span>
                    </div>
                    <div>
                      <span className="text-zinc-600">PnL:</span>
                      <span className={`ml-1 ${log.current_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {log.current_pnl_pct?.toFixed(2)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-600">ε:</span>
                      <span className="text-purple-400 ml-1">{(log.epsilon * 100).toFixed(0)}%</span>
                    </div>
                    <div>
                      <span className="text-zinc-600">Q[S]:</span>
                      <span className="text-cyan-400 ml-1">{log.q_values?.sell?.toFixed(2) || 'N/A'}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* Recent Exits - Detaillierte Analyse */}
      {rlStatus?.exit_stats?.recent_exits && rlStatus.exit_stats.recent_exits.length > 0 && (
        <div className="cyber-panel p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-green-500/20 border border-green-500/50">
              <Activity className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-green-400 tracking-widest uppercase">LETZTE EXITS</h3>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Abgeschlossene Trades (letzte 20)</p>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono-cyber">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-2">Symbol</th>
                  <th className="text-left py-2">Source</th>
                  <th className="text-right py-2">Hold</th>
                  <th className="text-right py-2">PnL</th>
                  <th className="text-right py-2">Q[SELL]</th>
                </tr>
              </thead>
              <tbody>
                {rlStatus.exit_stats.recent_exits.slice().reverse().map((exit, idx) => (
                  <tr key={idx} className="border-b border-zinc-800/50 hover:bg-zinc-800/20">
                    <td className="py-2 text-white">{exit.symbol}</td>
                    <td className={`py-2 ${
                      exit.source === 'time_limit' ? 'text-yellow-400' :
                      exit.source === 'exploitation' ? 'text-cyan-400' :
                      exit.source === 'random_exploration' ? 'text-purple-400' :
                      exit.source === 'emergency' ? 'text-red-400' : 'text-zinc-400'
                    }`}>
                      {exit.source === 'time_limit' ? '⏰' :
                       exit.source === 'exploitation' ? '🧠' :
                       exit.source === 'random_exploration' ? '🎲' :
                       exit.source === 'emergency' ? '🚨' : '❓'}
                      {exit.source}
                    </td>
                    <td className="py-2 text-right text-zinc-300">{exit.hold_seconds}s</td>
                    <td className={`py-2 text-right ${exit.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {exit.pnl_pct >= 0 ? '+' : ''}{exit.pnl_pct?.toFixed(2)}%
                    </td>
                    <td className="py-2 text-right text-cyan-400">
                      {exit.q_values?.sell?.toFixed(2) || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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

      {/* ============ COIN-SPEZIFISCHE STATISTIKEN ============ */}
      {coinStats?.coins && coinStats.coins.length > 0 && (
        <div className="cyber-panel p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-blue-500/20 border border-blue-500/50">
              <Activity className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-blue-400 tracking-widest uppercase">COIN PERFORMANCE</h3>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">
                {coinStats.profitable_coins}/{coinStats.total_coins} Coins profitabel
              </p>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono-cyber">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-2">Coin</th>
                  <th className="text-right py-2">Trades</th>
                  <th className="text-right py-2">Winrate</th>
                  <th className="text-right py-2">Avg PnL</th>
                  <th className="text-right py-2">Edge</th>
                  <th className="text-right py-2">Spread</th>
                  <th className="text-right py-2">Slip</th>
                  <th className="text-right py-2">PF</th>
                  <th className="text-right py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {coinStats.coins.map((coin, idx) => (
                  <tr key={idx} className="border-b border-zinc-800/50 hover:bg-zinc-800/20">
                    <td className="py-2 text-white font-bold">{coin.symbol.replace('USDT', '')}</td>
                    <td className="py-2 text-right text-zinc-400">{coin.trade_count}</td>
                    <td className={`py-2 text-right ${coin.winrate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                      {coin.winrate}%
                    </td>
                    <td className={`py-2 text-right ${coin.avg_net_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {coin.avg_net_pnl_pct >= 0 ? '+' : ''}{coin.avg_net_pnl_pct}%
                    </td>
                    <td className={`py-2 text-right font-bold ${coin.edge_after_costs >= 0 ? 'text-cyan-400' : 'text-red-400'}`}>
                      {coin.edge_after_costs >= 0 ? '+' : ''}{(coin.edge_after_costs * 100).toFixed(2)}%
                    </td>
                    <td className="py-2 text-right text-zinc-500">{(coin.avg_spread_pct * 100).toFixed(3)}%</td>
                    <td className="py-2 text-right text-zinc-500">{(coin.avg_slippage_pct * 100).toFixed(3)}%</td>
                    <td className={`py-2 text-right ${coin.profit_factor >= 1 ? 'text-green-400' : 'text-yellow-400'}`}>
                      {coin.profit_factor}
                    </td>
                    <td className="py-2 text-right text-xs">
                      {coin.recommendation}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {coinStats.summary?.best_coin && (
            <div className="mt-4 p-3 bg-black/30 border border-zinc-800 grid grid-cols-2 gap-4">
              <div>
                <p className="text-[10px] text-zinc-500 font-mono-cyber">BESTER COIN</p>
                <p className="text-lg font-cyber text-green-400">{coinStats.summary.best_coin.replace('USDT', '')}</p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 font-mono-cyber">SCHLECHTESTER COIN</p>
                <p className="text-lg font-cyber text-red-400">{coinStats.summary.worst_coin.replace('USDT', '')}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============ MFE/MAE ANALYSE ============ */}
      {mfeAnalysis && mfeAnalysis.total_analyzed > 0 && (
        <div className="cyber-panel p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 border border-purple-500/50">
              <Target className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="font-cyber text-sm text-purple-400 tracking-widest uppercase">MFE / MAE ANALYSE</h3>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">
                Exit-Timing basierend auf {mfeAnalysis.total_analyzed} Trades
              </p>
            </div>
          </div>
          
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="bg-black/50 border border-green-500/20 p-3 text-center">
              <p className="text-lg font-cyber text-green-400">{mfeAnalysis.avg_mfe}%</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Ø MFE (Max Profit)</p>
            </div>
            <div className="bg-black/50 border border-red-500/20 p-3 text-center">
              <p className="text-lg font-cyber text-red-400">{mfeAnalysis.avg_mae}%</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Ø MAE (Max Loss)</p>
            </div>
            <div className="bg-black/50 border border-cyan-500/20 p-3 text-center">
              <p className="text-lg font-cyber text-cyan-400">{mfeAnalysis.avg_mfe_captured_pct}%</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">MFE GENUTZT</p>
            </div>
            <div className="bg-black/50 border border-zinc-500/20 p-3 text-center">
              <p className="text-lg font-cyber text-zinc-300">{mfeAnalysis.avg_pnl}%</p>
              <p className="text-[10px] text-zinc-600 font-mono-cyber">Ø Net PnL</p>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-black/30 border border-zinc-800">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-zinc-500 font-mono-cyber">VERPASSTE PROFITS</span>
                <span className={`text-sm font-mono-cyber ${mfeAnalysis.missed_profit_pct > 30 ? 'text-red-400' : 'text-yellow-400'}`}>
                  {mfeAnalysis.missed_profit_trades} Trades ({mfeAnalysis.missed_profit_pct}%)
                </span>
              </div>
              <p className="text-[10px] text-zinc-600">Trades die im Plus waren, aber negativ geschlossen wurden</p>
            </div>
            <div className="p-3 bg-black/30 border border-zinc-800">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-zinc-500 font-mono-cyber">TIEFE DRAWDOWNS</span>
                <span className={`text-sm font-mono-cyber ${mfeAnalysis.deep_drawdown_pct > 30 ? 'text-red-400' : 'text-yellow-400'}`}>
                  {mfeAnalysis.deep_drawdown_trades} Trades ({mfeAnalysis.deep_drawdown_pct}%)
                </span>
              </div>
              <p className="text-[10px] text-zinc-600">Trades die mehr als -1% im Minus waren</p>
            </div>
          </div>
          
          {/* Interpretation */}
          <div className="mt-4 p-3 bg-black/30 border border-zinc-800">
            <p className="text-xs text-zinc-500 font-mono-cyber mb-2">DIAGNOSE</p>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <span className="text-[10px] text-zinc-500">MFE Nutzung:</span>
                <p className={`text-sm font-mono-cyber ${mfeAnalysis.interpretation?.mfe_utilization === 'gut' ? 'text-green-400' : 'text-yellow-400'}`}>
                  {mfeAnalysis.interpretation?.mfe_utilization === 'gut' ? '✅ Gut' : '⚠️ Verbesserungswürdig'}
                </p>
              </div>
              <div>
                <span className="text-[10px] text-zinc-500">Exit-Timing:</span>
                <p className={`text-sm font-mono-cyber ${
                  mfeAnalysis.interpretation?.exit_timing === 'optimal' ? 'text-green-400' : 
                  mfeAnalysis.interpretation?.exit_timing === 'akzeptabel' ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {mfeAnalysis.interpretation?.exit_timing === 'optimal' ? '✅ Optimal' : 
                   mfeAnalysis.interpretation?.exit_timing === 'akzeptabel' ? '⚠️ Akzeptabel' : '❌ Zu spät'}
                </p>
              </div>
              <div>
                <span className="text-[10px] text-zinc-500">Risk Management:</span>
                <p className={`text-sm font-mono-cyber ${
                  mfeAnalysis.interpretation?.risk_management === 'gut' ? 'text-green-400' : 
                  mfeAnalysis.interpretation?.risk_management === 'akzeptabel' ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {mfeAnalysis.interpretation?.risk_management === 'gut' ? '✅ Gut' : 
                   mfeAnalysis.interpretation?.risk_management === 'akzeptabel' ? '⚠️ Akzeptabel' : '❌ Kritisch'}
                </p>
              </div>
            </div>
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
