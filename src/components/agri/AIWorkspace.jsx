import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Mic,
  MicOff,
  Sparkles,
  Brain,
  Database,
  Terminal,
  ChevronDown,
  ChevronUp,
  Volume2,
  VolumeX,
  RefreshCw,
  Table,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import Nexus3DCore from '../Nexus3DCore';

export default function AIWorkspace({
  messages = [],
  onSendMessage,
  busy = false,
  voiceEnabled = true,
  onToggleVoice,
  voiceHook
}) {
  const [input, setInput] = useState('');
  const [showEvidence, setShowEvidence] = useState(true);
  const [aiState, setAiState] = useState('idle'); // idle | listening | thinking | speaking
  const chatEndRef = useRef(null);

  useEffect(() => {
    if (busy) {
      setAiState('thinking');
    } else if (voiceHook?.isListening) {
      setAiState('listening');
    } else {
      setAiState('idle');
    }
  }, [busy, voiceHook?.isListening]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || busy) return;
    onSendMessage(input);
    setInput('');
  };

  const samplePrompts = [
    'Show batches at spoilage risk',
    'Compare Tomato prices across mandis',
    'How many farmers and active batches?',
    'Which warehouses are over 85% capacity?',
    'Simulate Scenario SCN-A: Tomato Spoilage',
    'zetaris: test connection',
    'zetaris: query SELECT * FROM v_batch_spoilage_risk LIMIT 5'
  ];

  return (
    <div style={{ display: 'flex', height: '100%', gap: '1.25rem' }}>
      {/* Main Conversation Stream */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 }}>
        {/* Workspace Hero with 3D Core Mini-Status */}
        <div className="agri-card" style={{ padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ width: '48px', height: '48px', position: 'relative', overflow: 'hidden', borderRadius: '12px', background: 'rgba(7, 12, 22, 0.8)' }}>
              <Nexus3DCore phase="ONLINE" isDocked={true} state={aiState} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h2 style={{ margin: 0, fontSize: '1.15rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                  NEXUS AI Agricultural Assistant
                </h2>
                <span className={`agri-badge ${busy ? 'amber' : 'cyan'}`}>
                  {busy ? 'Processing Query...' : 'Online & Grounded'}
                </span>
              </div>
              <p style={{ margin: '0.15rem 0 0', color: 'var(--text-faint)', fontSize: '0.78rem' }}>
                Connected to PostgreSQL (nexus_fpo) & Zetaris AI Gateway. Zero fabricated numbers.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="agri-btn ghost"
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
            >
              <Table size={14} />
              <span>{showEvidence ? 'Hide Evidence Panel' : 'Show Evidence'}</span>
            </button>
          </div>
        </div>

        {/* Messages Stream Container */}
        <div className="agri-card" style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          padding: '1.25rem',
          overflowY: 'auto',
          maxHeight: 'calc(100vh - 280px)',
          gap: '1rem'
        }}>
          {messages.length === 0 ? (
            <div style={{
              margin: 'auto',
              textAlign: 'center',
              maxWidth: '520px',
              padding: '2rem 1rem'
            }}>
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #0284c7, #10b981)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                marginBottom: '1rem',
                boxShadow: '0 0 25px rgba(14, 165, 233, 0.3)'
              }}>
                <Sparkles size={28} />
              </div>
              <h3 style={{ margin: '0 0 0.5rem', color: '#fff', fontSize: '1.2rem', fontWeight: 700 }}>
                How can NEXUS assist your FPO network today?
              </h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                Ask natural questions about produce shelf-life, mandi price arbitrage, warehouse allocations, or run direct SQL through Zetaris.
              </p>

              {/* Sample Prompts Grid */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'center' }}>
                {samplePrompts.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => { setInput(p); }}
                    style={{
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '0.45rem 0.75rem',
                      color: 'var(--text-muted)',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#38bdf8'; e.currentTarget.style.color = '#38bdf8'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%'
                }}
              >
                <div style={{
                  fontSize: '0.7rem',
                  color: 'var(--text-faint)',
                  marginBottom: '0.25rem',
                  textAlign: m.sender === 'user' ? 'right' : 'left'
                }}>
                  {m.sender === 'user' ? 'FPO Operator' : 'NEXUS Agri-AI'} • {m.time || 'Live'}
                </div>

                <div style={{
                  padding: '0.85rem 1.1rem',
                  borderRadius: '12px',
                  background: m.sender === 'user'
                    ? 'linear-gradient(135deg, #0284c7, #0369a1)'
                    : 'rgba(15, 25, 45, 0.85)',
                  border: `1px solid ${m.sender === 'user' ? 'transparent' : 'var(--border-subtle)'}`,
                  color: '#fff',
                  fontSize: '0.9rem',
                  lineHeight: 1.5,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
                }}>
                  {m.text}

                  {/* Render Structured Table / Evidence Data if present */}
                  {m.fileData && m.fileData.rows && Array.isArray(m.fileData.rows) && (
                    <div style={{ marginTop: '0.75rem', overflowX: 'auto' }}>
                      <div className="agri-table-wrapper" style={{ maxHeight: '200px' }}>
                        <table className="agri-table">
                          <thead>
                            <tr>
                              {(m.fileData.columns || Object.keys(m.fileData.rows[0] || {})).map(col => (
                                <th key={col}>{col}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {m.fileData.rows.slice(0, 10).map((r, ri) => (
                              <tr key={ri}>
                                {(m.fileData.columns || Object.keys(r)).map(col => (
                                  <td key={col} style={{ fontSize: '0.75rem' }}>{String(r[col] ?? '')}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {busy && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#38bdf8', fontSize: '0.85rem' }}>
              <RefreshCw size={16} className="animate-spin" />
              <span>NEXUS is querying analytical database views & formulating recommendations...</span>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Chat Input Bar */}
        <form onSubmit={handleSubmit} className="agri-card" style={{ padding: '0.65rem 0.85rem', display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question or enter command (e.g., zetaris: query SELECT ...)"
            className="agri-input"
            style={{ flex: 1, border: 'none', background: 'transparent', height: '40px', fontSize: '0.9rem' }}
          />

          {voiceHook && (
            <button
              type="button"
              onClick={voiceHook.isListening ? voiceHook.stopListening : voiceHook.startListening}
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '8px',
                background: voiceHook.isListening ? '#ef4444' : 'rgba(255, 255, 255, 0.05)',
                border: 'none',
                color: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.15s ease'
              }}
              title={voiceHook.isListening ? 'Stop Listening' : 'Voice Input'}
            >
              {voiceHook.isListening ? <MicOff size={18} /> : <Mic size={18} />}
            </button>
          )}

          <button
            type="submit"
            disabled={!input.trim() || busy}
            className="agri-btn primary"
            style={{ width: '42px', height: '38px', padding: 0 }}
          >
            <Send size={18} />
          </button>
        </form>
      </div>

      {/* Side Evidence & Reasoner Panel */}
      {showEvidence && (
        <div className="agri-card" style={{ width: '320px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.2rem' }}>
              <Brain size={18} color="#38bdf8" />
              <h3 style={{ margin: 0, fontSize: '1rem', color: '#fff', fontWeight: 600 }}>
                Reasoner & Evidence Log
              </h3>
            </div>
            <p style={{ margin: 0, color: 'var(--text-faint)', fontSize: '0.75rem' }}>
              Real execution trace from backend agent tools.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ fontSize: '0.7rem', color: '#38bdf8', fontWeight: 600, textTransform: 'uppercase' }}>
                Connected Gateway
              </div>
              <div style={{ color: '#fff', fontSize: '0.8rem', fontWeight: 500, marginTop: '2px' }}>
                Zetaris AI Data Platform
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                Direct REST (HTTP Basic + Bearer)
              </div>
            </div>

            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ fontSize: '0.7rem', color: '#34d399', fontWeight: 600, textTransform: 'uppercase' }}>
                Database Target
              </div>
              <div style={{ color: '#fff', fontSize: '0.8rem', fontWeight: 500, marginTop: '2px' }}>
                PostgreSQL (nexus_fpo)
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                526K synthetic records • 8 views
              </div>
            </div>

            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ fontSize: '0.7rem', color: '#c084fc', fontWeight: 600, textTransform: 'uppercase' }}>
                Guardrails Active
              </div>
              <div style={{ color: '#fff', fontSize: '0.8rem', fontWeight: 500, marginTop: '2px' }}>
                SELECT-Only Enforced
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                Max 100 rows per query • No DDL/Writes
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
