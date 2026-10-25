import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Building2,
  Boxes,
  Warehouse,
  AlertTriangle,
  TrendingUp,
  ShieldAlert,
  Sparkles,
  ChevronRight,
  RefreshCw,
  IndianRupee,
  CalendarClock,
  Database,
  WifiOff
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  CartesianGrid
} from 'recharts';
import MetricCard from './MetricCard';

const RISK_COLORS = {
  expired: '#ef4444',
  critical_today: '#ef4444',
  high_risk: '#f97316',
  medium_risk: '#eab308',
  low_risk: '#10b981',
  unknown: '#94a3b8'
};

const RISK_LABELS = {
  expired: 'Expired Window',
  critical_today: 'Critical Today',
  high_risk: 'High Risk',
  medium_risk: 'Medium Risk',
  low_risk: 'Low Risk',
  unknown: 'Unknown'
};

const fmtKg = (v) => {
  const n = parseFloat(v || 0);
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B kg`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M kg`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K kg`;
  return `${n.toFixed(0)} kg`;
};

const fmtInr = (v) => {
  const n = parseFloat(v || 0);
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return `₹${n.toLocaleString('en-IN')}`;
};

function KpiSkeleton() {
  return (
    <div className="stat-kpi-grid" aria-busy="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="agri-card" style={{ padding: '1.1rem', minHeight: 118 }}>
          <div className="agri-skeleton" style={{ width: '55%', height: 10 }} />
          <div className="agri-skeleton" style={{ width: '38%', height: 26, marginTop: 12 }} />
          <div className="agri-skeleton" style={{ width: '70%', height: 9, marginTop: 12 }} />
        </div>
      ))}
    </div>
  );
}

export default function OverviewDashboard({ onNavigate }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [recordTotal, setRecordTotal] = useState(null);
  const [refreshedAt, setRefreshedAt] = useState(null);
  const [selectedCrop, setSelectedCrop] = useState('');
  const [marketData, setMarketData] = useState([]);
  const [cropOptions, setCropOptions] = useState([]);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketError, setMarketError] = useState(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/fpo/stats');
      const json = await res.json().catch(() => null);
      if (res.ok && json && json.status === 'success') {
        setData(json);
        setRefreshedAt(new Date());
        // Optional: total record count for the pipeline badge (non-fatal)
        fetch('/api/fpo/datasources')
          .then(r => (r.ok ? r.json() : null))
          .then(j => {
            if (j && j.status === 'success' && j.postgresql?.table_counts) {
              const total = Object.values(j.postgresql.table_counts)
                .reduce((a, v) => a + (parseInt(v, 10) || 0), 0);
              if (total > 0) setRecordTotal(total);
            }
          })
          .catch(() => {});
      } else {
        setError((json && (json.message || json.error)) || `Request failed (HTTP ${res.status})`);
      }
    } catch (e) {
      setError('Unable to reach the NEXUS backend. Is the FastAPI service running?');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMarketPrices = useCallback(async (crop) => {
    if (!crop) return;
    setMarketLoading(true);
    setMarketError(null);
    try {
      const res = await fetch(`/api/fpo/market-prices?crop_name=${encodeURIComponent(crop)}`);
      const json = await res.json().catch(() => null);
      if (res.ok && json && json.status === 'success') {
        const formatted = (json.trends || []).slice(0, 30).reverse().map(t => ({
          date: t.observation_date ? t.observation_date.slice(5) : '',
          modal: parseFloat(t.avg_modal_price || 0),
          market: t.market_name
        }));
        setMarketData(formatted);
        if (Array.isArray(json.available_crops) && json.available_crops.length) {
          setCropOptions(json.available_crops);
        }
        if (!formatted.length) setMarketError('No price observations for this crop in the selected window.');
      } else {
        setMarketError((json && (json.message || json.error)) || 'Price data unavailable.');
      }
    } catch {
      setMarketError('Unable to retrieve market prices from Zetaris.');
    } finally {
      setMarketLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => {
    if (!selectedCrop && cropOptions.length) setSelectedCrop(cropOptions[0]);
  }, [cropOptions, selectedCrop]);
  useEffect(() => { if (selectedCrop) fetchMarketPrices(selectedCrop); }, [selectedCrop, fetchMarketPrices]);

  const ov = data?.overview || {};

  const spoilageChartData = (data?.spoilage || []).map(s => ({
    name: RISK_LABELS[s.spoilage_risk_level] || s.spoilage_risk_level,
    value: parseInt(s.batch_count || 0, 10),
    kg: Math.round(parseFloat(s.total_kg || 0) / 1000),
    color: RISK_COLORS[s.spoilage_risk_level] || '#94a3b8'
  })).filter(d => d.value > 0);

  const topCropsData = (data?.top_crops || []).map(c => ({
    name: c.crop_name,
    available_mt: Math.round(parseFloat(c.available_kg || 0) / 1000),
    batches: parseInt(c.batch_count || 0, 10)
  }));

  const warehouseTypeData = (data?.warehouse_summary || []).map(w => ({
    type: (w.storage_type || 'standard').replace(/_/g, ' '),
    utilization: parseFloat(w.avg_utilization_pct || 0),
    warehouses: parseInt(w.total_warehouses || 0, 10),
    capacity_mt: Math.round(parseFloat(w.total_capacity_kg || 0) / 1000)
  }));

  const urgentAlerts = data?.urgent_alerts || [];
  const marketSnapshot = data?.market_snapshot || [];

  const tooltipStyle = {
    background: '#0b1322',
    borderColor: 'rgba(56, 189, 248, 0.25)',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '0.8rem'
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Platform Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.22) 0%, rgba(16, 185, 129, 0.12) 100%)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        borderRadius: '12px',
        padding: '1.25rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
            <span className={`status-beacon ${error ? 'offline' : 'online'}`} />
            <span style={{ fontSize: '0.8rem', color: '#38bdf8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Federated Agricultural Intelligence Network
            </span>
            {data?.source && (
              <span className="agri-badge cyan" style={{ fontSize: '0.65rem' }}>
                <Database size={11} /> source: {data.source}
              </span>
            )}
          </div>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: '#fff', fontFamily: 'var(--font-heading)' }}>
            FPO Operations Overview
          </h2>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Monitor harvests, identify emerging risks and coordinate agricultural decisions.
            {recordTotal ? ` ${recordTotal.toLocaleString('en-IN')} records via Zetaris.` : ''}
            {refreshedAt ? ` Refreshed ${refreshedAt.toLocaleTimeString()}.` : ''}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button onClick={fetchStats} className="agri-btn ghost" disabled={loading}>
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={() => onNavigate && onNavigate('ai-workspace')} className="agri-btn primary">
            <Sparkles size={16} />
            <span>Ask NEXUS AI</span>
          </button>
          <button onClick={() => onNavigate && onNavigate('risk-centre')} className="agri-btn ghost">
            <ShieldAlert size={16} />
            <span>Risk Centre</span>
          </button>
        </div>
      </div>

      {/* Error state — no fake fallback numbers */}
      {error && (
        <div className="agri-card" style={{
          padding: '1.5rem',
          borderColor: 'rgba(239, 68, 68, 0.35)',
          background: 'rgba(239, 68, 68, 0.06)',
          display: 'flex',
          gap: '0.9rem',
          alignItems: 'flex-start'
        }} role="alert">
          <WifiOff size={22} color="#f87171" style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontWeight: 600, color: '#f87171', marginBottom: '0.25rem' }}>
              Unable to retrieve FPO data
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{error}</div>
            <button onClick={fetchStats} className="agri-btn primary" style={{ marginTop: '0.85rem' }}>
              <RefreshCw size={14} /> <span>Retry</span>
            </button>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      {loading ? (
        <KpiSkeleton />
      ) : !error && (
        <div className="stat-kpi-grid">
          <MetricCard
            title="FPO Network"
            value={ov.total_fpos ?? '—'}
            subtitle="Registered Federations"
            icon={Building2}
            glowColor="cyan"
            delay={0.05}
          />
          <MetricCard
            title="Registered Farmers"
            value={ov.total_farmers != null ? ov.total_farmers.toLocaleString('en-IN') : '—'}
            subtitle="Active Members"
            icon={Users}
            glowColor="emerald"
            delay={0.1}
          />
          <MetricCard
            title="Active Harvest Batches"
            value={ov.active_batches != null ? ov.active_batches.toLocaleString('en-IN') : '—'}
            subtitle={ov.planned_batches != null ? `${ov.planned_batches.toLocaleString('en-IN')} planned ahead` : 'Harvested / stored / partial'}
            icon={Boxes}
            glowColor="purple"
            delay={0.15}
          />
          <MetricCard
            title="Physical Inventory"
            value={fmtKg(ov.physical_stock_kg)}
            subtitle={ov.reserved_stock_kg != null ? `${fmtKg(ov.reserved_stock_kg)} reserved` : 'Current stock positions'}
            icon={Boxes}
            glowColor="cyan"
            delay={0.2}
          />
          <MetricCard
            title="Warehouse Utilization"
            value={ov.avg_warehouse_utilization_pct != null ? `${ov.avg_warehouse_utilization_pct}%` : '—'}
            subtitle={ov.warehouses_near_capacity != null
              ? `${ov.warehouses_near_capacity.toLocaleString('en-IN')} of ${ov.total_warehouses?.toLocaleString('en-IN') ?? '—'} nodes ≥ 80%`
              : 'Across active facilities'}
            icon={Warehouse}
            glowColor="amber"
            delay={0.25}
          />
          <MetricCard
            title="High-Risk Batches"
            value={ov.high_risk_batches != null ? ov.high_risk_batches.toLocaleString('en-IN') : '—'}
            subtitle="Quality window at risk"
            icon={AlertTriangle}
            glowColor="rose"
            delay={0.3}
          />
          <MetricCard
            title="Available Capacity"
            value={fmtKg(ov.available_capacity_kg)}
            subtitle="Spare warehouse space"
            icon={Warehouse}
            glowColor="emerald"
            delay={0.35}
          />
          <MetricCard
            title="Recorded Revenue"
            value={fmtInr(ov.recorded_revenue_inr)}
            subtitle="Delivered orders (est.)"
            icon={IndianRupee}
            glowColor="cyan"
            delay={0.4}
          />
        </div>
      )}

      {/* Charts Row 1 */}
      {!error && !loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.25rem' }}>
          {/* Top Crops */}
          <div className="agri-card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  Inventory Volume
                </div>
                <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                  Available Stock by Major Crop (Metric Tonnes)
                </h3>
              </div>
              <span className="agri-badge cyan">Live Data</span>
            </div>

            {topCropsData.length === 0 ? (
              <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-faint)', fontSize: '0.85rem' }}>
                No inventory records available.
              </div>
            ) : (
              <div style={{ height: '280px', width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topCropsData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                    <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} angle={-25} textAnchor="end" />
                    <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(val, name, item) => [
                        `${val.toLocaleString('en-IN')} MT • ${item.payload.batches} batches`, 'Available'
                      ]}
                    />
                    <Bar dataKey="available_mt" fill="url(#cyanGradient)" radius={[6, 6, 0, 0]} />
                    <defs>
                      <linearGradient id="cyanGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.9} />
                        <stop offset="100%" stopColor="#0284c7" stopOpacity={0.4} />
                      </linearGradient>
                    </defs>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Spoilage Risk */}
          <div className="agri-card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  Quality Window Monitoring
                </div>
                <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                  Spoilage Risk Distribution (Batches with Stock)
                </h3>
              </div>
              <span className="agri-badge rose">Risk Analysis</span>
            </div>

            {spoilageChartData.length === 0 ? (
              <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-faint)', fontSize: '0.85rem' }}>
                No spoilage-risk data available.
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', height: '280px' }}>
                <div style={{ flex: 1, height: '100%' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={spoilageChartData}
                        cx="50%"
                        cy="50%"
                        innerRadius={65}
                        outerRadius={95}
                        paddingAngle={4}
                        dataKey="value"
                      >
                        {spoilageChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} stroke="rgba(7, 12, 22, 0.8)" strokeWidth={2} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={tooltipStyle}
                        formatter={(val, name, item) => [`${val.toLocaleString('en-IN')} batches (${item.payload.kg.toLocaleString('en-IN')} MT)`, item.payload.name]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ width: '180px', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                  {spoilageChartData.map((item, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.775rem' }}>
                      <div style={{ width: '10px', height: '10px', borderRadius: '3px', background: item.color, flexShrink: 0 }} />
                      <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <div style={{ color: 'var(--text-main)', fontWeight: 500 }}>{item.name}</div>
                        <div style={{ color: 'var(--text-faint)', fontSize: '0.7rem' }}>{item.value.toLocaleString('en-IN')} batches</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Charts Row 2 */}
      {!error && !loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.25rem' }}>
          {/* Market Price Trend */}
          <div className="agri-card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  Market Intelligence
                </div>
                <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                  Modal Price Trend: <span style={{ color: '#38bdf8' }}>{selectedCrop || '—'}</span> (₹/Quintal)
                </h3>
              </div>
              <span className="agri-badge amber" title="Generated price observations — not live market data">
                Synthetic Demo Data
              </span>
            </div>

            <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginBottom: '0.6rem' }}>
              {(cropOptions.length ? cropOptions : []).slice(0, 8).map(crop => (
                <button
                  key={crop}
                  onClick={() => setSelectedCrop(crop)}
                  style={{
                    background: selectedCrop === crop ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                    color: selectedCrop === crop ? '#38bdf8' : 'var(--text-faint)',
                    border: `1px solid ${selectedCrop === crop ? 'rgba(56, 189, 248, 0.4)' : 'transparent'}`,
                    borderRadius: '6px',
                    padding: '0.2rem 0.55rem',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                    fontWeight: selectedCrop === crop ? 600 : 400
                  }}
                >
                  {crop}
                </button>
              ))}
            </div>

            {marketLoading ? (
              <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-faint)' }}>
                Loading price observations…
              </div>
            ) : marketError ? (
              <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-faint)', fontSize: '0.85rem' }}>
                {marketError}
              </div>
            ) : (
              <div style={{ height: '260px', width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={marketData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                    <XAxis dataKey="date" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ ...tooltipStyle, borderColor: 'rgba(16, 185, 129, 0.3)' }}
                      formatter={(val, name, item) => [`₹${val.toLocaleString('en-IN')}/quintal (${item.payload.market || ''})`, 'Avg Modal Price']}
                    />
                    <Area type="monotone" dataKey="modal" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#priceGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Storage Type Utilization */}
          <div className="agri-card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  Infrastructure Capacity
                </div>
                <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                  Storage Type Utilization & Capacity
                </h3>
              </div>
              <span className="agri-badge emerald">Live Data</span>
            </div>

            {warehouseTypeData.length === 0 ? (
              <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-faint)', fontSize: '0.85rem' }}>
                No warehouse data available.
              </div>
            ) : (
              <div style={{ height: '260px', width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={warehouseTypeData} layout="vertical" margin={{ top: 10, right: 20, left: 20, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                    <XAxis type="number" domain={[0, 100]} stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} unit="%" />
                    <YAxis dataKey="type" type="category" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} width={110} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(val, name, item) => [
                        `${val}% • ${item.payload.warehouses} facilities • ${item.payload.capacity_mt.toLocaleString('en-IN')} MT`, 'Avg Utilization'
                      ]}
                    />
                    <Bar dataKey="utilization" fill="#a855f7" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Row 3: Urgent Alerts (real data) + Latest Market Snapshot */}
      {!error && !loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.25rem' }}>
          <div className="agri-card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '1rem' }}>
              <AlertTriangle size={18} color="#f97316" />
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                Batches Needing Attention
              </h3>
            </div>

            {urgentAlerts.length === 0 ? (
              <div style={{ color: 'var(--text-faint)', fontSize: '0.85rem', padding: '1rem 0' }}>
                No batches are currently in the critical or high-risk window. 🎉
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {urgentAlerts.map((a, i) => (
                  <button
                    key={`${a.batch_code}-${i}`}
                    onClick={() => onNavigate && onNavigate('risk-centre')}
                    style={{
                      textAlign: 'left',
                      padding: '0.75rem',
                      borderRadius: '8px',
                      background: 'rgba(239, 68, 68, 0.07)',
                      border: '1px solid rgba(239, 68, 68, 0.22)',
                      display: 'flex',
                      gap: '0.75rem',
                      cursor: 'pointer',
                      color: 'inherit'
                    }}
                  >
                    <AlertTriangle size={18} color={RISK_COLORS[a.spoilage_risk_level] || '#f87171'} style={{ flexShrink: 0, marginTop: 2 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <span>{a.crop_name}{a.variety ? ` • ${a.variety}` : ''}</span>
                        <span style={{ color: RISK_COLORS[a.spoilage_risk_level] || '#f87171' }}>
                          {a.days_until_quality_window_end != null
                            ? (a.days_until_quality_window_end < 0
                              ? 'window passed'
                              : a.days_until_quality_window_end === 0
                                ? 'window ends today'
                                : `${a.days_until_quality_window_end} day(s) left`)
                            : RISK_LABELS[a.spoilage_risk_level]}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                        {a.batch_code} • {fmtKg(a.net_available_kg)} available • {a.farm_district}
                      </div>
                    </div>
                    <ChevronRight size={15} style={{ color: 'var(--text-faint)', alignSelf: 'center' }} />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="agri-card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <TrendingUp size={18} color="#34d399" />
                <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                  Latest Market Observations
                </h3>
              </div>
              <button onClick={() => onNavigate && onNavigate('markets')} className="agri-btn ghost" style={{ fontSize: '0.75rem', padding: '0.3rem 0.7rem' }}>
                Markets <ChevronRight size={13} />
              </button>
            </div>

            {marketSnapshot.length === 0 ? (
              <div style={{ color: 'var(--text-faint)', fontSize: '0.85rem', padding: '1rem 0' }}>
                No recent market observations available.
              </div>
            ) : (
              <div className="agri-table-wrapper" style={{ maxHeight: 300 }}>
                <table className="agri-table">
                  <thead>
                    <tr>
                      <th>Crop</th>
                      <th>Market</th>
                      <th>Modal ₹/q</th>
                      <th>Δ Day</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {marketSnapshot.slice(0, 8).map((m, i) => {
                      const chg = parseFloat(m.price_change_pct);
                      return (
                        <tr key={`${m.crop_name}-${m.market_name}-${i}`}>
                          <td style={{ fontWeight: 600, color: '#fff' }}>{m.crop_name}</td>
                          <td style={{ color: 'var(--text-muted)' }}>{m.market_name}</td>
                          <td style={{ fontWeight: 600 }}>₹{parseFloat(m.modal_price_inr_per_quintal || 0).toLocaleString('en-IN')}</td>
                          <td style={{ color: isNaN(chg) ? 'var(--text-faint)' : chg >= 0 ? '#34d399' : '#f87171' }}>
                            {isNaN(chg) ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(1)}%`}
                          </td>
                          <td style={{ color: 'var(--text-faint)', fontSize: '0.75rem' }}>{m.observation_date}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <div style={{ marginTop: '0.6rem', fontSize: '0.72rem', color: 'var(--text-faint)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <CalendarClock size={12} />
              Generated demonstration observations — not live mandi prices.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
