import React, { useState, useEffect } from 'react';

const LABELS = {
  market: '📡 Market Selection',
  strategy: '🧠 Strategy ML',
  decision: '🎯 Decision Engine',
  trade: '💼 Trade Decision',
  exec: '⚡ Execution',
};

const COLORS = {
  market: 'border-blue-500',
  strategy: 'border-purple-500',
  decision: 'border-amber-500',
  trade: 'border-green-500',
  exec: 'border-red-500',
};

export default function LiveFlow() {
  const [logs, setLogs] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLogs = () => {
      fetch('/api/live-flow')
        .then(res => res.json())
        .then(data => {
          setLogs(data.logs || {});
          setLoading(false);
        })
        .catch(() => {});
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="p-6 text-white">Carregando live flow...</div>;

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-white mb-6">Live Flow</h1>
      <div className="grid grid-cols-1 gap-4">
        {Object.entries(LABELS).map(([key, label]) => (
          <div key={key} className={`bg-slate-800 p-4 rounded-xl border ${COLORS[key]}/30`}>
            <h2 className="text-sm font-bold text-slate-300 mb-2">{label}</h2>
            <div className="bg-slate-900 rounded-lg p-3 font-mono text-xs text-slate-400 max-h-40 overflow-y-auto">
              {(logs[key] || []).length === 0 && <span className="text-slate-600">-- sem dados --</span>}
              {(logs[key] || []).map((line, i) => (
                <div key={i} className="py-0.5 border-b border-slate-800 last:border-0">{line}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
