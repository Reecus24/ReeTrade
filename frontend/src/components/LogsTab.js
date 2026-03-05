import React, { useRef, useEffect } from 'react';
import { Activity, Terminal } from 'lucide-react';
import { format } from 'date-fns';

const LogsTab = ({ logs }) => {
  const logsEndRef = useRef(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const getLevelColor = (level) => {
    switch (level) {
      case 'ERROR':
        return 'text-red-400';
      case 'WARNING':
        return 'text-yellow-400';
      case 'INFO':
        return 'text-green-400';
      case 'DEBUG':
        return 'text-cyan-400';
      default:
        return 'text-zinc-400';
    }
  };

  const getLogHighlight = (msg) => {
    if (msg?.includes('[RL]')) return 'border-l-2 border-purple-500 pl-2';
    if (msg?.includes('[LIVE]')) return 'border-l-2 border-red-500 pl-2';
    if (msg?.includes('[ERROR]') || msg?.includes('ERROR')) return 'border-l-2 border-red-500 pl-2';
    if (msg?.includes('[SMART EXIT]')) return 'border-l-2 border-cyan-500 pl-2';
    if (msg?.includes('[ML]')) return 'border-l-2 border-blue-500 pl-2';
    return '';
  };

  return (
    <div className="space-y-4" data-testid="logs-tab">
      {/* Terminal Window */}
      <div className="cyber-panel overflow-hidden">
        {/* Terminal Header */}
        <div className="flex items-center justify-between p-3 border-b border-cyan-500/20 bg-black/50">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
            </div>
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-cyan-400" />
              <span className="font-cyber text-xs text-cyan-400 tracking-widest">SYSTEM LOG</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1">
              <Activity className="w-3 h-3 text-green-400 animate-pulse" />
              <span className="text-[10px] text-green-400 font-mono-cyber">LIVE</span>
            </div>
            <span className="text-[10px] text-zinc-600 font-mono-cyber">
              {logs.length} ENTRIES
            </span>
          </div>
        </div>

        {/* Terminal Body */}
        <div
          className="bg-black p-4 font-mono-cyber text-xs h-[500px] overflow-y-auto terminal"
          data-testid="logs-terminal"
        >
          {logs.length === 0 ? (
            <div className="text-center py-12">
              <Terminal className="w-12 h-12 mx-auto text-cyan-500/30 mb-4" />
              <p className="text-zinc-600 font-mono-cyber">AWAITING LOG DATA...</p>
              <p className="text-zinc-700 text-[10px] mt-2">System will stream logs here</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {logs.map((log, idx) => {
                const timestamp = new Date(log.ts);
                const timeStr = format(timestamp, 'HH:mm:ss');

                return (
                  <div
                    key={idx}
                    className={`terminal-line hover:bg-cyan-500/5 py-1 ${getLogHighlight(log.msg)}`}
                    data-testid={`log-entry-${idx}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-zinc-700 flex-shrink-0 w-16">{timeStr}</span>
                      <span className={`flex-shrink-0 w-16 ${getLevelColor(log.level)}`}>
                        {log.level}
                      </span>
                      <span className="text-zinc-300 flex-1 break-all">
                        {log.msg?.includes('[RL]') ? (
                          <span className="text-purple-400">{log.msg}</span>
                        ) : log.msg?.includes('[LIVE]') ? (
                          <span className="text-red-300">{log.msg}</span>
                        ) : log.msg?.includes('[SMART EXIT]') ? (
                          <span className="text-cyan-300">{log.msg}</span>
                        ) : (
                          log.msg
                        )}
                      </span>
                    </div>
                    {log.context && Object.keys(log.context).length > 0 && (
                      <div className="ml-36 text-zinc-600 text-[10px] mt-1 bg-zinc-900/50 p-1">
                        {JSON.stringify(log.context)}
                      </div>
                    )}
                  </div>
                );
              })}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>

        {/* Terminal Footer */}
        <div className="flex items-center justify-between p-2 border-t border-cyan-500/20 bg-black/80">
          <div className="flex items-center gap-4 text-[10px] font-mono-cyber">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 bg-red-500"></div>
              <span className="text-zinc-600">ERROR</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 bg-yellow-500"></div>
              <span className="text-zinc-600">WARN</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 bg-green-500"></div>
              <span className="text-zinc-600">INFO</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 bg-cyan-500"></div>
              <span className="text-zinc-600">DEBUG</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 bg-purple-500"></div>
              <span className="text-zinc-600">RL-AI</span>
            </div>
          </div>
          <div className="text-[10px] text-zinc-700 font-mono-cyber">
            AUTO-SCROLL ENABLED
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { level: 'ERROR', color: 'red' },
          { level: 'WARNING', color: 'yellow' },
          { level: 'INFO', color: 'green' },
          { level: 'DEBUG', color: 'cyan' },
          { level: 'RL', color: 'purple', filter: (log) => log.msg?.includes('[RL]') }
        ].map(({ level, color, filter }) => {
          const count = filter 
            ? logs.filter(filter).length 
            : logs.filter((log) => log.level === level).length;
          return (
            <div 
              key={level} 
              className={`p-3 bg-black/50 border border-${color}-500/20`}
              data-testid={`log-count-${level.toLowerCase()}`}
            >
              <div className={`text-[10px] text-${color}-400 font-mono-cyber mb-1`}>{level}</div>
              <div className={`text-xl font-cyber text-${color}-400`}>{count}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default LogsTab;
