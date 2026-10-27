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

  AlertCircle,

  Server,

  Cpu,

  Shield,

  AlertTriangle,

  Wifi,

  WifiOff,

  Link,

  Unlink,

  Zap,

  Loader2,

  Info,

  X

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

  const [showProviders, setShowProviders] = useState(false);

  const [aiState, setAiState] = useState('idle'); // idle | listening | thinking | speaking

  const [providerStatus, setProviderStatus] = useState({ meterless: null, nvidia: null });

  const [checkingProviders, setCheckingProviders] = useState(false);

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

    'Should we hold vs sell tomatoes?',

    'Which market gives best net profit for onions?',

    'Show batches at spoilage risk',

    'Compare Tomato prices across mandis',

    'How many farmers and active batches?',

    'Which warehouses are over 85% capacity?',

    'Simulate Scenario SCN-A: Tomato Spoilage',

    'zetaris: test connection',

    'zetaris: query SELECT * FROM v_batch_spoilage_risk LIMIT 5'

  ];



  const checkProviders = async () => {

    setCheckingProviders(true);

    try {

      const configRes = await fetch('/api/config');

      const config = await configRes.json();

      

      const [meterlessRes, nvidiaRes] = await Promise.all([

        fetch('/api/meterless/status', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ config })

        }),

        fetch('/api/nvidia/status', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ config })

        })

      ]);

      

      const meterless = await meterlessRes.json();

      const nvidia = await nvidiaRes.json();

      

      setProviderStatus({ meterless, nvidia });

    } catch (e) {

      console.error(e);

    } finally {

      setCheckingProviders(false);

    }

  };



  const getProviderBadge = (provider) => {

    if (!provider) return <span className="agri-badge ghost">Not checked</span>;

    switch (provider.status) {

      case 'online':

        return <span className="agri-badge emerald"><CheckCircle2 size={10} /> Online</span>;

      case 'unauthorized':

        return <span className="agri-badge amber"><AlertTriangle size={10} /> Invalid Token</span>;

      case 'unconfigured':

        return <span className="agri-badge ghost"><X size={10} /> Not Configured</span>;

      case 'offline':

        return <span className="agri-badge rose"><WifiOff size={10} /> Offline</span>;

      default:

        return <span className="agri-badge ghost">{provider.status}</span>;

    }

  };



  const renderMessageContent = (m) => {
    // Parse structured response sections from text
    const parseStructuredResponse = (text) => {
      const sections = {};
      const sectionHeaders = [
        'EXECUTIVE SUMMARY',
        'CURRENT SITUATION',
        'MARKET ANALYSIS',
        'TRANSPORT & LOGISTICS',
        'WEATHER & SPOILAGE RISK',
        'FINANCIAL COMPARISON',
        'FEASIBILITY & UNCERTAINTY',
        'RECOMMENDATION',
        'PRACTICAL NEXT STEPS',
        'MISSING EVIDENCE & ASSUMPTIONS'
      ];
      
      let currentSection = 'EXECUTIVE SUMMARY';
      let currentContent = [];
      
      text.split('\n').forEach(line => {
        const trimmed = line.trim();
        const matchedHeader = sectionHeaders.find(h => trimmed === `## ${h}` || trimmed === `### ${h}`);
        if (matchedHeader) {
          if (currentContent.length > 0) {
            sections[currentSection] = currentContent.join('\n').trim();
          }
          currentSection = matchedHeader;
          currentContent = [];
        } else {
          currentContent.push(line);
        }
      });
      if (currentContent.length > 0) {
        sections[currentSection] = currentContent.join('\n').trim();
      }
      
      return sections;
    };
    
    const renderSection = (title, content) => {
      if (!content || !content.trim()) return null;
      return (
        <div style={{ marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.5rem', 
            marginBottom: '0.5rem',
            fontSize: '0.8rem',
            fontWeight: 700,
            color: '#38bdf8',
            textTransform: 'uppercase',
            letterSpacing: '0.05em'
          }}>
            {title}
          </div>
          <div style={{ 
            whiteSpace: 'pre-wrap', 
            lineHeight: 1.6, 
            fontSize: '0.85rem',
            color: '#e0e7ff'
          }}>
            {content}
          </div>
        </div>
      );
    };
    
    // Handle simple text messages (user messages or simple responses)
    if (m.text && !m.fileData) {
      return <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{m.text}</div>;
    }
    
    // Handle structured AI responses with sections
    if (m.fileData && m.text && m.text.includes('## ')) {
      const sections = parseStructuredResponse(m.text);
      return (
        <>
          {Object.entries(sections).map(([title, content]) => 
            renderSection(title, content)
          )}
          
          {/* Evidence Sources */}
          {m.fileData.evidence && m.fileData.evidence.length > 0 && (
            <details style={{ marginTop: '1rem' }}>
              <summary style={{ cursor: 'pointer', color: '#38bdf8', fontSize: '0.75rem', fontWeight: 600 }}>
                Evidence Sources ({m.fileData.evidence.length})
              </summary>
              <ul style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem' }}>
                {m.fileData.evidence.map((src, i) => (
                  <li key={i} style={{ fontFamily: 'var(--font-mono)' }}>
                    {src.source}: {src.identifier}
                  </li>
                ))}
              </ul>
            </details>
          )}
          
          {/* Warnings */}
          {m.fileData.warnings && m.fileData.warnings.length > 0 && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', borderRadius: '6px', background: 'rgba(251, 113, 133, 0.1)', border: '1px solid rgba(251, 113, 133, 0.3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#fb7185', fontSize: '0.7rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                <AlertTriangle size={12} />
                Warnings & Missing Evidence
              </div>
              <ul style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0, paddingLeft: '1.25rem', lineHeight: 1.8 }}>
                {m.fileData.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      );
    }
    
    // Handle table data (inventory listings, etc.)
    if (m.fileData && m.fileData.rows && Array.isArray(m.fileData.rows)) {
      return (
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
      );
    }
    
    // Legacy FPO Decision format
    if (m.fileData && m.fileData.type === 'fpo_decision') {
      return (
        <div style={{ marginTop: '1rem', padding: '1rem', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Shield size={18} color="#10b981" />
            <strong style={{ color: '#10b981', fontSize: '0.9rem' }}>FPO Decision Recommendation</strong>
            {m.fileData.live_model && (
              <span className="agri-badge cyan" style={{ fontSize: '0.65rem' }}>
                <Zap size={10} /> Live AI
              </span>
            )}
            {!m.fileData.live_model && (
              <span className="agri-badge ghost" style={{ fontSize: '0.65rem' }}>
                Deterministic
              </span>
            )}
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.8rem' }}>
            <div>
              <span style={{ color: 'var(--text-faint)' }}>Action:</span>
              <div style={{ fontWeight: 600, color: '#fff', textTransform: 'capitalize' }}>
                {m.fileData.recommendation?.action?.replace('_', ' ') || '—'}
              </div>
            </div>
            <div>
              <span style={{ color: 'var(--text-faint)' }}>Crop:</span>
              <div style={{ fontWeight: 600, color: '#fff' }}>{m.fileData.recommendation?.crop || '—'}</div>
            </div>
            {m.fileData.recommendation?.sell_now && (
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: 'var(--text-faint)' }}>Sell Now (Best Market):</span>
                <div style={{ fontWeight: 600, color: '#34d399' }}>
                  {m.fileData.recommendation.sell_now.best_market} — Net ₹{m.fileData.recommendation.sell_now.estimated_net_inr?.toLocaleString()} ({m.fileData.recommendation.sell_now.net_per_kg_inr} INR/kg)
                </div>
              </div>
            )}
            {m.fileData.recommendation?.hold_proxy && (
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: 'var(--text-faint)' }}>Hold / Local:</span>
                <div style={{ fontWeight: 600, color: '#38bdf8' }}>
                  {m.fileData.recommendation.hold_proxy.local_market} — Net ₹{m.fileData.recommendation.hold_proxy.estimated_net_inr?.toLocaleString()} ({m.fileData.recommendation.hold_proxy.gross_per_kg_inr} INR/kg)
                </div>
              </div>
            )}
            {m.fileData.recommendation?.spoilage?.days_until_quality_window_end !== null && m.fileData.recommendation?.spoilage?.days_until_quality_window_end !== undefined && (
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: 'var(--text-faint)' }}>Spoilage Risk:</span>
                <div style={{ fontWeight: 600, color: m.fileData.recommendation.spoilage.days_until_quality_window_end <= 3 ? '#fb7185' : '#34d399' }}>
                  {m.fileData.recommendation.spoilage.days_until_quality_window_end} days left ({m.fileData.recommendation.spoilage.spoilage_risk_level})
                </div>
              </div>
            )}
          </div>

          {/* Evidence Sources */}
          {m.fileData.evidence && m.fileData.evidence.length > 0 && (
            <details style={{ marginTop: '0.75rem' }}>
              <summary style={{ cursor: 'pointer', color: '#38bdf8', fontSize: '0.75rem', fontWeight: 600 }}>
                Evidence Sources ({m.fileData.evidence.length})
              </summary>
              <ul style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem' }}>
                {m.fileData.evidence.map((src, i) => (
                  <li key={i} style={{ fontFamily: 'var(--font-mono)' }}>
                    {src.source}: {src.identifier}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* Warnings */}
          {m.fileData.warnings && m.fileData.warnings.length > 0 && (
            <div style={{ marginTop: '0.75rem', padding: '0.5rem', borderRadius: '6px', background: 'rgba(251, 113, 133, 0.1)', border: '1px solid rgba(251, 113, 133, 0.3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#fb7185', fontSize: '0.7rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                <AlertTriangle size={12} />
                Warnings
              </div>
              <ul style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0, paddingLeft: '1.25rem' }}>
                {m.fileData.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );
    }
    
    // Fallback: simple text
    return m.text ? <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{m.text}</div> : null;
  };
  return (

    <div style={{ display: 'flex', height: '100%', gap: '1.25rem' }}>

      {/* Main Conversation Stream */}

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 }}>

        {/* Workspace Hero with 3D Core Mini-Status */}

        <div className="agri-card" style={{ padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>

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



          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>

            <button

              onClick={() => setShowEvidence(!showEvidence)}

              className="agri-btn ghost"

              style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}

            >

              <Table size={14} />

              <span>{showEvidence ? 'Hide Evidence Panel' : 'Show Evidence'}</span>

            </button>

            <button

              onClick={() => { setShowProviders(!showProviders); if (!showProviders) checkProviders(); }}

              className="agri-btn ghost"

              style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}

            >

              <Server size={14} />

              <span>{showProviders ? 'Hide Providers' : 'AI Providers'}</span>

            </button>

          </div>

        </div>



        {/* Provider Status Bar */}

        {showProviders && (

          <div className="agri-card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>

                <h3 style={{ margin: 0, fontSize: '0.9rem', color: '#fff', fontWeight: 600 }}>AI Provider Status</h3>

                <button onClick={checkProviders} disabled={checkingProviders} className="agri-btn ghost" style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}>

                  <RefreshCw size={12} className={checkingProviders ? 'animate-spin' : ''} />

                  <span>Refresh</span>

                </button>

              </div>

              <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.7rem', color: 'var(--text-faint)' }}>

                <span>Meterless routes to local fleet</span>

                <span>NVIDIA NIM calls Nemotron models</span>

              </div>

            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>

              <div style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)' }}>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>

                  <Server size={16} color="#10b981" />

                  <span style={{ fontWeight: 600, color: '#fff' }}>Meterless Runtime (Nightshift)</span>

                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', fontSize: '0.75rem' }}>

                  {getProviderBadge(providerStatus.meterless)}

                  {providerStatus.meterless && providerStatus.meterless.message && (

                    <span style={{ color: 'var(--text-muted)' }}>{providerStatus.meterless.message}</span>

                  )}

                </div>

                {providerStatus.meterless && providerStatus.meterless.models && (

                  <details style={{ marginTop: '0.5rem', color: 'var(--text-muted)', fontSize: '0.7rem' }}>

                    <summary>Routing modes ({providerStatus.meterless.models.filter(m => m.startsWith('meterless/')).length})</summary>

                    <ul style={{ marginTop: '0.5rem' }}>

                      {providerStatus.meterless.models.filter(m => m.startsWith('meterless/')).slice(0, 8).map((m, i) => (

                        <li key={i} style={{ fontFamily: 'var(--font-mono)' }}>{m}</li>

                      ))}

                    </ul>

                  </details>

                )}

              </div>

              <div style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)' }}>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>

                  <Cpu size={16} color="#76b900" />

                  <span style={{ fontWeight: 600, color: '#fff' }}>NVIDIA NIM Nemotron (FPO)</span>

                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', fontSize: '0.75rem' }}>

                  {getProviderBadge(providerStatus.nvidia)}

                  {providerStatus.nvidia && providerStatus.nvidia.message && (

                    <span style={{ color: 'var(--text-muted)' }}>{providerStatus.nvidia.message}</span>

                  )}

                </div>

                {providerStatus.nvidia && providerStatus.nvidia.models && (

                  <details style={{ marginTop: '0.5rem', color: 'var(--text-muted)', fontSize: '0.7rem' }}>

                    <summary>FPO Models ({providerStatus.nvidia.models.length})</summary>

                    <ul style={{ marginTop: '0.5rem' }}>

                      {providerStatus.nvidia.models.map((m, i) => (

                        <li key={i} style={{ fontFamily: 'var(--font-mono)' }}>

                          {m.label} — {m.role}

                        </li>

                      ))}

                    </ul>

                  </details>

                )}

              </div>

            </div>

          </div>

        )}



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

                  {renderMessageContent(m)}

                </div>

              </div>

            ))

          )}



          {busy && (

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#38bdf8', fontSize: '0.85rem' }}>

              <Loader2 size={16} className="animate-spin" />

              <span>NEXUS is querying analytical database views & formulating recommendations...</span>

            </div>

          )}

          <div ref={chatEndRef} />

        </div>



        {/* Chat Input Bar */}

        <form onSubmit={(e) => { e.preventDefault(); handleSubmit(e); return false; }} className="agri-card" style={{ padding: '0.65rem 0.85rem', display: 'flex', alignItems: 'center', gap: '0.65rem' }}>

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

        <div className="agri-card" style={{ width: '340px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto' }}>

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



            {messages.length > 0 && messages[messages.length - 1].fileData && (

              <div style={{

                padding: '0.75rem',

                borderRadius: '8px',

                background: 'rgba(255, 255, 255, 0.03)',

                border: '1px solid var(--border-subtle)'

              }}>

                <div style={{ fontSize: '0.7rem', color: '#a855f7', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.5rem' }}>

                  Last Response Metadata

                </div>

                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>

                  <div><strong>Intent:</strong> {messages[messages.length - 1].intent || '—'}</div>

                  <div><strong>Provider:</strong> {messages[messages.length - 1].provider || '—'}</div>

                  <div><strong>Live Model:</strong> {messages[messages.length - 1].live_model ? 'Yes' : 'No'}</div>

                  <div><strong>Sources:</strong> {messages[messages.length - 1].evidence?.sources?.length || 0}</div>

                  <div><strong>Warnings:</strong> {messages[messages.length - 1].evidence?.warnings?.length || 0}</div>

                </div>

              </div>

            )}

          </div>

        </div>

      )}

    </div>

  );

}

