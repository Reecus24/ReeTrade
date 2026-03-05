import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { ScrollArea } from './ui/scroll-area';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Brain, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, 
  BookOpen, Target, Activity, Zap, Clock
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
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchKIStats();
    const interval = setInterval(fetchKIStats, 30000); // Refresh alle 30s
    return () => clearInterval(interval);
  }, []);

  const fetchKIStats = async () => {
    try {
      const res = await axios.get(`${API}/api/ki/stats`, getAuthHeaders());
      setStats(res.data);
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
        <div className="text-zinc-400">Laden...</div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className="bg-red-900/50 border-red-700">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const tradesUntilTakeover = stats?.trades_until_takeover || 10;
  const progress = Math.min(100, ((10 - tradesUntilTakeover) / 10) * 100);

  return (
    <div className="space-y-6" data-testid="ki-log-tab">
      {/* KI Status Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Brain className="w-6 h-6 text-purple-500" />
            KI Learning Engine
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            Learning by Doing - KI lernt aus jedem Trade
          </p>
        </div>
        <Badge 
          className={stats?.ki_active 
            ? "bg-purple-600 text-white text-lg px-4 py-1" 
            : "bg-zinc-700 text-zinc-300 text-lg px-4 py-1"
          }
        >
          {stats?.ki_active ? '🧠 KI AKTIV' : '📊 DATENSAMMLUNG'}
        </Badge>
      </div>

      {/* Takeover Progress */}
      {!stats?.ki_active && (
        <Card className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border-purple-700">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">KI Übernahme Progress</h3>
                <p className="text-zinc-400 text-sm">
                  Noch {tradesUntilTakeover} Trades bis die KI übernimmt
                </p>
              </div>
              <div className="text-right">
                <span className="text-3xl font-bold text-purple-400">
                  {10 - tradesUntilTakeover}/10
                </span>
                <p className="text-xs text-zinc-500">Trades</p>
              </div>
            </div>
            <Progress value={progress} className="h-3" />
            <p className="text-xs text-zinc-500 mt-2">
              Die KI sammelt Daten und lernt aus den ersten 10 Trades, bevor sie selbst handelt.
            </p>
          </CardContent>
        </Card>
      )}

      {/* KI Active Card */}
      {stats?.ki_active && (
        <Card className="bg-gradient-to-r from-green-900/30 to-purple-900/30 border-green-700">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-4 bg-green-500/20 rounded-full">
                <CheckCircle className="w-8 h-8 text-green-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">KI hat übernommen!</h3>
                <p className="text-zinc-400 text-sm">
                  Seit {stats.ki_takeover_time ? format(new Date(stats.ki_takeover_time), 'dd.MM.yyyy HH:mm', { locale: de }) : '-'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-4 text-center">
            <Activity className="w-6 h-6 text-blue-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-white">{stats?.total_trades || 0}</p>
            <p className="text-xs text-zinc-500">Gesamt Trades</p>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-4 text-center">
            <Brain className="w-6 h-6 text-purple-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-white">{stats?.ki_trades || 0}</p>
            <p className="text-xs text-zinc-500">KI Trades</p>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-4 text-center">
            <Target className="w-6 h-6 text-green-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-white">{stats?.ki_win_rate?.toFixed(1) || 0}%</p>
            <p className="text-xs text-zinc-500">KI Win Rate</p>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-4 text-center">
            <Zap className="w-6 h-6 text-yellow-400 mx-auto mb-2" />
            <p className="text-2xl font-bold text-white">{stats?.ki_confidence?.toFixed(0) || 50}%</p>
            <p className="text-xs text-zinc-500">KI Confidence</p>
          </CardContent>
        </Card>
      </div>

      {/* Gelernte Parameter */}
      {stats?.learned_params && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg text-white flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-blue-400" />
              Gelernte Parameter
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="bg-zinc-800/50 p-3 rounded-lg text-center">
                <p className="text-xs text-zinc-500 mb-1">RSI Min</p>
                <p className="text-xl font-mono text-blue-400">
                  {stats.learned_params.rsi_min?.toFixed(0) || 45}
                </p>
              </div>
              <div className="bg-zinc-800/50 p-3 rounded-lg text-center">
                <p className="text-xs text-zinc-500 mb-1">RSI Max</p>
                <p className="text-xl font-mono text-blue-400">
                  {stats.learned_params.rsi_max?.toFixed(0) || 70}
                </p>
              </div>
              <div className="bg-zinc-800/50 p-3 rounded-lg text-center">
                <p className="text-xs text-zinc-500 mb-1">ADX Min</p>
                <p className="text-xl font-mono text-green-400">
                  {stats.learned_params.adx_min?.toFixed(0) || 20}
                </p>
              </div>
              <div className="bg-zinc-800/50 p-3 rounded-lg text-center">
                <p className="text-xs text-zinc-500 mb-1">Volume Min</p>
                <p className="text-lg font-mono text-yellow-400">
                  ${(stats.learned_params.volume_threshold / 1000)?.toFixed(0) || 500}k
                </p>
              </div>
              <div className="bg-zinc-800/50 p-3 rounded-lg text-center">
                <p className="text-xs text-zinc-500 mb-1">ATR Mult</p>
                <p className="text-xl font-mono text-orange-400">
                  {stats.learned_params.atr_multiplier?.toFixed(1) || 2.0}x
                </p>
              </div>
            </div>
            <p className="text-xs text-zinc-500 mt-3 text-center">
              Diese Werte werden automatisch angepasst basierend auf Trade-Ergebnissen
            </p>
          </CardContent>
        </Card>
      )}

      {/* Learning Log */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg text-white flex items-center gap-2">
            <Clock className="w-5 h-5 text-purple-400" />
            KI Learning Log
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-64">
            {stats?.recent_lessons && stats.recent_lessons.length > 0 ? (
              <div className="space-y-3">
                {stats.recent_lessons.slice().reverse().map((lesson, idx) => (
                  <div 
                    key={idx} 
                    className={`p-3 rounded-lg border ${
                      lesson.type === 'KI_TAKEOVER' 
                        ? 'bg-purple-900/30 border-purple-700'
                        : lesson.type === 'MISTAKE_LEARNING'
                        ? 'bg-red-900/30 border-red-700'
                        : 'bg-zinc-800/50 border-zinc-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        {lesson.type === 'KI_TAKEOVER' && <Brain className="w-4 h-4 text-purple-400" />}
                        {lesson.type === 'MISTAKE_LEARNING' && <AlertTriangle className="w-4 h-4 text-red-400" />}
                        {lesson.type === 'INITIAL_LEARNING' && <BookOpen className="w-4 h-4 text-blue-400" />}
                        <span className="text-sm font-medium text-white">
                          {lesson.message || lesson.type}
                        </span>
                      </div>
                      <span className="text-xs text-zinc-500">
                        {lesson.time ? format(new Date(lesson.time), 'HH:mm', { locale: de }) : ''}
                      </span>
                    </div>
                    {lesson.adjustments && lesson.adjustments.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {lesson.adjustments.map((adj, i) => (
                          <Badge key={i} variant="outline" className="text-xs bg-zinc-800">
                            {adj}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-zinc-500 py-8">
                <Brain className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Noch keine Lerneinträge</p>
                <p className="text-sm">Die KI beginnt nach den ersten Trades zu lernen</p>
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Recent Mistakes */}
      {stats?.recent_mistakes && stats.recent_mistakes.length > 0 && (
        <Card className="bg-zinc-900 border-red-900/50">
          <CardHeader>
            <CardTitle className="text-lg text-white flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              Letzte Fehler & Lektionen
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.recent_mistakes.map((mistake, idx) => (
                <div key={idx} className="p-3 bg-red-950/30 rounded-lg border border-red-900/50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-red-400">{mistake.symbol}</span>
                    <span className="text-sm text-red-300">{mistake.pnl_percent?.toFixed(1)}%</span>
                  </div>
                  <p className="text-sm text-zinc-400">
                    📚 <span className="text-zinc-300">{mistake.lesson_learned}</span>
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
