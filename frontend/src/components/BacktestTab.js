import React, { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    headers: {
      Authorization: `Bearer ${token}`
    }
  };
};

const BacktestTab = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const runBacktest = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${BACKEND_URL}/api/backtest/run`, {}, getAuthHeaders());
      setResult(response.data);
      toast.success('Backtest abgeschlossen');
    } catch (error) {
      toast.error('Backtest fehlgeschlagen: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD'
    }).format(value || 0);
  };

  return (
    <div className="space-y-6" data-testid="backtest-tab">
      {/* Header */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold mb-2">Backtest Runner</h3>
            <p className="text-sm text-zinc-400">
              Teste die Strategie mit historischen 15m-Daten der Top-5-Pairs (~5 Tage)
            </p>
          </div>
          <Button
            onClick={runBacktest}
            disabled={loading}
            className="bg-white text-black hover:bg-gray-200 font-medium"
            data-testid="run-backtest-button"
          >
            {loading ? (
              <>
                <Activity className="w-4 h-4 mr-2 animate-spin" />
                Läuft...
              </>
            ) : (
              <>
                <TrendingUp className="w-4 h-4 mr-2" />
                Backtest starten
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="backtest-total-trades">
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Total Trades</div>
              <div className="text-2xl font-bold font-mono">{result.total_trades}</div>
            </div>

            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="backtest-win-rate">
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Win Rate</div>
              <div className="text-2xl font-bold font-mono text-green-500">{result.win_rate.toFixed(1)}%</div>
              <div className="text-xs text-zinc-500 mt-1">
                {result.winning_trades}W / {result.losing_trades}L
              </div>
            </div>

            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="backtest-total-pnl">
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Total PnL</div>
              <div className={`text-2xl font-bold font-mono ${result.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {result.total_pnl >= 0 ? '+' : ''}{result.total_pnl.toFixed(2)}%
              </div>
            </div>

            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg" data-testid="backtest-max-drawdown">
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Max Drawdown</div>
              <div className="text-2xl font-bold font-mono text-red-500">{result.max_drawdown.toFixed(2)}%</div>
            </div>
          </div>

          {/* Trades Table */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Trade History ({result.trades.length})</h3>
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-zinc-950">
                  <tr className="border-b border-zinc-800">
                    <th className="text-left py-2 text-zinc-500 font-medium">Time</th>
                    <th className="text-left py-2 text-zinc-500 font-medium">Symbol</th>
                    <th className="text-right py-2 text-zinc-500 font-medium">Entry</th>
                    <th className="text-right py-2 text-zinc-500 font-medium">Exit</th>
                    <th className="text-right py-2 text-zinc-500 font-medium">PnL %</th>
                    <th className="text-right py-2 text-zinc-500 font-medium">Result</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {result.trades.map((trade, idx) => (
                    <tr key={idx} className="border-b border-zinc-900 last:border-0" data-testid={`backtest-trade-${idx}`}>
                      <td className="py-3 text-xs">
                        {new Date(trade.ts).toLocaleString('de-DE', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </td>
                      <td className="py-3">{trade.symbol}</td>
                      <td className="text-right py-3">${trade.entry.toFixed(4)}</td>
                      <td className="text-right py-3">${trade.exit.toFixed(4)}</td>
                      <td className={`text-right py-3 ${trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}%
                      </td>
                      <td className="text-right py-3">
                        {trade.pnl >= 0 ? (
                          <TrendingUp className="w-4 h-4 text-green-500 inline" />
                        ) : (
                          <TrendingDown className="w-4 h-4 text-red-500 inline" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!result && !loading && (
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-12 text-center">
          <div className="text-zinc-600 mb-2">
            <Activity className="w-12 h-12 mx-auto mb-4" />
          </div>
          <p className="text-zinc-400">Klicke auf "Backtest starten" um die Strategie zu testen</p>
        </div>
      )}
    </div>
  );
};

export default BacktestTab;
