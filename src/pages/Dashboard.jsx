import React, { useState, useEffect } from 'react';

export default function Dashboard() {
  const [data, setData] = useState({
    total_pnl: 0,
    win_rate: 0,
    total_closed: 0,
    wins: 0,
    losses: 0,
    active_positions: [],
    patrimony: 97.38
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/dashboard')
      .then(res => res.json())
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  if (loading) {
    return <div className="p-6 text-white">Carregando dados do Dashboard...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-white mb-6">Dashboard</h1>
      
      {/* KPIs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {/* Card 1 */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 hover:border-accentGreen transition-colors cursor-pointer">
          <p className="text-slate-400 text-sm font-medium">Patrimônio Total</p>
          <p className="text-2xl font-bold text-white mt-2">${data.patrimony}</p>
          <span className="text-accentRed text-xs font-medium">-2.62% vs inicial</span>
        </div>
        
        {/* Card 2 */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 hover:border-accentGreen transition-colors cursor-pointer">
          <p className="text-slate-400 text-sm font-medium">Lucro Líquido (DB)</p>
          <p className={`text-2xl font-bold mt-2 ${data.total_pnl >= 0 ? 'text-accentGreen' : 'text-accentRed'}`}>
            {data.total_pnl >= 0 ? '+' : ''}{data.total_pnl}%
          </p>
          <span className="text-accentGreen text-xs font-medium">Sinais positivos</span>
        </div>
        
        {/* Card 3 */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 hover:border-accentGreen transition-colors cursor-pointer">
          <p className="text-slate-400 text-sm font-medium">Win Rate Geral</p>
          <p className="text-2xl font-bold text-white mt-2">{data.win_rate}%</p>
          <span className="text-slate-400 text-xs font-medium">{data.wins} vitórias / {data.losses} derrotas</span>
        </div>
        
        {/* Card 4 */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 hover:border-accentGreen transition-colors cursor-pointer">
          <p className="text-slate-400 text-sm font-medium">Total de Trades</p>
          <p className="text-2xl font-bold text-white mt-2">{data.total_closed}</p>
          <span className="text-slate-400 text-xs font-medium">Encerrados</span>
        </div>
      </div>

      {/* Charts or Big Section */}
      <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 mb-8">
        <h2 className="text-xl font-bold text-white mb-4">Curva de Patrimônio</h2>
        <div className="h-64 flex items-center justify-center border-2 border-dashed border-slate-700 rounded-lg">
          <p className="text-slate-500">[ Gráfico de Linha será renderizado aqui ]</p>
        </div>
      </div>
      
      {/* Active Positions */}
      <div className="bg-slate-800 p-6 rounded-xl border border-slate-700">
        <h2 className="text-xl font-bold text-white mb-4">Posições Abertas Agora</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-slate-300">
            <thead className="text-slate-500 border-b border-slate-700">
              <tr>
                <th className="pb-3">Moeda</th>
                <th className="pb-3">Preço Entrada</th>
                <th className="pb-3">Quantidade</th>
                <th className="pb-3">Investido</th>
                <th className="pb-3">Aberto em</th>
              </tr>
            </thead>
            <tbody>
              {data.active_positions.map((pos, index) => (
                <tr key={index} className="border-b border-slate-700 last:border-b-0">
                  <td className="py-4 font-medium text-white">{pos.symbol}</td>
                  <td className="py-4">${pos.entry_price}</td>
                  <td className="py-4">{pos.quantity}</td>
                  <td className="py-4">${(pos.entry_price * pos.quantity).toFixed(2)}</td>
                  <td className="py-4">{pos.created_at}</td>
                </tr>
              ))}
              {data.active_positions.length === 0 && (
                <tr>
                  <td colSpan="5" className="py-4 text-center text-slate-500">Nenhuma posição aberta.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
