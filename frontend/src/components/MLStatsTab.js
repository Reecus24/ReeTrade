import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Brain, TrendingUp, TrendingDown, Clock, Target, Zap, Database, Trophy } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

const MLStatsTab = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000); // Update every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/ml/stats`, getAuthHeaders());
      setStats(response.data);
      setError(null);
    } catch (err) {
      setError('Fehler beim Laden der ML-Daten');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-zinc-500">
        <Brain className="w-12 h-12 mx-auto mb-4 animate-pulse" />
        <p>Lade KI-Daten...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-red-400">
        <p>{error}</p>
      </div>
    );
  }

  const progress = stats ? Math.min((stats.completed_trades / 100) * 100, 100) : 0;
  const isReady = stats?.ready_for_training;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="w-8 h-8 text-purple-500" />
          <div>
            <h2 className="text-xl font-bold text-white">KI Training</h2>
            <p className="text-sm text-zinc-500">Dein Bot lernt von jedem Trade</p>
          </div>
        </div>
        <Badge className={isReady ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}>
          {isReady ? '✅ Bereit für Training' : '⏳ Sammelt Daten...'}
        </Badge>
      </div>

      {/* Progress to 100 Trades */}
      <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-lg">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-zinc-400">Fortschritt bis erstes KI-Modell</span>
          <span className="text-sm font-mono text-purple-400">
            {stats?.completed_trades || 0} / 100 Trades
          </span>
        </div>
        <Progress value={progress} className="h-3 bg-zinc-800" />
        <p className="text-xs text-zinc-600 mt-2">
          {isReady 
            ? '🎉 Genug Daten gesammelt! KI-Modell kann trainiert werden.' 
            : `Noch ${100 - (stats?.completed_trades || 0)} Trades bis zum ersten Training.`}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Total Trades */}
        <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Database className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-zinc-500">Gesamt Snapshots</span>
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {stats?.total_snapshots || 0}
          </div>
        </div>

        {/* Completed */}
        <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-green-400" />
            <span className="text-xs text-zinc-500">Abgeschlossen</span>
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {stats?.completed_trades || 0}
          </div>
        </div>

        {/* Win Rate */}
        <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Trophy className="w-4 h-4 text-yellow-400" />
            <span className="text-xs text-zinc-500">Win Rate</span>
          </div>
          <div className={`text-2xl font-bold font-mono ${(stats?.win_rate || 0) >= 50 ? 'text-green-400' : 'text-red-400'}`}>
            {(stats?.win_rate || 0).toFixed(1)}%
          </div>
        </div>

        {/* Avg PnL */}
        <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-zinc-500">Ø PnL</span>
          </div>
          <div className={`text-2xl font-bold font-mono ${(stats?.avg_pnl_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(stats?.avg_pnl_percent || 0) >= 0 ? '+' : ''}{(stats?.avg_pnl_percent || 0).toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Winners vs Losers */}
      <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-lg">
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Gewinner vs Verlierer</h3>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                <span className="text-green-400">Gewinner</span>
              </div>
              <span className="font-mono text-green-400">{stats?.winners || 0}</span>
            </div>
            <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-green-500 transition-all duration-500"
                style={{ width: `${stats?.completed_trades ? (stats.winners / stats.completed_trades * 100) : 0}%` }}
              />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-red-400" />
                <span className="text-red-400">Verlierer</span>
              </div>
              <span className="font-mono text-red-400">{stats?.losers || 0}</span>
            </div>
            <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-red-500 transition-all duration-500"
                style={{ width: `${stats?.completed_trades ? (stats.losers / stats.completed_trades * 100) : 0}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-zinc-400" />
            <span className="text-xs text-zinc-500">Ø Haltezeit</span>
          </div>
          <div className="text-lg font-mono text-white">
            {Math.round(stats?.avg_hold_minutes || 0)} Min
          </div>
        </div>
        <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-zinc-400" />
            <span className="text-xs text-zinc-500">Gesamt PnL</span>
          </div>
          <div className={`text-lg font-mono ${(stats?.total_pnl_usdt || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(stats?.total_pnl_usdt || 0) >= 0 ? '+' : ''}${(stats?.total_pnl_usdt || 0).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div className="p-4 bg-purple-950/30 border border-purple-900/50 rounded-lg">
        <h4 className="text-sm font-medium text-purple-400 mb-2">🧠 Wie funktioniert das?</h4>
        <ul className="text-xs text-zinc-400 space-y-1">
          <li>• Bei jedem Kauf speichert der Bot alle Marktdaten (RSI, ADX, Volume, etc.)</li>
          <li>• Nach dem Verkauf wird das Ergebnis (Gewinn/Verlust) hinzugefügt</li>
          <li>• Nach 100+ Trades kann ein ML-Modell trainiert werden</li>
          <li>• Die KI lernt welche Bedingungen zu Gewinnen führen</li>
          <li>• Später ersetzt die KI den regelbasierten Bot</li>
        </ul>
      </div>

      {/* Open Trades */}
      {stats?.open_trades > 0 && (
        <div className="p-4 bg-zinc-900 border border-yellow-900/50 rounded-lg">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-yellow-400" />
            <span className="text-sm text-yellow-400">
              {stats.open_trades} offene Trades werden noch beobachtet...
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default MLStatsTab;
