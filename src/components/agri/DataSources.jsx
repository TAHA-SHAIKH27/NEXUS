import React, { useState, useEffect } from 'react';
import {
  Database,
  Server,
  Cpu,
  ShieldCheck,
  Play,
  Terminal,
  RefreshCw,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

export default function DataSources() {
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('SELECT crop_name, spoilage_risk_level, COUNT(*) as batch_count FROM v_batch_spoilage_risk GROUP BY crop_name, spoilage_risk_level LIMIT 10;');
  const [queryRunning, setQueryRunning] = useState(false);
  const [queryResult, setQueryResult] = useState(null);
  const [queryError, setQueryError] = useState(null);

  useEffect(() => {
    fetchDatasources();
  }, []);

  const fetchDatasources = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/fpo/datasources');
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success') {
          setStatusData(json);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleRunQuery = async () => {
    if (!query.trim()) return;
    try {
      setQueryRunning(true);
      setQueryError(null);
      setQueryResult(null);

      // Execute via /api/command with zetaris: query ...
      const res = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: `zetaris: query ${query}` })
      });

      if (res.ok) {
        const json = await res.json();
        if (json.file_data && Array.isArray(json.file_data.rows)) {
          setQueryResult(json.file_data);
        } else if (json.speak) {
          setQueryError(json.speak);
        }
      }
    } catch (err) {
      setQueryError(err.message);
    } finally {
      setQueryRunning(false);
    }
  };

  const pg = statusData?.postgresql || {};
  const zetaris = statusData?.zetaris || {};
  const tableCounts = pg.table_counts || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <Database size={20} color="#38bdf8" />
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                Data Infrastructure & Gateway Topology
              </h2>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Multi-tier data federation: React → FastAPI → Zetaris AI Gateway → PostgreSQL (nexus_fpo).
            </p>
          </div>

          <button onClick={fetchDatasources} className="agri-btn ghost">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>Health Ping</span>
          </button>
        </div>
      </div>

      {/* 3 Node Health Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.25rem' }}>
        {/* PostgreSQL Node */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <Server size={22} color="#10b981" />
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', color: '#fff', fontWeight: 600 }}>PostgreSQL DB</h3>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>nexus_fpo • 127.0.0.1:5433</div>
              </div>
            </div>
            <span className="agri-badge emerald">
              {pg.connected ? 'Connected' : 'Offline'}
            </span>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <div>Database: <span style={{ color: '#fff', fontWeight: 600 }}>nexus_fpo</span></div>
            <div>Docker Container: <span style={{ color: '#38bdf8' }}>nexus-fpo-db</span></div>
            <div>Read-Only Role: <span style={{ color: '#34d399' }}>zetaris_ro (Enforced)</span></div>
            <div>Total Tables: <span style={{ color: '#fff' }}>{Object.keys(tableCounts).length}</span></div>
          </div>
        </div>

        {/* Zetaris Gateway Node */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <Cpu size={22} color="#38bdf8" />
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', color: '#fff', fontWeight: 600 }}>Zetaris AI Gateway</h3>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>REST Ports 8888 / 8889</div>
              </div>
            </div>
            <span className={`agri-badge ${zetaris.connected ? 'cyan' : 'amber'}`}>
              {zetaris.connected ? 'Connected' : 'Degraded'}
            </span>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <div>Registered Source: <span style={{ color: '#38bdf8', fontWeight: 600 }}>NEXUS_FPO</span></div>
            <div>Auth Mechanism: <span style={{ color: '#fff' }}>HTTP Basic → Bearer Token</span></div>
            <div>SQL Validator: <span style={{ color: '#34d399' }}>SELECT-Only Protected</span></div>
            <div>Message: <span style={{ color: 'var(--text-faint)' }}>{zetaris.message}</span></div>
          </div>
        </div>

        {/* FastAPI Middleware */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <ShieldCheck size={22} color="#a855f7" />
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', color: '#fff', fontWeight: 600 }}>FastAPI Platform Engine</h3>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>127.0.0.1:8000 (Uvicorn)</div>
              </div>
            </div>
            <span className="agri-badge purple">Active</span>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <div>Analytics Routers: <span style={{ color: '#fff', fontWeight: 600 }}>/api/fpo/*</span></div>
            <div>Zetaris Adapter: <span style={{ color: '#fff' }}>Direct HTTP Client</span></div>
            <div>Query Safety: <span style={{ color: '#34d399' }}>Row Limit 100 Enforced</span></div>
            <div>Connection Pooling: <span style={{ color: '#fff' }}>Scoped Psycopg2</span></div>
          </div>
        </div>
      </div>

      {/* Database Catalog Table */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
          Public Database Tables & Live Row Counts
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem' }}>
          {Object.entries(tableCounts).map(([tbl, cnt]) => (
            <div key={tbl} style={{
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              background: 'rgba(15, 25, 45, 0.6)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <span style={{ fontSize: '0.8rem', color: '#fff', fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
                {tbl}
              </span>
              <span style={{ fontSize: '0.8rem', color: '#38bdf8', fontWeight: 600 }}>
                {cnt?.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Safe Read-Only SQL Query Console */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Terminal size={18} color="#38bdf8" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Live Zetaris / PostgreSQL Query Diagnostic Terminal
            </h3>
          </div>
          <span className="agri-badge emerald">Read-Only Guard Active</span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={2}
            className="agri-input"
            style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: '0.85rem', resize: 'vertical' }}
            placeholder="SELECT ... FROM v_batch_spoilage_risk"
          />
          <button
            onClick={handleRunQuery}
            disabled={queryRunning}
            className="agri-btn primary"
            style={{ height: 'auto', padding: '0 1.25rem' }}
          >
            <Play size={16} />
            <span>{queryRunning ? 'Executing...' : 'Run Query'}</span>
          </button>
        </div>

        {queryError && (
          <div style={{
            padding: '0.75rem',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: '8px',
            color: '#f87171',
            fontSize: '0.8rem'
          }}>
            {queryError}
          </div>
        )}

        {queryResult && (
          <div style={{ marginTop: '0.75rem' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.4rem' }}>
              Returned {queryResult.row_count || queryResult.rows?.length || 0} rows via Zetaris Gateway:
            </div>
            <div className="agri-table-wrapper" style={{ maxHeight: '280px' }}>
              <table className="agri-table">
                <thead>
                  <tr>
                    {(queryResult.columns || Object.keys(queryResult.rows[0] || {})).map(c => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(queryResult.rows || []).map((row, i) => (
                    <tr key={i}>
                      {(queryResult.columns || Object.keys(row)).map(col => (
                        <td key={col} style={{ fontSize: '0.75rem' }}>
                          {String(row[col] ?? '')}
                        </td>
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
  );
}
