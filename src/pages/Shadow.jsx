import React, { useState, useEffect } from 'react';

export default function Shadow() {
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/shadow')
      .then(res => res.json())
      .then(data => {
        setStrategies(data.strategies);
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  if (loading) {
    return <div className="p-6 text-white">Carregando dados do Shadow...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-white mb-6">Shadow Tests</h1>
      <p className="text-slate-400 mb-6">Simulações de estratégias em tempo real rodando em paralelo.</p>

      {/* Melhores Estratégias */}
      <div className="bg-slate-800 p-6 rounded-xl border border-slate-700">
        <h2 className="text-xl font-bold text-white mb-4">Ranking de Estratégias (Últimos Dados)</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-slate-300">
            <thead className="text-slate-500 border-b border-slate-700">
              <tr>
                <th className="pb-3">Posição</th>
                <th className="pb-3">Configuração (SL / TP)</th>
                <th className="pb-3">PnL Acumulado</th>
                <th className="pb-3">Amostra (N)</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((strat, index) => {
                const isWin = strat.pnl > 0;
                let trophy = "";
                if (index === 0) trophy = "🥇 ";
                if (index === 1) trophy = "🥈 ";
                if (index === 2) trophy = "🥉 ";
                
                return (
                  <tr key={index} className="border-b border-slate-700 last:border-b-0 text-white font-medium">
                    <td className="py-4">{trophy}{index + 1}º</td>
                    <td className="py-4">{strat.config}</td>
                    <td className={`py-4 ${isWin ? 'text-accentGreen' : 'text-accentRed'}`}>
                      {isWin ? '+' : ''}{strat.pnl}%
                    </td>
                    <td className="py-4 text-slate-500">{strat.count} trades</td>
                  </tr>
                );
              })}
              {strategies.length === 0 && (
                <tr>
                  <td colSpan="4" className="py-4 text-center text-slate-500">Nenhum dado de simulação disponível.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
