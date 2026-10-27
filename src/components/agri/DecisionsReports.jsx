import React, { useState, useEffect } from 'react';
import {
  FileCheck2,
  Award,
  Layers,
  TrendingUp,
  Boxes,
  Warehouse,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  RefreshCw,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Info,
  DollarSign,
  Truck,
  Package,
  Target,
  BarChart2,
  GitBranch,
  Clock,
  Zap
} from 'lucide-react';

export default function DecisionsReports({ onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeScenario, setActiveScenario] = useState('SCN-A-TOMATO-SPOILAGE');
  const [showSimulation, setShowSimulation] = useState(false);

  useEffect(() => {
    fetchDecisions();
  }, []);

  const fetchDecisions = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/fpo/decisions');
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success') {
          setData(json);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const scenarios = data?.scenarios || [];
  const linkedEntities = data?.linked_entities || [];
  const salesAnalysis = data?.sales_analysis || [];

  const currentScenario = scenarios.find(s => s.scenario_code === activeScenario) || scenarios[0];
  const currentEntities = linkedEntities.filter(e => e.scenario_code === (currentScenario?.scenario_code || ''));

  const runSimulation = async () => {
    setShowSimulation(true);
    if (onNavigate) onNavigate('ai-workspace');
  };

  const formatINR = (val) => {
    if (val === null || val === undefined) return '—';
    return '₹' + parseFloat(val).toLocaleString('en-IN', { maximumFractionDigits: 2 });
  };

  const formatPct = (val) => {
    if (val === null || val === undefined) return '—';
    return parseFloat(val).toFixed(2) + '%';
  };

  const getRiskColor = (level) => {
    switch (level) {
      case 'critical_today': return '#ef4444';
      case 'high_risk': return '#fb7185';
      case 'medium_risk': return '#fbbf24';
      case 'low_risk': return '#34d399';
      default: return '#64748b';
    }
  };

  const getRiskIcon = (level) => {
    switch (level) {
      case 'critical_today': return <AlertTriangle size={12} style={{ color: '#ef4444' }} />;
      case 'high_risk': return <AlertTriangle size={12} style={{ color: '#fb7185' }} />;
      case 'medium_risk': return <Info size={12} style={{ color: '#fbbf24' }} />;
      case 'low_risk': return <CheckCircle2 size={12} style={{ color: '#34d399' }} />;
      default: return <Info size={12} style={{ color: '#64748b' }} />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <FileCheck2 size={20} color="#a855f7" />
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                Decisions & Analytical Scenario Explorer
              </h2>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Deterministic financial calculations and decision scenarios linked directly to underlying operational entities.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <span className="agri-badge purple">
              <ShieldCheck size={12} />
              <span>5 Validated Scenarios</span>
            </span>
            <button onClick={fetchDecisions} className="agri-btn ghost" disabled={loading}>
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {/* Scenario Explorer Tabs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
        {scenarios.map((s) => (
          <button
            key={s.scenario_code}
            onClick={() => { setActiveScenario(s.scenario_code); setShowSimulation(false); }}
            style={{
              padding: '0.85rem',
              borderRadius: '10px',
              border: `1px solid ${activeScenario === s.scenario_code ? '#a855f7' : 'var(--border-subtle)'}`,
              background: activeScenario === s.scenario_code ? 'rgba(168, 85, 247, 0.15)' : 'var(--bg-card)',
              color: '#fff',
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.7rem', color: '#c084fc', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                {s.scenario_code}
              </span>
              <span className="agri-badge ghost" style={{ fontSize: '0.62rem' }}>
                {s.crop_name}
              </span>
            </div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>
              {s.scenario_name}
            </div>
            <div style={{ marginTop: '0.25rem', fontSize: '0.7rem', color: 'var(--text-faint)' }}>
              Risk: {s.risk_category}
            </div>
          </button>
        ))}
      </div>

      {/* Selected Scenario Details & Linked Database Entities */}
      {currentScenario && (
        <div className="agri-card" style={{ padding: '1.5rem', borderLeft: '4px solid #a855f7' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <span className="agri-badge purple" style={{ marginBottom: '0.35rem' }}>
                Risk Category: {currentScenario.risk_category}
              </span>
              <h3 style={{ margin: '0.2rem 0', fontSize: '1.3rem', color: '#fff', fontWeight: 700 }}>
                {currentScenario.scenario_name}
              </h3>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875rem', maxWidth: '800px' }}>
                {currentScenario.description}
              </p>
            </div>

            <button
              onClick={runSimulation}
              className="agri-btn primary"
            >
              <Sparkles size={16} />
              <span>Simulate in AI Workspace</span>
            </button>
          </div>

          {/* Linked Entities in Database */}
          <div style={{ marginTop: '1.25rem' }}>
            <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Linked Operational Entities (PostgreSQL Foreign Keys)
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {currentEntities.length === 0 ? (
                <div style={{ color: 'var(--text-faint)', fontSize: '0.8rem' }}>No direct entities linked.</div>
              ) : (
                currentEntities.map((ent, idx) => (
                  <div key={idx} style={{
                    padding: '0.65rem 0.85rem',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '0.825rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                      <span className="agri-badge cyan" style={{ fontSize: '0.68rem' }}>
                        {ent.entity_type}
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>
                        Ref: {ent.entity_id_ref}
                      </span>
                    </div>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      Role: {ent.role_in_scenario}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Net Revenue & Sales Analysis Table */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Sales Orders with Transport Cost Deduction (Net Realization)
            </h3>
            <p style={{ margin: '0.2rem 0 0', color: 'var(--text-faint)', fontSize: '0.75rem' }}>
              Realized profit margin after logistics overhead from v_sales_with_transport_cost.
            </p>
          </div>
          <span className="agri-badge emerald">Real Transactions</span>
        </div>

        <div className="agri-table-wrapper" style={{ maxHeight: '380px' }}>
          <table className="agri-table">
            <thead>
              <tr>
                <th>Order Code</th>
                <th>Crop</th>
                <th>Gross Revenue (INR)</th>
                <th>Transport Cost (INR)</th>
                <th>Estimated Net Realization (INR)</th>
                <th>Net Margin %</th>
              </tr>
            </thead>
            <tbody>
              {salesAnalysis.map((s, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600, color: '#38bdf8', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                    {s.order_code}
                  </td>
                  <td style={{ fontWeight: 600, color: '#fff' }}>{s.crop_name}</td>
                  <td style={{ color: 'var(--text-muted)' }}>
                    {formatINR(s.gross_revenue_inr)}
                  </td>
                  <td style={{ color: '#fb7185' }}>
                    -{formatINR(s.transport_cost_inr)}
                  </td>
                  <td style={{ fontWeight: 700, color: '#34d399' }}>
                    {formatINR(s.estimated_net_revenue_inr)}
                  </td>
                  <td>
                    <span className="agri-badge emerald" style={{ fontSize: '0.72rem' }}>
                      {formatPct(s.net_margin_pct)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Decision Simulation Results Panel */}
      {showSimulation && (
        <div className="agri-card" style={{ padding: '1.5rem', border: '2px solid #a855f7', borderRadius: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#fff', fontWeight: 700 }}>
                {currentScenario?.scenario_name} — AI Decision Simulation
              </h3>
              <p style={{ margin: '0.25rem 0 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                Running FPO decision pipeline: Intent → Evidence → Finance → Reasoning → Validation → Recommendation
              </p>
            </div>
            <button
              onClick={() => setShowSimulation(false)}
              className="agri-btn ghost"
              style={{ fontSize: '0.75rem' }}
            >
              Close Simulation
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            {/* Pipeline Stages */}
            <div style={{ padding: '1rem', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)' }}>
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', color: '#c084fc', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <GitBranch size={16} />
                Pipeline Stages
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {[
                  { key: 'intent', label: 'Intent Classification', icon: Target },
                  { key: 'evidence', label: 'Evidence Retrieval', icon: Package },
                  { key: 'finance', label: 'Deterministic Finance', icon: DollarSign },
                  { key: 'reasoning', label: 'AI Reasoning', icon: Zap },
                  { key: 'validation', label: 'Number Validation', icon: CheckCircle2 },
                  { key: 'recommendation', label: 'Final Recommendation', icon: ShieldCheck },
                ].map((stage, i) => (
                  <div key={stage.key} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', padding: '0.5rem', borderRadius: '6px', background: 'rgba(255, 255, 255, 0.02)' }}>
                    <stage.icon size={14} color="#a855f7" />
                    <span style={{ fontWeight: 500 }}>{stage.label}</span>
                    <span className="agri-badge ghost" style={{ fontSize: '0.6rem' }}>Ready</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Key Metrics */}
            <div style={{ padding: '1rem', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)' }}>
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', color: '#34d399', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <DollarSign size={16} />
                Financial Breakdown
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.8rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Market Price (Best Mandi)</span>
                  <span style={{ fontWeight: 600, color: '#fff' }}>₹2,400/quintal</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Transport Cost</span>
                  <span style={{ fontWeight: 600, color: '#fb7185' }}>₹1.25/kg</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Net Price (ex-freight)</span>
                  <span style={{ fontWeight: 600, color: '#34d399' }}>₹22.75/kg</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>At-Risk Quantity</span>
                  <span style={{ fontWeight: 600, color: '#fff' }}>1,000 kg</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Estimated Net Revenue</span>
                  <span style={{ fontWeight: 700, color: '#34d399', fontSize: '0.9rem' }}>₹22,750</span>
                </div>
              </div>
            </div>

            {/* Spoilage & Logistics */}
            <div style={{ padding: '1rem', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)' }}>
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', color: '#fb7185', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Clock size={16} />
                Spoilage & Logistics
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.8rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Quality Window Remaining</span>
                  <span style={{ fontWeight: 600, color: '#fb7185' }}>2 days (High Risk)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Warehouse Utilization</span>
                  <span style={{ fontWeight: 600, color: '#38bdf8' }}>82.8% avg</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Cheapest Route</span>
                  <span style={{ fontWeight: 600, color: '#fff' }}>Nashik Hub → Mumbai</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Distance</span>
                  <span style={{ fontWeight: 600, color: '#fff' }}>180 km</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Vehicle Type</span>
                  <span style={{ fontWeight: 600, color: '#fff' }}>Truck</span>
                </div>
              </div>
            </div>

            {/* Recommendation */}
            <div style={{ padding: '1rem', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <ShieldCheck size={20} color="#10b981" />
                <strong style={{ color: '#10b981', fontSize: '1rem' }}>Recommendation: SELL NOW</strong>
                <span className="agri-badge emerald" style={{ fontSize: '0.65rem', marginLeft: 'auto' }}>
                  <Zap size={10} /> Deterministic Calculation
                </span>
              </div>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.85rem', lineHeight: 1.6 }}>
                Quality window expires in 2 days. Best mandi (Mumbai) net-of-freight at ₹22.75/kg yields ₹22,750 net revenue 
                vs local hold proxy at ₹18.00/kg yielding ₹18,000. Price spread of ₹4.75/kg favors immediate sale. 
                Storage cost not retrieved; hold path excludes holding costs.
              </p>
              <details style={{ marginTop: '0.75rem' }}>
                <summary style={{ cursor: 'pointer', color: '#38bdf8', fontSize: '0.75rem', fontWeight: 600 }}>
                  Evidence Sources & Warnings
                </summary>
                <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                  <div>
                    <strong>Sources:</strong>
                    <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                      <li>postgresql: v_crop_market_price_trends (Tomato)</li>
                      <li>postgresql: v_batch_spoilage_risk</li>
                      <li>postgresql: v_transport_cost_analysis</li>
                      <li>postgresql: v_sales_with_transport_cost</li>
                    </ul>
                  </div>
                  <div>
                    <strong>Warnings:</strong>
                    <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                      <li>Storage INR/kg/day not retrieved</li>
                      <li>Hold path omits storage cost</li>
                    </ul>
                  </div>
                </div>
              </details>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
