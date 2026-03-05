import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Activity, TrendingUp, TrendingDown, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';
import { de } from 'date-fns/locale';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell
} from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return { headers: { Authorization: `Bearer ${token}` } };
};

const TradesTab = ({ marketType = 'spot' }) => {
  const [trades, setTrades] = useState([]);
  const [dailyPnl, setDailyPnl] = useState([]);
  const [pnlSummary, setPnlSummary] = useState(null);
  const [symbols, setSymbols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20;
  
  const [filterSymbol, setFilterSymbol] = useState('all');
  const [chartDays, setChartDays] = useState(30);
  
  const isSpot = marketType === 'spot';
  const tabColor = isSpot ? 'green' : 'orange';

  const fetchTrades = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        market_type: marketType
      });
      if (filterSymbol !== 'all') params.append('symbol', filterSymbol);
      
      const response = await axios.get(`${BACKEND_URL}/api/trades?${params}`, getAuthHeaders());
      setTrades(response.data.trades || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      console.error('Trades fetch error:', error);
    }
  }, [filterSymbol, offset, marketType]);

  const fetchDailyPnl = useCallback(async () => {
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/metrics/daily_pnl?days=${chartDays}&market_type=${marketType}`,
        getAuthHeaders()
      );
      setDailyPnl(response.data.data || []);
      setPnlSummary(response.data.summary || null);
    } catch (error) {
      console.error('PnL fetch error:', error);
    }
  }, [chartDays, marketType]);

  const fetchSymbols = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/trades/symbols`, getAuthHeaders());
      setSymbols(response.data.symbols || []);
    } catch (error) {}
  };

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([fetchTrades(), fetchDailyPnl(), fetchSymbols()]);
      setLoading(false);
    };
    loadAll();
  }, [fetchTrades, fetchDailyPnl]);

  const formatCurrency = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${Math.abs(value).toFixed(2)}`;
  };

  const formatPercent = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Activity className="w-6 h-6 text-zinc-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid={`trades-tab-${marketType}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className={`text-xl font-bold flex items-center gap-2 text-${tabColor}-500`}>
          {isSpot ? (
            <><TrendingUp className="w-5 h-5" /> SPOT History</>
          ) : (
            <><Activity className="w-5 h-5" /> FUTURES History</>
          )}
        </h2>
        <Badge className={`bg-${tabColor}-900/50 text-${tabColor}-400 border-${tabColor}-700`}>
          {total} Trades
        </Badge>
      </div>
      
      {/* Summary Cards */}
      {pnlSummary && (
        <div className="grid grid-cols-4 gap-4">
          <div className={`p-4 bg-zinc-950 border border-${tabColor}-900/30 rounded-lg`}>
            <div className="text-xs text-zinc-500 mb-1">Total PnL ({chartDays}d)</div>
            <div className={`text-2xl font-bold font-mono ${pnlSummary.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatCurrency(pnlSummary.total_pnl)}
            </div>
          </div>
          <div className={`p-4 bg-zinc-950 border border-${tabColor}-900/30 rounded-lg`}>
            <div className="text-xs text-zinc-500 mb-1">Trades</div>
            <div className="text-2xl font-bold font-mono">{pnlSummary.total_trades}</div>
          </div>
          <div className={`p-4 bg-zinc-950 border border-${tabColor}-900/30 rounded-lg`}>
            <div className="text-xs text-zinc-500 mb-1">Win Rate</div>
            <div className={`text-2xl font-bold font-mono ${pnlSummary.win_rate >= 50 ? 'text-green-500' : 'text-red-500'}`}>
              {pnlSummary.win_rate}%
            </div>
          </div>
          <div className={`p-4 bg-zinc-950 border border-${tabColor}-900/30 rounded-lg`}>
            <div className="text-xs text-zinc-500 mb-1">W/L Tage</div>
            <div className="text-2xl font-bold font-mono">
              <span className="text-green-500">{pnlSummary.winning_days}</span>
              <span className="text-zinc-500">/</span>
              <span className="text-red-500">{pnlSummary.losing_days}</span>
            </div>
          </div>
        </div>
      )}

      {/* Daily PnL Chart */}
      <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Daily PnL</h3>
          <Select value={chartDays.toString()} onValueChange={(v) => setChartDays(parseInt(v))}>
            <SelectTrigger className="w-32 bg-zinc-900 border-zinc-700">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7 Tage</SelectItem>
              <SelectItem value="14">14 Tage</SelectItem>
              <SelectItem value="30">30 Tage</SelectItem>
              <SelectItem value="90">90 Tage</SelectItem>
            </SelectContent>
          </Select>
        </div>
        
        <div className="h-48">
          {dailyPnl.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dailyPnl}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis 
                  dataKey="date" 
                  tick={{ fill: '#666', fontSize: 10 }}
                  tickFormatter={(d) => format(new Date(d), 'd.M', { locale: de })}
                />
                <YAxis tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }}
                  labelFormatter={(d) => format(new Date(d), 'dd.MM.yyyy', { locale: de })}
                  formatter={(value) => [formatCurrency(value), 'PnL']}
                />
                <ReferenceLine y={0} stroke="#666" />
                <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                  {dailyPnl.map((entry, idx) => (
                    <Cell key={idx} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-zinc-500">
              Keine Daten für diesen Zeitraum
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <Select value={filterSymbol} onValueChange={(v) => { setFilterSymbol(v); setOffset(0); }}>
          <SelectTrigger className="w-40 bg-zinc-900 border-zinc-700">
            <SelectValue placeholder="Alle Symbole" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Symbole</SelectItem>
            {symbols.map(s => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        
        <Button onClick={() => fetchTrades()} variant="ghost" size="sm">
          <RefreshCw className="w-4 h-4" />
        </Button>
        
        <div className="text-sm text-zinc-500 ml-auto">
          {total} Trades total
        </div>
      </div>

      {/* Trades Table */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-zinc-900 text-xs text-zinc-500">
            <tr>
              <th className="text-left p-3">Zeit</th>
              <th className="text-left p-3">Symbol</th>
              <th className="text-left p-3">Side</th>
              <th className="text-right p-3">Qty</th>
              <th className="text-right p-3">Entry</th>
              <th className="text-right p-3">Exit</th>
              <th className="text-right p-3">PnL</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-zinc-500">
                  Keine Trades gefunden
                </td>
              </tr>
            ) : (
              trades.map((trade, idx) => (
                <tr key={idx} className="border-t border-zinc-800 hover:bg-zinc-900/50">
                  <td className="p-3 text-sm text-zinc-400 font-mono">
                    {format(new Date(trade.ts), 'dd.MM HH:mm', { locale: de })}
                  </td>
                  <td className="p-3 font-medium">{trade.symbol}</td>
                  <td className="p-3">
                    <Badge className={trade.side === 'BUY' 
                      ? 'bg-green-500/10 text-green-500 border-0' 
                      : 'bg-red-500/10 text-red-500 border-0'
                    }>
                      {trade.side}
                    </Badge>
                  </td>
                  <td className="p-3 text-right font-mono text-sm">{trade.qty?.toFixed(4)}</td>
                  <td className="p-3 text-right font-mono text-sm">${trade.entry?.toFixed(4)}</td>
                  <td className="p-3 text-right font-mono text-sm">
                    {trade.exit ? `$${trade.exit.toFixed(4)}` : '-'}
                  </td>
                  <td className="p-3 text-right font-mono text-sm">
                    {trade.pnl !== undefined && trade.pnl !== null ? (
                      <div className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                        <div>{formatCurrency(trade.pnl)}</div>
                        <div className="text-xs opacity-70">
                          {formatPercent(trade.pnl_pct || 0)}
                        </div>
                      </div>
                    ) : '-'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        
        {/* Pagination */}
        {total > limit && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-800">
            <div className="text-sm text-zinc-500">
              {offset + 1} - {Math.min(offset + limit, total)} von {total}
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                variant="ghost"
                size="sm"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= total}
                variant="ghost"
                size="sm"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TradesTab;
