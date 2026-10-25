import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Clock,
  Warehouse,
  Flame,
  CheckCircle2,
  RefreshCw,
  Send,
  ArrowRight
} from 'lucide-react';

export default function RiskCentre({ onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRiskData();
  }, []);

  const fetchRiskData = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/fpo/risks');
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

  const criticalBatches = data?.critical_batches || [];
  const congestedWarehouses = data?.congested_warehouses || [];
  const cropSummary = data?.crop_risk_summary || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header Banner */}
      <div className="agri-card" style={{
        padding: '1.25rem',
        background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(245, 158, 11, 0.08) 100%)',
        border: '1px solid rgba(239, 68, 68, 0.3)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <ShieldAlert size={22} color="#f87171" />
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                Agricultural Risk Centre & Spoilage Prevention
              </h2>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Real-time surveillance of perishability windows, harvest expiration, and warehouse capacity bottlenecks.
            </p>
          </div>

          <button onClick={fetchRiskData} className="agri-btn ghost">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Alerts</span>
          </button>
        </div>
      </div>

      {/* Critical Batches at Expiration Window */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Priority Produce Expiration Window (≤ 3 Days Remaining)
            </h3>
            <p style={{ margin: '0.2rem 0 0', color: 'var(--text-faint)', fontSize: '0.75rem' }}>
              Harvest batches requiring expedited dispatch or processing liquidation to prevent total value loss.
            </p>
          </div>
          <span className="agri-badge rose">{criticalBatches.length} Urgent Batches</span>
        </div>

        <div className="agri-table-wrapper" style={{ maxHeight: '420px' }}>
          <table className="agri-table">
            <thead>
              <tr>
                <th>Batch Code</th>
                <th>Crop & Perishability</th>
                <th>Location</th>
                <th>Window Closes</th>
                <th>Days Left</th>
                <th>Net Available (kg)</th>
                <th>Severity</th>
                <th>Operational Directive</th>
              </tr>
            </thead>
            <tbody>
              {criticalBatches.slice(0, 15).map((b) => (
                <tr key={b.batch_id}>
                  <td style={{ fontWeight: 600, color: '#38bdf8', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                    {b.batch_code}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600, color: '#fff' }}>{b.crop_name}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)' }}>{b.variety} • {b.perishability_category}</div>
                  </td>
                  <td style={{ color: 'var(--text-muted)' }}>
                    {b.farm_district}, {b.farm_state}
                  </td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {b.estimated_quality_window_end}
                  </td>
                  <td>
                    <span style={{
                      fontWeight: 700,
                      color: b.days_until_quality_window_end <= 0 ? '#ef4444' : '#f97316'
                    }}>
                      {b.days_until_quality_window_end <= 0 ? 'CRITICAL TODAY' : `${b.days_until_quality_window_end} days`}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {parseFloat(b.net_available_kg || 0).toLocaleString()} kg
                  </td>
                  <td>
                    <span className={`agri-badge ${b.spoilage_risk_level === 'critical_today' ? 'rose' : 'amber'}`}>
                      {b.spoilage_risk_level}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => onNavigate && onNavigate('ai-workspace')}
                      className="agri-btn ghost"
                      style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem' }}
                    >
                      <span>Route to Buyer</span>
                      <ArrowRight size={12} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Grid: Crop At-Risk Summary + Congested Warehouses */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.25rem' }}>
        {/* Crop Spoilage Summary */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
            Produce Volume at Risk by Crop
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            {cropSummary.slice(0, 8).map((c, i) => (
              <div key={i} style={{
                padding: '0.75rem',
                borderRadius: '8px',
                background: 'rgba(15, 25, 45, 0.6)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontWeight: 600, color: '#fff' }}>{c.crop_name}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                    {c.critical_count} critical today • {c.high_risk_count} high risk
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 700, color: '#f87171' }}>
                    {Math.round(parseFloat(c.at_risk_quantity_kg || 0) / 1000).toLocaleString()} MT
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)' }}>Total at Risk</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* High Utilization Warehouses */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
            Near-Ceiling Storage Nodes (≥ 90% Utilization)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            {congestedWarehouses.slice(0, 8).map((w) => (
              <div key={w.warehouse_id} style={{
                padding: '0.75rem',
                borderRadius: '8px',
                background: 'rgba(15, 25, 45, 0.6)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontWeight: 600, color: '#fff' }}>{w.warehouse_name}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                    {w.district} • {w.storage_type}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className="agri-badge amber">
                    {parseFloat(w.utilization_pct || 0).toFixed(1)}% Full
                  </span>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '2px' }}>
                    {Math.round(parseFloat(w.remaining_capacity_kg || 0) / 1000).toLocaleString()} MT remaining
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
