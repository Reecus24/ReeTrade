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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Activity, TrendingUp, TrendingDown, ChevronLeft, ChevronRight, Filter, RefreshCw } from 'lucide-react';
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
  return {
    headers: {
      Authorization: `Bearer ${token}`
    }
  };
};

const TradesTab = ({ currentMode }) => {
  const [trades, setTrades] = useState([]);
  const [dailyPnl, setDailyPnl] = useState([]);
  const [pnlSummary, setPnlSummary] = useState(null);
  const [symbols, setSymbols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20;
  
  // Filters
  const [filterMode, setFilterMode] = useState(currentMode || 'paper');
  const [filterSymbol, setFilterSymbol] = useState('all');
  const [chartDays, setChartDays] = useState(30);

  const fetchTrades = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString()
      });
      if (filterMode !== 'all') params.append('mode', filterMode);
      if (filterSymbol !== 'all') params.append('symbol', filterSymbol);
      
      const response = await axios.get(
        `${BACKEND_URL}/api/trades?${params}`,
        getAuthHeaders()
      );
      setTrades(response.data.trades || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      console.error('Trades fetch error:', error);
    }
  }, [filterMode, filterSymbol, offset]);

  const fetchDailyPnl = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        days: chartDays.toString()
      });
      if (filterMode !== 'all') params.append('mode', filterMode);
      
      const response = await axios.get(
        `${BACKEND_URL}/api/metrics/daily_pnl?${params}`,
        getAuthHeaders()
      );
      setDailyPnl(response.data.data || []);
      setPnlSummary(response.data.summary || null);
    } catch (error) {
      console.error('Daily PnL fetch error:', error);
    }
  }, [filterMode, chartDays]);

  const fetchSymbols = async () => {
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/trades/symbols`,
        getAuthHeaders()
      );
      setSymbols(response.data.symbols || []);
    } catch (error) {
      console.error('Symbols fetch error:', error);
    }
  };

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      await Promise.all([fetchTrades(), fetchDailyPnl(), fetchSymbols()]);
      setLoading(false);
    };
    fetchAll();
  }, [fetchTrades, fetchDailyPnl]);

  useEffect(() => {
    setOffset(0);
  }, [filterMode, filterSymbol]);

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(value || 0);
  };

  const formatPrice = (value) => {
    if (!value) return '-';
    if (value < 0.01) return value.toFixed(8);
    if (value < 1) return value.toFixed(6);
    return value.toFixed(4);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    try {
      return format(new Date(dateStr), 'dd.MM.yy HH:mm', { locale: de });
    } catch {
      return dateStr;
    }
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-3 shadow-lg">
          <p className="text-zinc-400 text-sm mb-1">
            {format(new Date(label), 'dd. MMM yyyy', { locale: de })}
          </p>
          <p className={`text-lg font-bold ${data.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {data.pnl >= 0 ? '+' : ''}{formatCurrency(data.pnl)}
          </p>
          <p className="text-xs text-zinc-500">
            {data.trades_count} Trade(s) • {data.wins}W / {data.losses}L
          </p>
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 text-zinc-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="trades-tab">
      {/* Daily PnL Chart */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-500" />
            Daily PnL
          </h3>
          <div className="flex items-center gap-3">
            <Select value={chartDays.toString()} onValueChange={(v) => setChartDays(parseInt(v))}>
              <SelectTrigger className="w-24 bg-zinc-900 border-zinc-800" data-testid="chart-days-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">7 Tage</SelectItem>
                <SelectItem value="30">30 Tage</SelectItem>
                <SelectItem value="90">90 Tage</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterMode} onValueChange={setFilterMode}>
              <SelectTrigger className="w-28 bg-zinc-900 border-zinc-800" data-testid="mode-filter-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="paper">Paper</SelectItem>
                <SelectItem value="live">Live</SelectItem>
                <SelectItem value="all">Alle</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Summary Stats */}
        {pnlSummary && (
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="p-3 bg-zinc-900 rounded-lg">
              <div className="text-xs text-zinc-500">Total PnL</div>
              <div className={`text-lg font-bold ${pnlSummary.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {pnlSummary.total_pnl >= 0 ? '+' : ''}{formatCurrency(pnlSummary.total_pnl)}
              </div>
            </div>
            <div className="p-3 bg-zinc-900 rounded-lg">
              <div className="text-xs text-zinc-500">Trades</div>
              <div className="text-lg font-bold text-white">{pnlSummary.total_trades}</div>
            </div>
            <div className="p-3 bg-zinc-900 rounded-lg">
              <div className="text-xs text-zinc-500">Winning Days</div>
              <div className="text-lg font-bold text-green-500">{pnlSummary.winning_days}</div>
            </div>
            <div className="p-3 bg-zinc-900 rounded-lg">
              <div className="text-xs text-zinc-500">Win Rate</div>
              <div className="text-lg font-bold text-white">{pnlSummary.win_rate}%</div>
            </div>
          </div>
        )}

        {/* Chart */}
        <div className="h-64" data-testid="daily-pnl-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={dailyPnl} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis 
                dataKey="date" 
                tick={{ fill: '#71717a', fontSize: 10 }}
                tickFormatter={(val) => {
                  try {
                    return format(new Date(val), 'dd.MM');
                  } catch {
                    return val;
                  }
                }}
              />
              <YAxis 
                tick={{ fill: '#71717a', fontSize: 10 }}
                tickFormatter={(val) => `$${val}`}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#52525b" strokeWidth={2} />
              <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                {dailyPnl.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'}
                    opacity={entry.pnl === 0 ? 0.3 : 1}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trade History */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Filter className="w-5 h-5 text-blue-500" />
            Trade History
          </h3>
          <div className="flex items-center gap-3">
            <Select value={filterSymbol} onValueChange={setFilterSymbol}>
              <SelectTrigger className="w-36 bg-zinc-900 border-zinc-800" data-testid="symbol-filter-select">
                <SelectValue placeholder="Symbol" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Alle Symbols</SelectItem>
                {symbols.map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => { fetchTrades(); fetchDailyPnl(); }}
              data-testid="refresh-trades-button"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Trade Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="trades-table">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left py-3 px-2 text-zinc-500 font-medium">Datum</th>
                <th className="text-left py-3 px-2 text-zinc-500 font-medium">Symbol</th>
                <th className="text-left py-3 px-2 text-zinc-500 font-medium">Side</th>
                <th className="text-right py-3 px-2 text-zinc-500 font-medium">Entry → Exit</th>
                <th className="text-right py-3 px-2 text-zinc-500 font-medium">Qty</th>
                <th className="text-right py-3 px-2 text-zinc-500 font-medium">Einsatz</th>
                <th className="text-right py-3 px-2 text-zinc-500 font-medium">PnL</th>
                <th className="text-right py-3 px-2 text-zinc-500 font-medium">%</th>
                <th className="text-left py-3 px-2 text-zinc-500 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-zinc-500">
                    Keine Trades gefunden
                  </td>
                </tr>
              ) : (
                trades.map((trade, idx) => {
                  const notional = trade.notional || (trade.qty * trade.entry);
                  const pnlPct = trade.pnl_pct || (trade.pnl && notional ? (trade.pnl / notional) * 100 : 0);
                  const isClosed = trade.exit !== null && trade.exit !== undefined;
                  
                  return (
                    <tr 
                      key={idx} 
                      className="border-b border-zinc-900 hover:bg-zinc-900/50 cursor-pointer transition-colors"
                      onClick={() => setSelectedTrade(trade)}
                      data-testid={`trade-row-${idx}`}
                    >
                      <td className="py-3 px-2 text-zinc-400">{formatDate(trade.ts)}</td>
                      <td className="py-3 px-2 text-white font-medium">{trade.symbol}</td>
                      <td className="py-3 px-2">
                        <Badge className={`${
                          trade.side === 'BUY' 
                            ? 'bg-green-500/10 text-green-500 border-green-500/20' 
                            : 'bg-red-500/10 text-red-500 border-red-500/20'
                        }`}>
                          {trade.side}
                        </Badge>
                      </td>
                      <td className="text-right py-3 px-2 text-zinc-300">
                        ${formatPrice(trade.entry)} → {isClosed ? `$${formatPrice(trade.exit)}` : '-'}
                      </td>
                      <td className="text-right py-3 px-2 text-zinc-400">
                        {trade.qty?.toLocaleString('de-DE', { maximumFractionDigits: 4 })}
                      </td>
                      <td className="text-right py-3 px-2 text-zinc-400">
                        {formatCurrency(notional)}
                      </td>
                      <td className={`text-right py-3 px-2 font-medium ${
                        !isClosed ? 'text-zinc-500' :
                        trade.pnl > 0 ? 'text-green-500' : 
                        trade.pnl < 0 ? 'text-red-500' : 'text-zinc-400'
                      }`}>
                        {isClosed ? (
                          <>
                            {trade.pnl > 0 ? '+' : ''}{formatCurrency(trade.pnl)}
                          </>
                        ) : (
                          <span className="text-yellow-500">OPEN</span>
                        )}
                      </td>
                      <td className={`text-right py-3 px-2 ${
                        !isClosed ? 'text-zinc-500' :
                        pnlPct > 0 ? 'text-green-500' : 
                        pnlPct < 0 ? 'text-red-500' : 'text-zinc-400'
                      }`}>
                        {isClosed ? `${pnlPct > 0 ? '+' : ''}${pnlPct.toFixed(2)}%` : '-'}
                      </td>
                      <td className="py-3 px-2">
                        <Badge className={`text-xs ${
                          !isClosed ? 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20' :
                          trade.reason?.includes('TP') ? 'bg-green-500/10 text-green-500 border-green-500/20' :
                          trade.reason?.includes('SL') ? 'bg-red-500/10 text-red-500 border-red-500/20' :
                          'bg-zinc-800 text-zinc-400'
                        }`}>
                          {!isClosed ? 'OPEN' : 
                           trade.reason?.includes('TP') ? 'TP' :
                           trade.reason?.includes('SL') ? 'SL' : 
                           trade.mode?.toUpperCase() || 'CLOSED'}
                        </Badge>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > limit && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-zinc-800">
            <span className="text-sm text-zinc-500">
              {offset + 1} - {Math.min(offset + limit, total)} von {total} Trades
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="bg-zinc-900 border-zinc-800"
                data-testid="prev-page-button"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= total}
                className="bg-zinc-900 border-zinc-800"
                data-testid="next-page-button"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Trade Detail Sheet */}
      <Sheet open={!!selectedTrade} onOpenChange={() => setSelectedTrade(null)}>
        <SheetContent className="bg-zinc-950 border-zinc-800 text-white w-[400px]">
          <SheetHeader>
            <SheetTitle className="text-white flex items-center gap-2">
              {selectedTrade?.symbol}
              <Badge className={`${
                selectedTrade?.side === 'BUY' 
                  ? 'bg-green-500/10 text-green-500' 
                  : 'bg-red-500/10 text-red-500'
              }`}>
                {selectedTrade?.side}
              </Badge>
            </SheetTitle>
            <SheetDescription className="text-zinc-500">
              Trade Details
            </SheetDescription>
          </SheetHeader>
          
          {selectedTrade && (
            <div className="mt-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-zinc-900 rounded-lg">
                  <div className="text-xs text-zinc-500">Datum</div>
                  <div className="text-sm text-white">{formatDate(selectedTrade.ts)}</div>
                </div>
                <div className="p-3 bg-zinc-900 rounded-lg">
                  <div className="text-xs text-zinc-500">Mode</div>
                  <div className="text-sm text-white uppercase">{selectedTrade.mode}</div>
                </div>
              </div>
              
              <div className="p-3 bg-zinc-900 rounded-lg">
                <div className="text-xs text-zinc-500 mb-2">Entry → Exit</div>
                <div className="flex items-center gap-2 text-lg font-mono">
                  <span className="text-white">${formatPrice(selectedTrade.entry)}</span>
                  <span className="text-zinc-500">→</span>
                  <span className={selectedTrade.exit ? 'text-white' : 'text-yellow-500'}>
                    {selectedTrade.exit ? `$${formatPrice(selectedTrade.exit)}` : 'OPEN'}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-zinc-900 rounded-lg">
                  <div className="text-xs text-zinc-500">Qty</div>
                  <div className="text-sm text-white font-mono">
                    {selectedTrade.qty?.toLocaleString('de-DE', { maximumFractionDigits: 8 })}
                  </div>
                </div>
                <div className="p-3 bg-zinc-900 rounded-lg">
                  <div className="text-xs text-zinc-500">Einsatz</div>
                  <div className="text-sm text-white">
                    {formatCurrency(selectedTrade.notional || (selectedTrade.qty * selectedTrade.entry))}
                  </div>
                </div>
              </div>
              
              {selectedTrade.exit && (
                <div className="p-4 bg-zinc-900 rounded-lg">
                  <div className="text-xs text-zinc-500 mb-2">PnL</div>
                  <div className={`text-2xl font-bold ${
                    selectedTrade.pnl > 0 ? 'text-green-500' : 
                    selectedTrade.pnl < 0 ? 'text-red-500' : 'text-white'
                  }`}>
                    {selectedTrade.pnl > 0 ? '+' : ''}{formatCurrency(selectedTrade.pnl)}
                    <span className="text-sm ml-2">
                      ({selectedTrade.pnl_pct > 0 ? '+' : ''}{(selectedTrade.pnl_pct || 0).toFixed(2)}%)
                    </span>
                  </div>
                </div>
              )}
              
              {selectedTrade.fees_paid && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-zinc-900 rounded-lg">
                    <div className="text-xs text-zinc-500">Fees</div>
                    <div className="text-sm text-orange-400">
                      -{formatCurrency(selectedTrade.fees_paid)}
                    </div>
                  </div>
                  {selectedTrade.slippage_cost && (
                    <div className="p-3 bg-zinc-900 rounded-lg">
                      <div className="text-xs text-zinc-500">Slippage</div>
                      <div className="text-sm text-orange-400">
                        -{formatCurrency(selectedTrade.slippage_cost)}
                      </div>
                    </div>
                  )}
                </div>
              )}
              
              {selectedTrade.reason && (
                <div className="p-3 bg-zinc-900 rounded-lg">
                  <div className="text-xs text-zinc-500">Reason</div>
                  <div className="text-sm text-zinc-300">{selectedTrade.reason}</div>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
};

export default TradesTab;
