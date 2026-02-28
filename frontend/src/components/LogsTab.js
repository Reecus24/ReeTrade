import React, { useRef, useEffect } from 'react';
import { Activity } from 'lucide-react';
import { format } from 'date-fns';

const LogsTab = ({ logs }) => {
  const logsEndRef = useRef(null);

  useEffect(() => {
    // Auto-scroll to bottom
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const getLevelColor = (level) => {
    switch (level) {
      case 'ERROR':
        return 'text-red-500';
      case 'WARNING':
        return 'text-yellow-500';
      case 'INFO':
        return 'text-green-500';
      case 'DEBUG':
        return 'text-blue-500';
      default:
        return 'text-zinc-400';
    }
  };

  const getLevelBadge = (level) => {
    const colors = {
      ERROR: 'bg-red-500/10 text-red-500 border-red-500/20',
      WARNING: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
      INFO: 'bg-green-500/10 text-green-500 border-green-500/20',
      DEBUG: 'bg-blue-500/10 text-blue-500 border-blue-500/20'
    };
    return colors[level] || 'bg-zinc-800 text-zinc-400';
  };

  return (
    <div className="space-y-4" data-testid="logs-tab">
      {/* Terminal Header */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg">
        <div className="flex items-center justify-between p-4 border-b border-zinc-900">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-green-500 animate-pulse" />
            <h3 className="text-sm font-semibold font-mono">LIVE LOG STREAM</h3>
          </div>
          <div className="text-xs text-zinc-500 font-mono">
            {logs.length} entries
          </div>
        </div>

        {/* Terminal Body */}
        <div
          className="bg-black p-4 font-mono text-xs h-[500px] overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-black"
          data-testid="logs-terminal"
        >
          {logs.length === 0 ? (
            <div className="text-zinc-600 text-center py-8">
              Waiting for log entries...
            </div>
          ) : (
            <div className="space-y-1">
              {logs.map((log, idx) => {
                const timestamp = new Date(log.ts);
                const timeStr = format(timestamp, 'HH:mm:ss');

                return (
                  <div
                    key={idx}
                    className="hover:bg-white/5 px-2 py-1 rounded transition-colors"
                    data-testid={`log-entry-${idx}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-zinc-600 flex-shrink-0">{timeStr}</span>
                      <span className={`flex-shrink-0 ${getLevelColor(log.level)}`}>
                        [{log.level}]
                      </span>
                      <span className="text-zinc-300 flex-1">{log.msg}</span>
                    </div>
                    {log.context && Object.keys(log.context).length > 0 && (
                      <div className="ml-24 text-zinc-500 text-[10px] mt-1">
                        {JSON.stringify(log.context, null, 2)}
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
        <div className="flex items-center justify-between p-2 border-t border-zinc-900 bg-zinc-950">
          <div className="flex items-center gap-4 text-[10px] text-zinc-600">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-red-500 rounded-full"></div>
              ERROR
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
              WARNING
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              INFO
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              DEBUG
            </div>
          </div>
          <div className="text-[10px] text-zinc-600">Auto-scroll enabled</div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {['ERROR', 'WARNING', 'INFO', 'DEBUG'].map((level) => {
          const count = logs.filter((log) => log.level === level).length;
          return (
            <div key={level} className="p-3 bg-zinc-950 border border-zinc-800 rounded" data-testid={`log-count-${level.toLowerCase()}`}>
              <div className="text-xs text-zinc-500 mb-1">{level}</div>
              <div className={`text-xl font-bold font-mono ${getLevelColor(level)}`}>{count}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default LogsTab;
