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
  Sparkles
} from 'lucide-react';

export default function DecisionsReports({ onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeScenario, setActiveScenario] = useState('SCN-A-TOMATO-SPOILAGE');

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
            <button onClick={fetchDecisions} className="agri-btn ghost">
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
            onClick={() => setActiveScenario(s.scenario_code)}
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
              onClick={() => onNavigate && onNavigate('ai-workspace')}
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
                    ₹{parseFloat(s.gross_revenue_inr || 0).toLocaleString()}
                  </td>
                  <td style={{ color: '#fb7185' }}>
                    -₹{parseFloat(s.transport_cost_inr || 0).toLocaleString()}
                  </td>
                  <td style={{ fontWeight: 700, color: '#34d399' }}>
                    ₹{parseFloat(s.estimated_net_revenue_inr || 0).toLocaleString()}
                  </td>
                  <td>
                    <span className="agri-badge emerald" style={{ fontSize: '0.72rem' }}>
                      {parseFloat(s.net_margin_pct || 0).toFixed(2)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
