import React from 'react';
import { Activity } from 'lucide-react';

const StrategieTab = ({ status }) => {
  if (!status) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 text-zinc-600 animate-spin" />
      </div>
    );
  }

  const { settings } = status;

  const params = [
    { label: 'EMA Fast', value: settings.ema_fast, unit: 'periods' },
    { label: 'EMA Slow', value: settings.ema_slow, unit: 'periods' },
    { label: 'RSI Period', value: settings.rsi_period, unit: 'periods' },
    { label: 'RSI Min', value: settings.rsi_min, unit: '' },
    { label: 'RSI Overbought', value: settings.rsi_overbought, unit: '' },
  ];

  const riskParams = [
    { label: 'Risk per Trade', value: `${(settings.risk_per_trade * 100).toFixed(1)}%`, desc: 'Max risk per single position' },
    { label: 'Max Positions', value: settings.max_positions, desc: 'Maximum concurrent positions' },
    { label: 'Max Daily Loss', value: `${(settings.max_daily_loss * 100).toFixed(1)}%`, desc: 'Daily loss limit before stopping' },
    { label: 'Take Profit R:R', value: `1:${settings.take_profit_rr}`, desc: 'Risk:Reward ratio for take profit' },
    { label: 'ATR Stop', value: settings.atr_stop ? 'Enabled' : 'Disabled', desc: 'Use ATR for stop loss calculation' },
    { label: 'Fees', value: `${settings.fee_bps} bps`, desc: 'Trading fees per transaction' },
    { label: 'Slippage', value: `${settings.slippage_bps} bps`, desc: 'Expected slippage' },
  ];

  return (
    <div className="space-y-6" data-testid="strategie-tab">
      {/* Strategy Overview */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Strategie: EMA Crossover + RSI Filter</h3>
        <div className="space-y-3 text-sm text-zinc-400">
          <p className="leading-relaxed">
            <strong className="text-white">Entry Signal:</strong> EMA {settings.ema_fast} kreuzt über EMA {settings.ema_slow} UND RSI ist zwischen {settings.rsi_min} und {settings.rsi_overbought}.
          </p>
          <p className="leading-relaxed">
            <strong className="text-white">Exit Signal:</strong> Stop Loss oder Take Profit wird erreicht, oder EMA crossover bearish.
          </p>
          <p className="leading-relaxed">
            <strong className="text-white">Timeframe:</strong> 15 Minuten Kerzen
          </p>
          <p className="leading-relaxed">
            <strong className="text-white">Universe:</strong> Top 20 USDT Spot Pairs nach 24h Volumen
          </p>
        </div>
      </div>

      {/* Strategy Parameters */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Strategie-Parameter</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {params.map((param, idx) => (
            <div key={idx} className="p-4 bg-zinc-900 border border-zinc-800 rounded" data-testid={`strategy-param-${idx}`}>
              <div className="text-xs text-zinc-500 mb-1">{param.label}</div>
              <div className="text-xl font-bold font-mono">
                {param.value} <span className="text-sm text-zinc-500">{param.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Management */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Risk Management</h3>
        <div className="space-y-3">
          {riskParams.map((param, idx) => (
            <div key={idx} className="flex items-center justify-between py-3 border-b border-zinc-900 last:border-0" data-testid={`risk-param-${idx}`}>
              <div>
                <div className="text-sm font-medium text-white">{param.label}</div>
                <div className="text-xs text-zinc-500">{param.desc}</div>
              </div>
              <div className="text-sm font-mono font-bold text-zinc-300">{param.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Market Info */}
      {settings.top_pairs && settings.top_pairs.length > 0 && (
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Top Pairs (wird täglich aktualisiert)</h3>
          <div className="flex flex-wrap gap-2">
            {settings.top_pairs.slice(0, 10).map((pair, idx) => (
              <div key={idx} className="px-3 py-1 bg-zinc-900 border border-zinc-800 rounded text-xs font-mono" data-testid={`top-pair-${idx}`}>
                {pair}
              </div>
            ))}
            {settings.top_pairs.length > 10 && (
              <div className="px-3 py-1 text-xs text-zinc-500">
                +{settings.top_pairs.length - 10} more
              </div>
            )}
          </div>
          {settings.last_pairs_refresh && (
            <div className="mt-4 text-xs text-zinc-500">
              Letztes Update: {new Date(settings.last_pairs_refresh).toLocaleString('de-DE')}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default StrategieTab;
