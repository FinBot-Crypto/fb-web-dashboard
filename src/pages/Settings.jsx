import React, { useState, useEffect } from 'react';

const TIER_LABELS = {
  'Major': 'Major (BTC, ETH)',
  'Strong Alt': 'Strong Alt (SOL, BNB, etc.)',
  'High Volatility': 'High Volatility (PEPE, TRX, etc.)'
};

const TIER_COLORS = {
  'Major': { border: 'rgba(234,179,8,0.3)', glow: 'rgba(234,179,8,0.1)' },
  'Strong Alt': { border: 'rgba(99,102,241,0.3)', glow: 'rgba(99,102,241,0.1)' },
  'High Volatility': { border: 'rgba(239,68,68,0.3)', glow: 'rgba(239,68,68,0.1)' }
};

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [lemeHistory, setLemeHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);

  const fetchLemeHistory = () => {
    fetch('/api/leme/history')
      .then(res => res.json())
      .then(data => setLemeHistory(data))
      .catch(err => console.error("Erro ao buscar histórico do Leme:", err));
  };

  useEffect(() => {
    fetch('/api/settings')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setSettings(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });

    fetchLemeHistory();
  }, []);

  const handleChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleSave = () => {
    // Validação de limites
    for (let k in settings) {
      if (k.endsWith('_min_score')) {
        const val = parseFloat(settings[k]);
        if (isNaN(val) || val <= 0 || val >= 1.0) {
          setFeedback({ type: 'error', text: `O score mínimo para ${k.replace('long_', '').replace('short_', '').replace('_min_score', '')} deve ser um decimal entre 0.0 e 1.0 (ex: 0.70)` });
          return;
        }
      }
      if (k.endsWith('_sl') || k.endsWith('_tp')) {
        const val = parseFloat(settings[k]);
        if (isNaN(val) || val <= 0 || val > 100) {
          setFeedback({ type: 'error', text: `Stop Loss / Take Profit para ${k} deve ser um valor numérico entre 0.1% e 100%` });
          return;
        }
      }
      if (k.endsWith('_max_rsi') || k.endsWith('_min_rsi')) {
        const val = parseFloat(settings[k]);
        if (isNaN(val) || val <= 0 || val > 100) {
          setFeedback({ type: 'error', text: `O limite de RSI para ${k} deve ser um valor numérico entre 1 e 100` });
          return;
        }
      }
      if (k === 'leme_max_consecutive_sl') {
        const val = parseInt(settings[k]);
        if (isNaN(val) || val <= 0 || val > 20) {
          setFeedback({ type: 'error', text: 'O limite de Stop Losses seguidos do Leme deve ser entre 1 e 20.' });
          return;
        }
      }
      if (k === 'leme_min_win_rate' || k === 'leme_shadow_min_winrate') {
        const val = parseFloat(settings[k]);
        if (isNaN(val) || val < 0 || val > 100) {
          setFeedback({ type: 'error', text: 'As taxas de win-rate do Leme devem ser entre 0% e 100%.' });
          return;
        }
      }
      if (k === 'leme_cooldown_hours') {
        const val = parseInt(settings[k]);
        if (isNaN(val) || val <= 0 || val > 720) {
          setFeedback({ type: 'error', text: 'O prazo de cooldown do Leme deve ser entre 1 e 720 horas.' });
          return;
        }
      }
      if (k === 'leme_shadow_min_trades') {
        const val = parseInt(settings[k]);
        if (isNaN(val) || val <= 0 || val > 50) {
          setFeedback({ type: 'error', text: 'A quantidade mínima de trades shadow do Leme deve ser entre 1 e 50.' });
          return;
        }
      }
    }

    setSaving(true);
    setFeedback(null);
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    })
      .then(res => {
        if (!res.ok) throw new Error('Falha ao salvar');
        return res.json();
      })
      .then(() => {
        setFeedback({ type: 'success', text: 'Configurações salvas e aplicadas em tempo real com sucesso!' });
        setSaving(false);
        fetchLemeHistory();
        setTimeout(() => setFeedback(null), 5000);
      })
      .catch(err => {
        setFeedback({ type: 'error', text: `Erro ao salvar: ${err.message}` });
        setSaving(false);
      });
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ color: '#6366f1', fontSize: '32px', marginBottom: '12px' }}>⚙️</div>
        <div style={{ color: '#94a3b8', fontSize: '16px' }}>Carregando configurações do sistema...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ color: '#ef4444' }}>Erro ao carregar configurações: {error}</div>
      </div>
    );
  }

  const sectionStyle = {
    background: 'rgba(15,23,42,0.6)',
    border: '1px solid rgba(71,85,105,0.3)',
    borderRadius: '16px',
    padding: '24px',
    marginBottom: '24px',
    backdropFilter: 'blur(8px)',
  };

  const inputStyle = {
    background: '#0f172a',
    color: '#f1f5f9',
    border: '1px solid rgba(71,85,105,0.6)',
    borderRadius: '8px',
    padding: '8px 12px',
    width: '100%',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box'
  };

  const labelStyle = {
    color: '#94a3b8',
    fontSize: '12px',
    fontWeight: 500,
    marginBottom: '6px',
    display: 'block'
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      
      {/* Header */}
      <div style={{ marginBottom: '28px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <span style={{ fontSize: '28px' }}>⚙️</span>
            <h1 style={{ fontSize: '26px', fontWeight: 800, color: '#f1f5f9', margin: 0 }}>
              Painel de Configurações
            </h1>
          </div>
          <p style={{ color: '#64748b', fontSize: '14px', margin: 0 }}>
            Gerencie em tempo real os limites operacionais de LONG e SHORT para os 6 grupos de Tiers.
          </p>
        </div>
        
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            color: '#fff',
            border: 'none',
            borderRadius: '10px',
            padding: '12px 24px',
            fontWeight: 700,
            fontSize: '14px',
            cursor: 'pointer',
            boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)',
            transition: 'all 0.2s',
            opacity: saving ? 0.7 : 1
          }}
        >
          {saving ? 'Gravando...' : 'Salvar Alterações'}
        </button>
      </div>

      {feedback && (
        <div style={{
          background: feedback.type === 'success' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
          border: `1px solid ${feedback.type === 'success' ? '#10b981' : '#ef4444'}`,
          borderRadius: '12px',
          padding: '14px 20px',
          color: feedback.type === 'success' ? '#6ee7b7' : '#fca5a5',
          fontSize: '14px',
          fontWeight: 600,
          marginBottom: '24px'
        }}>
          {feedback.type === 'success' ? '✅' : '❌'} {feedback.text}
        </div>
      )}

      {/* O Leme Config Card */}
      <div style={{
        ...sectionStyle,
        border: '1px solid rgba(99, 102, 241, 0.3)',
        boxShadow: '0 4px 20px rgba(99, 102, 241, 0.1)',
        marginBottom: '32px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '14px', marginBottom: '20px' }}>
          <div>
            <h2 style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              ☸️ O Leme (Piloto Autônomo)
            </h2>
            <p style={{ color: '#64748b', fontSize: '12px', margin: '4px 0 0 0' }}>
              Gerenciamento dinâmico de risco. Ajusta e pausa automaticamente a operação dos Tiers com base em perdas reais e shadow.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{ color: '#f1f5f9', fontSize: '14px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <input 
                type="checkbox" 
                checked={settings.leme_active ?? true}
                onChange={(e) => handleChange('leme_active', e.target.checked)}
                style={{ cursor: 'pointer', transform: 'scale(1.2)' }}
              />
              Piloto Ativo
            </label>
          </div>
        </div>

        {/* Leme Parameters Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div>
            <label style={labelStyle}>Stop Losses Consecutivos (Max)</label>
            <input 
              type="number" 
              step="1"
              min="1"
              max="20"
              value={settings.leme_max_consecutive_sl ?? 3}
              onChange={(e) => handleChange('leme_max_consecutive_sl', parseInt(e.target.value))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Win-Rate Mínimo Real (%)</label>
            <input 
              type="number" 
              step="1"
              min="10"
              max="100"
              value={settings.leme_min_win_rate ?? 50.0}
              onChange={(e) => handleChange('leme_min_win_rate', parseFloat(e.target.value))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Prazo de Cooldown (Horas)</label>
            <input 
              type="number" 
              step="1"
              min="1"
              max="720"
              value={settings.leme_cooldown_hours ?? 24}
              onChange={(e) => handleChange('leme_cooldown_hours', parseInt(e.target.value))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Mínimo de Trades Shadow</label>
            <input 
              type="number" 
              step="1"
              min="1"
              max="50"
              value={settings.leme_shadow_min_trades ?? 5}
              onChange={(e) => handleChange('leme_shadow_min_trades', parseInt(e.target.value))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Win-Rate Recuperação Shadow (%)</label>
            <input 
              type="number" 
              step="1"
              min="10"
              max="100"
              value={settings.leme_shadow_min_winrate ?? 60.0}
              onChange={(e) => handleChange('leme_shadow_min_winrate', parseFloat(e.target.value))}
              style={inputStyle}
            />
          </div>
        </div>

        {/* Leme History Decisions Log Table */}
        <div style={{ marginTop: '28px' }}>
          <h3 style={{ color: '#e2e8f0', fontSize: '14px', fontWeight: 700, marginBottom: '12px' }}>
            📜 Histórico de Decisões do Piloto
          </h3>
          {lemeHistory.length === 0 ? (
            <div style={{ padding: '16px', background: '#0f172a', border: '1px solid rgba(71,85,105,0.2)', borderRadius: '8px', color: '#64748b', fontSize: '13px', textAlign: 'center' }}>
              Nenhuma decisão automática registrada ainda pelo piloto do Leme.
            </div>
          ) : (
            <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid rgba(71,85,105,0.3)', background: '#0f172a' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: 'rgba(30,41,59,0.8)', borderBottom: '1px solid rgba(71,85,105,0.4)' }}>
                    <th style={{ padding: '10px 14px', color: '#94a3b8', fontWeight: 600 }}>Data/Hora</th>
                    <th style={{ padding: '10px 14px', color: '#94a3b8', fontWeight: 600 }}>Grupo</th>
                    <th style={{ padding: '10px 14px', color: '#94a3b8', fontWeight: 600 }}>Ação</th>
                    <th style={{ padding: '10px 14px', color: '#94a3b8', fontWeight: 600 }}>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {lemeHistory.map((h, i) => {
                    let actionBadgeStyle = {
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      display: 'inline-block'
                    };
                    if (h.action === 'DISABLE') {
                      actionBadgeStyle = { ...actionBadgeStyle, background: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', border: '1px solid rgba(239, 68, 68, 0.3)' };
                    } else if (h.action === 'ENABLE') {
                      actionBadgeStyle = { ...actionBadgeStyle, background: 'rgba(34, 197, 94, 0.15)', color: '#86efac', border: '1px solid rgba(34, 197, 94, 0.3)' };
                    } else {
                      actionBadgeStyle = { ...actionBadgeStyle, background: 'rgba(100, 116, 139, 0.15)', color: '#cbd5e1', border: '1px solid rgba(100, 116, 139, 0.3)' };
                    }

                    return (
                      <tr key={h.id || i} style={{ borderBottom: i === lemeHistory.length - 1 ? 'none' : '1px solid rgba(71,85,105,0.2)' }}>
                        <td style={{ padding: '10px 14px', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                          {h.created_at ? new Date(h.created_at).toLocaleString('pt-BR') : '-'}
                        </td>
                        <td style={{ padding: '10px 14px', color: '#f1f5f9', fontWeight: 600 }}>
                          {h.group_name}
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <span style={actionBadgeStyle}>{h.action}</span>
                        </td>
                        <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>
                          {h.reason}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Tiers Loop */}
      {['Major', 'Strong Alt', 'High Volatility'].map(tier => {
        const colors = TIER_COLORS[tier];
        return (
          <div key={tier} style={{
            ...sectionStyle,
            border: `1px solid ${colors.border}`,
            boxShadow: `0 4px 20px ${colors.glow}`
          }}>
            <h2 style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: 800, marginTop: 0, marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '10px' }}>
              💎 {TIER_LABELS[tier]}
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
              
              {/* LONG CONFIG */}
              <div style={{ background: 'rgba(99,102,241,0.03)', border: '1px solid rgba(99,102,241,0.1)', borderRadius: '12px', padding: '18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ color: '#818cf8', fontSize: '15px', fontWeight: 700, margin: 0 }}>🟢 Operações LONG</h3>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input 
                      type="checkbox"
                      checked={settings[`long_${tier}_allowed`] ?? true}
                      onChange={(e) => handleChange(`long_${tier}_allowed`, e.target.checked)}
                      style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                    />
                    <span style={{ color: '#f1f5f9', fontSize: '13px', fontWeight: 600 }}>Ativo</span>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={labelStyle}>Score Mínimo</label>
                    <input 
                      type="number" 
                      step="0.01"
                      min="0.5"
                      max="0.99"
                      value={settings[`long_${tier}_min_score`] ?? 0.70}
                      onChange={(e) => handleChange(`long_${tier}_min_score`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>RSI Máximo (LONG)</label>
                    <input 
                      type="number" 
                      step="1"
                      min="10"
                      max="60"
                      value={settings[`long_${tier}_max_rsi`] ?? 30}
                      onChange={(e) => handleChange(`long_${tier}_max_rsi`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Stop Loss (SL %)</label>
                    <input 
                      type="number" 
                      step="0.1"
                      min="0.5"
                      max="20"
                      value={settings[`long_${tier}_sl`] ?? 3.0}
                      onChange={(e) => handleChange(`long_${tier}_sl`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Take Profit (TP %)</label>
                    <input 
                      type="number" 
                      step="0.1"
                      min="0.5"
                      max="50"
                      value={settings[`long_${tier}_tp`] ?? 3.0}
                      onChange={(e) => handleChange(`long_${tier}_tp`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                </div>
              </div>

              {/* SHORT CONFIG */}
              <div style={{ background: 'rgba(239,68,68,0.03)', border: '1px solid rgba(239,68,68,0.1)', borderRadius: '12px', padding: '18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ color: '#f87171', fontSize: '15px', fontWeight: 700, margin: 0 }}>🔴 Operações SHORT</h3>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input 
                      type="checkbox"
                      checked={settings[`short_${tier}_allowed`] ?? true}
                      onChange={(e) => handleChange(`short_${tier}_allowed`, e.target.checked)}
                      style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                    />
                    <span style={{ color: '#f1f5f9', fontSize: '13px', fontWeight: 600 }}>Ativo</span>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={labelStyle}>Score Mínimo</label>
                    <input 
                      type="number" 
                      step="0.01"
                      min="0.5"
                      max="0.99"
                      value={settings[`short_${tier}_min_score`] ?? 0.70}
                      onChange={(e) => handleChange(`short_${tier}_min_score`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>RSI Mínimo (SHORT)</label>
                    <input 
                      type="number" 
                      step="1"
                      min="50"
                      max="90"
                      value={settings[`short_${tier}_min_rsi`] ?? 70}
                      onChange={(e) => handleChange(`short_${tier}_min_rsi`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Stop Loss (SL %)</label>
                    <input 
                      type="number" 
                      step="0.1"
                      min="0.5"
                      max="20"
                      value={settings[`short_${tier}_sl`] ?? 3.0}
                      onChange={(e) => handleChange(`short_${tier}_sl`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Take Profit (TP %)</label>
                    <input 
                      type="number" 
                      step="0.1"
                      min="0.5"
                      max="50"
                      value={settings[`short_${tier}_tp`] ?? 3.0}
                      onChange={(e) => handleChange(`short_${tier}_tp`, parseFloat(e.target.value))}
                      style={inputStyle}
                    />
                  </div>
                </div>
              </div>

            </div>
          </div>
        );
      })}

      {/* Floating Save Button on bottom mobile */}
      <div style={{ marginTop: '12px', textAlign: 'right' }}>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            color: '#fff',
            border: 'none',
            borderRadius: '10px',
            padding: '14px 32px',
            fontWeight: 700,
            fontSize: '15px',
            cursor: 'pointer',
            boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)',
            transition: 'all 0.2s',
            opacity: saving ? 0.7 : 1
          }}
        >
          {saving ? 'Gravando...' : 'Salvar Todas as Configurações'}
        </button>
      </div>

    </div>
  );
}
