import React, { useState, useEffect } from 'react';

export default function Operations() {
  const [data, setData] = useState({ open: [], closed: [], balance: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/operations')
      .then(res => res.json())
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  if (loading) {
    return <div className="p-6 text-white">Carregando histórico de operações...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-white mb-6">Operações</h1>
      
      {/* Filtros e Saldo */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
        <div className="flex gap-4">
          <select className="bg-slate-800 text-white p-2 rounded-lg border border-slate-700 focus:border-accentGreen outline-none">
            <option>Todas as Moedas</option>
          </select>
          <input type="date" className="bg-slate-800 text-white p-2 rounded-lg border border-slate-700 focus:border-accentGreen outline-none" />
        </div>
        <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
          <span className="text-slate-400 text-sm">Saldo Livre (Estimado):</span>
          <span className="text-white font-bold ml-2">${data.balance} USDT</span>
        </div>
      </div>

      {/* Ordens Abertas */}
      <div className="mb-8">
        <h2 className="text-xl font-bold text-white mb-4">Ordens Abertas</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {data.open.map((order) => (
            <div key={order.id} className="bg-slate-800 p-5 rounded-xl border border-blue-500/30 hover:border-blue-500 transition-colors">
              <div className="flex justify-between items-center mb-3">
                <span className="text-white font-bold text-lg">{order.symbol}</span>
                <span className="bg-blue-500/20 text-blue-400 text-xs px-2 py-1 rounded-full uppercase">Comprado</span>
              </div>
              <div className="text-sm text-slate-400 space-y-1">
                <div className="flex justify-between"><span>Quantidade:</span><span className="text-white">{order.quantity}</span></div>
                <div className="flex justify-between"><span>Preço Médio:</span><span className="text-white">${order.entry_price}</span></div>
                <div className="flex justify-between"><span>Total:</span><span className="text-white">${(order.entry_price * order.quantity).toFixed(2)}</span></div>
                <div className="flex justify-between"><span>Aberto em:</span><span className="text-white">{order.created_at}</span></div>
              </div>
            </div>
          ))}
          {data.open.length === 0 && (
            <p className="text-slate-500 col-span-full">Nenhuma ordem aberta.</p>
          )}
        </div>
      </div>

      {/* Ordens Fechadas */}
      <div>
        <h2 className="text-xl font-bold text-white mb-4">Histórico de Ordens</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {data.closed.map((order) => {
            const isWin = order.pnl_pct > 0;
            const invested = order.entry_price * order.quantity;
            const pnl_money = (order.pnl_pct / 100) * invested;
            
            // Tratamento visual para Stop Loss com Lucro (Trailing Stop)
            let badgeText = order.exit_reason || 'Encerrado';
            if (order.exit_reason === 'STOP_LOSS' && isWin) {
              badgeText = 'Trailing Stop';
            }

            return (
              <div key={order.id} className={`bg-slate-800 p-5 rounded-xl border ${isWin ? 'border-accentGreen/30 hover:border-accentGreen' : 'border-accentRed/30 hover:border-accentRed'} transition-colors`}>
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
                      {isWin ? '+' : ''}{pnl_money.toFixed(4)} USDT ({isWin ? '+' : ''}{order.pnl_pct.toFixed(2)}%)
                    </span>
                  </div>
                  <div className="flex justify-between"><span>Investido:</span><span className="text-white">${invested.toFixed(2)}</span></div>
                  <div className="flex justify-between"><span>Preço Entrada:</span><span className="text-white">${order.entry_price}</span></div>
                  <div className="flex justify-between"><span>Preço Saída:</span><span className="text-white">${order.exit_price}</span></div>
                  <div className="flex justify-between"><span>Fechado em:</span><span className="text-white">{order.updated_at}</span></div>
                </div>
              </div>
            );
          })}
          {data.closed.length === 0 && (
            <p className="text-slate-500 col-span-full">Nenhuma ordem fechada encontrada.</p>
          )}
        </div>
      </div>
    </div>
  );
}
