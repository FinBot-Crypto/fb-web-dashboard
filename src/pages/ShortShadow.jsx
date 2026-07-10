import React, { useState, useEffect } from 'react';

const TIER_COLORS = {
  'Strong Alt': { bg: 'rgba(99,102,241,0.15)', border: '#6366f1', badge: '#6366f1' },
  'Major': { bg: 'rgba(234,179,8,0.12)', border: '#eab308', badge: '#eab308' },
  'High Volatility': { bg: 'rgba(239,68,68,0.12)', border: '#ef4444', badge: '#ef4444' },
  'Desconhecido': { bg: 'rgba(100,116,139,0.15)', border: '#64748b', badge: '#64748b' },
};

function pnlColor(val) {
  if (val === null || val === undefined) return '#64748b';
  return val > 0 ? '#10b981' : val < 0 ? '#ef4444' : '#64748b';
}

function pnlSign(val) {
  if (val === null || val === undefined) return '\u2013';
  return (val > 0 ? '+' : '') + val.toFixed(3) + '%';
}

function HeatmapCell({ hour, avg_pnl, count }) {
  const hasData = count > 0;
  let bg = 'rgba(51,65,85,0.5)';
  let textColor = '#475569';
  if (hasData && avg_pnl !== null) {
    const intensity = Math.min(Math.abs(avg_pnl) / 1.0, 1);
    if (avg_pnl > 0) {
      bg = `rgba(16,185,129,${0.15 + intensity * 0.55})`;
      textColor = '#6ee7b7';
    } else {
      bg = `rgba(239,68,68,${0.15 + intensity * 0.55})`;
      textColor = '#fca5a5';
    }
  }
  return (
    <div
      title={hasData ? `${hour}h UTC | Media: ${pnlSign(avg_pnl)} | ${count} sims` : `${hour}h UTC | Sem dados`}
      style={{
        background: bg, border: '1px solid rgba(255,255,255,0.06)', borderRadius: '6px',
        padding: '6px 4px', textAlign: 'center', minWidth: '36px', cursor: 'default',
        transition: 'transform 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.12)'}
      onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
    >
      <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '2px' }}>{hour}h</div>
      {hasData && avg_pnl !== null
        ? <div style={{ fontSize: '9px', fontWeight: 700, color: textColor }}>{avg_pnl > 0 ? '+' : ''}{avg_pnl.toFixed(2)}</div>
        : <div style={{ fontSize: '9px', color: '#334155' }}>{"\u2013"}</div>
      }
    </div>
  );
}

function RSIBar({ range, avg_pnl, win_rate, count }) {
  const maxAbsPnl = 0.5;
  const pct = Math.min(Math.abs(avg_pnl) / maxAbsPnl * 100, 100);
  const color = avg_pnl >= 0 ? '#10b981' : '#ef4444';
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
        <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '14px' }}>RSI {range}</span>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8', fontSize: '12px' }}>{count} sims</span>
          <span style={{ color: '#94a3b8', fontSize: '12px' }}>WR: {win_rate}%</span>
          <span style={{ color, fontWeight: 700, fontSize: '14px' }}>{pnlSign(avg_pnl)}</span>
        </div>
      </div>
      <div style={{ background: 'rgba(51,65,85,0.6)', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
        <div style={{
          width: count > 0 ? `${pct}%` : '0%', height: '100%',
          background: color, borderRadius: '4px', transition: 'width 0.6s ease',
        }} />
      </div>
    </div>
  );
}

function SLTPRow({ rank, config, avg_pnl, win_rate, count }) {
  const isPos = avg_pnl >= 0;
  const medals = ['\uD83E\uDD47', '\uD83E\uDD48', '\uD83E\uDD49'];
  const medal = rank < 3 ? medals[rank] : `${rank + 1}º`;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px',
      borderRadius: '10px', marginBottom: '8px',
      background: isPos ? 'rgba(16,185,129,0.07)' : 'rgba(239,68,68,0.07)',
      border: `1px solid ${isPos ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
    }}>
      <span style={{ fontSize: '18px', minWidth: '32px', textAlign: 'center' }}>{medal}</span>
      <span style={{ flex: 1, color: '#e2e8f0', fontWeight: 600, fontSize: '14px' }}>{config}</span>
      <span style={{ color: '#94a3b8', fontSize: '12px', minWidth: '70px', textAlign: 'right' }}>{count} trades</span>
      <span style={{ color: '#94a3b8', fontSize: '12px', minWidth: '60px', textAlign: 'right' }}>WR {win_rate}%</span>
      <span style={{
        color: isPos ? '#10b981' : '#ef4444', fontWeight: 700, fontSize: '15px',
        minWidth: '80px', textAlign: 'right',
      }}>{pnlSign(avg_pnl)}</span>
    </div>
  );
}

export default function ShortShadow() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/shadow-short?min_model_score=0.70')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(d => { setData(d); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!data) return;
    const interval = setInterval(() => {
      fetch('/api/shadow-short?min_model_score=0.70')
        .then(res => res.json())
        .then(d => setData(d))
        .catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [data]);

  if (loading) return (
    <div style={{ padding: '40px', textAlign: 'center' }}>
      <div style={{ color: '#ef4444', fontSize: '32px', marginBottom: '12px' }}>{"\u2620\uFE0F"}</div>
      <div style={{ color: '#94a3b8', fontSize: '16px' }}>Carregando laboratorio SHORT...</div>
    </div>
  );

  if (error) return (
    <div style={{ padding: '40px', textAlign: 'center' }}>
      <div style={{ color: '#ef4444' }}>Erro: {error}</div>
    </div>
  );

  const noData = !data || data.total_simulations === 0;
  const rankingSltp = data?.ranking_sltp || [];
  const rankingRsi = data?.ranking_rsi || [];
  const rankingHour = data?.ranking_hour || [];
  const rankingTier = data?.ranking_tier || [];
  const rankingSymbol = data?.ranking_symbol || [];
  const bestCombo = data?.best_combo;

  const heatmapRows = [
    { label: 'Madrugada', hours: rankingHour.slice(0, 6) },
    { label: 'Manha', hours: rankingHour.slice(6, 12) },
    { label: 'Tarde', hours: rankingHour.slice(12, 18) },
    { label: 'Noite', hours: rankingHour.slice(18, 24) },
  ];

  const sectionStyle = {
    background: 'rgba(15,23,42,0.6)',
    border: '1px solid rgba(71,85,105,0.4)',
    borderRadius: '16px', padding: '24px', marginBottom: '24px',
    backdropFilter: 'blur(8px)',
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <span style={{ fontSize: '28px' }}>{"\u2620\uFE0F"}</span>
          <h1 style={{ fontSize: '26px', fontWeight: 800, color: '#f1f5f9', margin: 0 }}>
            Shadow SHORT
          </h1>
          {!noData && (
            <span style={{
              background: 'rgba(239,68,68,0.2)', border: '1px solid rgba(239,68,68,0.4)',
              color: '#fca5a5', fontSize: '12px', fontWeight: 600,
              padding: '3px 10px', borderRadius: '20px',
            }}>
              {data.total_simulations.toLocaleString()} simulacoes
            </span>
          )}
        </div>
        <p style={{ color: '#64748b', fontSize: '14px', margin: 0 }}>
          Simulacao de operacoes SHORT - entradas quando RSI &ge; 65 (sobrecomprado).
          Analise por SL/TP, faixa de RSI, horario, tier e moeda.
        </p>
      </div>

      {noData ? (
        <div style={{ ...sectionStyle, textAlign: 'center', padding: '48px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>{"\uD83D\uDD2C"}</div>
          <div style={{ color: '#94a3b8', fontSize: '16px' }}>
            Nenhum dado de simulacao SHORT disponivel.
            <br />
            <span style={{ color: '#64748b', fontSize: '13px' }}>
              O scanner analisa OHLCV de 15m dos ultimos 30 dias buscando RSI &ge; 65.
            </span>
          </div>
        </div>
      ) : (
        <>
          {bestCombo && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(239,68,68,0.2) 0%, rgba(234,88,12,0.15) 100%)',
              border: '1px solid rgba(239,68,68,0.4)', borderRadius: '16px',
              padding: '20px 24px', marginBottom: '24px',
              display: 'flex', alignItems: 'center', gap: '20px',
            }}>
              <div style={{ fontSize: '36px' }}>{"\uD83C\uDFC6"}</div>
              <div style={{ flex: 1 }}>
                <div style={{ color: '#fca5a5', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>
                  Melhor Combinacao SHORT Detectada
                </div>
                <div style={{ color: '#f1f5f9', fontSize: '18px', fontWeight: 700, marginBottom: '4px' }}>
                  {bestCombo.label}
                </div>
                <div style={{ color: '#94a3b8', fontSize: '13px' }}>
                  Baseado em {bestCombo.count} simulacoes com {bestCombo.win_rate}% de acerto
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ color: '#10b981', fontSize: '28px', fontWeight: 800 }}>
                  {pnlSign(bestCombo.avg_pnl)}
                </div>
                <div style={{ color: '#6ee7b7', fontSize: '12px' }}>PnL medio / simulacao</div>
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
            <div style={sectionStyle}>
              <h2 style={{ color: '#e2e8f0', fontSize: '17px', fontWeight: 700, marginTop: 0, marginBottom: '20px' }}>
                Performance por Tier
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {rankingTier.map(t => {
                  const colors = TIER_COLORS[t.tier] || TIER_COLORS['Desconhecido'];
                  return (
                    <div key={t.tier} style={{
                      display: 'flex', alignItems: 'center', gap: '12px',
                      padding: '14px 16px', borderRadius: '10px',
                      background: colors.bg, border: `1px solid ${colors.border}`,
                    }}>
                      <span style={{
                        display: 'inline-block', background: colors.badge, color: '#fff',
                        fontSize: '10px', fontWeight: 700, padding: '2px 10px',
                        borderRadius: '20px', textTransform: 'uppercase',
                      }}>{t.tier}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ color: '#64748b', fontSize: '12px' }}>{t.count} sims &bull; WR {t.win_rate}%</div>
                      </div>
                      <div style={{ color: pnlColor(t.avg_pnl), fontWeight: 700, fontSize: '16px' }}>
                        {pnlSign(t.avg_pnl)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={sectionStyle}>
              <h2 style={{ color: '#e2e8f0', fontSize: '17px', fontWeight: 700, marginTop: 0, marginBottom: '20px' }}>
                RSI de Entrada SHORT
              </h2>
              {rankingRsi.map(r => (
                <RSIBar key={r.range} range={r.range} avg_pnl={r.avg_pnl} win_rate={r.win_rate} count={r.count} />
              ))}
              <p style={{ color: '#475569', fontSize: '11px', marginTop: '12px', marginBottom: 0 }}>
                * Quanto maior o RSI de entrada, mais sobrecomprado = maior probabilidade de queda.
              </p>
            </div>
          </div>

          {(data?.ranking_trend && data.ranking_trend.length > 0) && (
          <div style={sectionStyle}>
            <h2 style={{ color: '#e2e8f0', fontSize: '17px', fontWeight: 700, marginTop: 0, marginBottom: '20px' }}>
              📈 Tendencia do BTC (Short)
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              {data.ranking_trend.map(t => (
                <div key={t.trend} style={{
                  background: t.trend === 'bull' ? 'rgba(16,185,129,0.08)' : t.trend === 'bear' ? 'rgba(239,68,68,0.08)' : 'rgba(100,116,139,0.08)',
                  border: `1px solid ${t.trend === 'bull' ? 'rgba(16,185,129,0.3)' : t.trend === 'bear' ? 'rgba(239,68,68,0.3)' : 'rgba(100,116,139,0.3)'}`,
                  borderRadius: '12px', padding: '20px', textAlign: 'center',
                }}>
                  <div style={{ fontSize: '24px', marginBottom: '8px' }}>
                    {t.trend === 'bull' ? '🐂' : t.trend === 'bear' ? '🐻' : '➖'}
                  </div>
                  <div style={{ color: '#e2e8f0', fontWeight: 700, fontSize: '16px', textTransform: 'uppercase', marginBottom: '8px' }}>
                    {t.trend === 'bull' ? 'Bull' : t.trend === 'bear' ? 'Bear' : 'Neutral'}
                  </div>
                  <div style={{ color: pnlColor(t.avg_pnl), fontSize: '24px', fontWeight: 800 }}>
                    {pnlSign(t.avg_pnl)}
                  </div>
                  <div style={{ color: '#64748b', fontSize: '12px', marginTop: '4px' }}>{t.count} sims | WR {t.win_rate}%</div>
                </div>
              ))}
            </div>
          </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
            <div style={sectionStyle}>
              <h2 style={{ color: '#e2e8f0', fontSize: '17px', fontWeight: 700, marginTop: 0, marginBottom: '16px' }}>
                Mapa de Calor - Hora de Entrada SHORT (UTC)
              </h2>
              <p style={{ color: '#475569', fontSize: '12px', marginBottom: '16px', marginTop: 0 }}>
                Verde = lucrativo &middot; Vermelho = prejuizo &middot; Cinza = sem dados
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {heatmapRows.map(row => (
                  <div key={row.label} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ color: '#64748b', fontSize: '12px', minWidth: '90px' }}>{row.label}</span>
                    <div style={{ display: 'flex', gap: '4px', flex: 1 }}>
                      {row.hours.map(h => (
                        <HeatmapCell key={h.hour} hour={h.hour} avg_pnl={h.avg_pnl} count={h.count} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div style={sectionStyle}>
              <h2 style={{ color: '#e2e8f0', fontSize: '17px', fontWeight: 700, marginTop: 0, marginBottom: '20px' }}>
                Melhores Moedas para SHORT
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '400px', overflowY: 'auto' }}>
                {rankingSymbol.slice(0, 15).map((s, i) => (
                  <div key={s.symbol} style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '10px 12px', borderRadius: '8px',
                    background: s.avg_pnl >= 0 ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)',
                  }}>
                    <span style={{ color: '#475569', fontSize: '12px', minWidth: '20px' }}>{i + 1}</span>
                    <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '14px', flex: 1 }}>{s.symbol}</span>
                    <span style={{ color: '#64748b', fontSize: '11px' }}>{s.count} sims</span>
                    <span style={{ color: '#64748b', fontSize: '11px' }}>WR {s.win_rate}%</span>
                    <span style={{ color: pnlColor(s.avg_pnl), fontWeight: 700, fontSize: '14px' }}>
                      {pnlSign(s.avg_pnl)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div style={sectionStyle}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h2 style={{ color: '#e2e8f0', fontSize: '17px', fontWeight: 700, margin: 0 }}>
                Ranking de SL/TP para SHORT
              </h2>
              <span style={{ color: '#64748b', fontSize: '12px' }}>
                SL = stop acima do preco &middot; TP = alvo abaixo do preco
              </span>
            </div>
            {rankingSltp.map((strat, i) => (
              <SLTPRow
                key={strat.config}
                rank={i}
                config={strat.config}
                avg_pnl={strat.avg_pnl}
                win_rate={strat.win_rate}
                count={strat.count}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
