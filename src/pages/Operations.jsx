import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Spinner, playNewTradeSound } from '../components/UI';

function SLTPBar({ current, sl, tp, entry }) {
  if (!sl || !tp || !current) return null;
  const range = tp - sl;
  if (range <= 0) return null;
  const pct = ((current - sl) / range) * 100;
  const clamped = Math.max(0, Math.min(100, pct));
  const barColor = current >= entry ? 'bg-accentGreen' : 'bg-accentRed';
  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-slate-500 mb-1">
        <span>SL ${sl?.toFixed(6)}</span>
        <span className="text-slate-400">Entry ${entry?.toFixed(6)}</span>
        <span>TP ${tp?.toFixed(6)}</span>
      </div>
      <div className="h-3 bg-slate-700 rounded-full relative overflow-hidden">
        <div className={`h-full ${barColor} rounded-full transition-all duration-500`} style={{ width: `${clamped}%` }} />
        <div className="absolute top-0 bottom-0 w-0.5 bg-white/50" style={{ left: `${((entry - sl) / range) * 100}%` }} />
      </div>
      <div className="text-center text-xs text-slate-400 mt-1">
        ${current?.toFixed(6)} ({clamped.toFixed(0)}% até TP)
      </div>
    </div>
  );
}

function TradeChart({ order, onClose }) {
  if (!order.sl_price || !order.tp_price) return null;
  const data = [
    { name: 'SL', price: order.sl_price },
    { name: 'Entry', price: order.entry_price },
    { name: 'Now', price: order.current_price || order.entry_price },
    { name: 'TP', price: order.tp_price },
  ];
  const min = order.sl_price * 0.998;
  const max = order.tp_price * 1.002;
  
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-900 rounded-xl p-6 max-w-2xl w-full border border-slate-700" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-white font-bold text-lg">{order.symbol}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">&times;</button>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="name" stroke="#94a3b8" />
            <YAxis domain={[min, max]} stroke="#94a3b8" tickFormatter={v => '$' + v.toFixed(4)} />
            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#fff' }} />
            <ReferenceLine y={order.entry_price} stroke="#fbbf24" strokeDasharray="5 5" label={{ value: 'Entry', fill: '#fbbf24', fontSize: 12 }} />
            <ReferenceLine y={order.sl_price} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'SL', fill: '#ef4444', fontSize: 12 }} />
            <ReferenceLine y={order.tp_price} stroke="#22c55e" strokeDasharray="5 5" label={{ value: 'TP', fill: '#22c55e', fontSize: 12 }} />
            <Line type="monotone" dataKey="price" stroke="#38bdf8" strokeWidth={2} dot={{ r: 4, fill: '#38bdf8' }} />
          </LineChart>
        </ResponsiveContainer>
        <div className="grid grid-cols-3 gap-4 mt-4 text-sm text-slate-400">
          <div><span className="text-red-400">SL:</span> ${order.sl_price?.toFixed(6)}</div>
          <div><span className="text-amber-400">Entry:</span> ${order.entry_price?.toFixed(6)}</div>
          <div><span className="text-green-400">TP:</span> ${order.tp_price?.toFixed(6)}</div>
        </div>
      </div>
    </div>
  );
}

export default function Operations() {
  const [data, setData] = useState({ open: [], closed: [] });
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const prevOpenCount = useRef(0);

  useEffect(() => {
    const fetchData = () => {
      fetch('/api/operations')
        .then(res => res.json())
        .then(data => {
          // Som quando nova ordem entra
          if (data.open.length > prevOpenCount.current && prevOpenCount.current > 0) {
            playNewTradeSound();
          }
          prevOpenCount.current = data.open.length;
          setData(data);
          setLoading(false);
        })
        .catch(err => console.error(err));
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="p-6"><Spinner /></div>;

  const totalInvested = data.open.reduce((sum, o) => sum + (o.entry_price * o.quantity), 0);
  const totalCurrent = data.open.reduce((sum, o) => sum + ((o.current_price || o.entry_price) * o.quantity), 0);
  const totalReturn = totalCurrent - totalInvested;

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-white mb-6">Operações</h1>

      {selectedOrder && <TradeChart order={selectedOrder} onClose={() => setSelectedOrder(null)} />}

      {/* Card de Resumo */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <div className="text-slate-400 text-sm">Em operação</div>
          <div className="text-white text-xl font-bold">${totalInvested.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-slate-400 text-sm">Valor atual</div>
          <div className="text-white text-xl font-bold">${totalCurrent.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-slate-400 text-sm">Retorno</div>
          <div className={`text-xl font-bold ${totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(4)} USDT
          </div>
        </div>
        <div>
          <div className="text-slate-400 text-sm">% Retorno</div>
          <div className={`text-xl font-bold ${totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalReturn >= 0 ? '+' : ''}{(totalInvested > 0 ? (totalReturn / totalInvested * 100) : 0).toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Ordens Abertas */}
      <div className="mb-8">
        <h2 className="text-xl font-bold text-white mb-4">Ordens Abertas ({data.open.length})</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {data.open.map((order) => {
            const current = order.current_price;
            const isProfit = current && current >= order.entry_price;
            const pnlDollar = current ? (current - order.entry_price) * order.quantity : 0;
            const pnlPct = current ? ((current / order.entry_price) - 1) * 100 : 0;
            const wlInfo = order.coin_total > 0 
              ? <span className={`text-xs ${order.coin_wins >= order.coin_losses ? 'text-green-400' : 'text-red-400'}`}>
                  ({order.coin_wins}W/{order.coin_losses}L)
                </span>
              : null;
            return (
              <div key={order.id}
                onClick={() => setSelectedOrder(order)}
                className={`bg-slate-800 p-5 rounded-xl border cursor-pointer transition-all hover:scale-[1.02] ${isProfit ? 'border-green-500/30 hover:border-green-500' : 'border-red-500/30 hover:border-red-500'}`}
              >
                <div className="flex justify-between items-center mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-bold text-lg">{order.symbol}</span>
                    {wlInfo}
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full uppercase ${isProfit ? 'bg-accentGreen/20 text-accentGreen' : 'bg-accentRed/20 text-accentRed'}`}>
                    {isProfit ? 'Lucro' : 'Perda'}
                  </span>
                </div>
                {/* Mini-card central com PnL em $ e % */}
                <div className={`text-center py-4 my-2 rounded-lg ${isProfit ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                  <div className={`text-3xl font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                    {isProfit ? '+' : ''}{pnlDollar.toFixed(4)} USDT
                  </div>
                  <div className={`text-sm mt-1 ${isProfit ? 'text-green-300' : 'text-red-300'}`}>
                    {isProfit ? '+' : ''}{pnlPct.toFixed(2)}% da entrada
                  </div>
                </div>
                <div className="text-xs text-slate-500 space-y-1">
                  <div className="flex justify-between"><span>Qtd:</span><span className="text-white">{order.quantity}</span></div>
                  <div className="flex justify-between"><span>Entrada:</span><span className="text-white">${order.entry_price}</span></div>
                  <div className="flex justify-between"><span>Atual:</span><span className={`font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>${current?.toFixed(6) || '...'}</span></div>
                </div>
                <SLTPBar current={current} sl={order.sl_price} tp={order.tp_price} entry={order.entry_price} />
              </div>
            );
          })}
          {data.open.length === 0 && (
            <p className="text-slate-500 col-span-full">Nenhuma ordem aberta.</p>
          )}
        </div>
      </div>

      {/* Ordens Fechadas */}
      <div>
        <h2 className="text-xl font-bold text-white mb-4">Histórico ({data.closed.length})</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {data.closed.map((order) => {
            const isWin = order.pnl_pct > 0;
            const invested = order.entry_price * order.quantity;
            const pnl_dollar = (order.pnl_pct / 100) * invested;
            let badgeText = order.exit_reason || 'Encerrado';
            if (order.exit_reason === 'STOP_LOSS' && isWin) badgeText = 'Trailing Stop';

            return (
              <div key={order.id} className={`bg-slate-800 p-5 rounded-xl border ${isWin ? 'border-accentGreen/30' : 'border-accentRed/30'}`}>
                <div className="flex justify-between items-center mb-3">
                  <span className="text-white font-bold text-lg">{order.symbol}</span>
                  <span className={`text-xs px-2 py-1 rounded-full uppercase ${isWin ? 'bg-accentGreen/20 text-accentGreen' : 'bg-accentRed/20 text-accentRed'}`}>
                    {badgeText}
                  </span>
                </div>
                <div className="text-sm text-slate-400 space-y-1">
                  <div className="flex justify-between">
                    <span>Resultado:</span>
                    <span className={`font-bold ${isWin ? 'text-accentGreen' : 'text-accentRed'}`}>
                      {isWin ? '+' : ''}{pnl_dollar.toFixed(4)} USDT ({isWin ? '+' : ''}{order.pnl_pct?.toFixed(2)}%)
                    </span>
                  </div>
                  <div className="flex justify-between"><span>Entrada:</span><span className="text-white">${order.entry_price}</span></div>
                  <div className="flex justify-between"><span>Saída:</span><span className="text-white">${order.exit_price}</span></div>
                  <div className="flex justify-between"><span>Fechado:</span><span className="text-white">{order.updated_at}</span></div>
                </div>
              </div>
            );
          })}
          {data.closed.length === 0 && (
            <p className="text-slate-500 col-span-full">Nenhuma ordem fechada.</p>
          )}
        </div>
      </div>
    </div>
  );
}
