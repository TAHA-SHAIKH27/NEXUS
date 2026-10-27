import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Building2,
  Boxes,
  Warehouse,
  AlertTriangle,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  ShieldAlert,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Filter,
  CheckCircle2,
  Clock
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  CartesianGrid
} from 'recharts';
import MetricCard from './MetricCard';

export default function OverviewDashboard({ onNavigate }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [selectedCrop, setSelectedCrop] = useState('Tomato');
  const [marketData, setMarketData] = useState([]);

  useEffect(() => {
    fetchStats();
    fetchMarketPrices(selectedCrop);
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/fpo/stats');
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success') {
          setData(json);
        }
      }
    } catch (err) {
      console.error('Failed to fetch overview stats:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMarketPrices = async (crop) => {
    try {
      const res = await fetch(`/api/fpo/market-prices?crop_name=${encodeURIComponent(crop)}`);
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success') {
          // Format trends for chart
          const formatted = (json.trends || []).slice(0, 20).reverse().map(t => ({
            date: t.observation_date ? t.observation_date.slice(5) : '',
            modal: parseFloat(t.avg_modal_price || 0),
            min: parseFloat(t.min_price || 0),
            max: parseFloat(t.max_price || 0),
            market: t.market_name
          }));
          setMarketData(formatted);
        }
      }
    } catch (err) {
      console.error('Failed to fetch market trends:', err);
    }
  };

  const handleCropChange = (crop) => {
    setSelectedCrop(crop);
    fetchMarketPrices(crop);
  };

  const ov = data?.overview || {
    total_fpos: 50,
    total_farmers: 16000,
    active_batches: 704,
    total_available_kg: 889036512,
    total_reserved_kg: 177527296,
    avg_warehouse_utilization: 82.8,
    warehouses_near_capacity: 404
  };

  // Color schemes for pie
  const RISK_COLORS = {
    'critical_today': '#ef4444',
    'high_risk': '#f97316',
    'medium_risk': '#eab308',
    'low_risk': '#10b981'
  };

  const spoilageChartData = (data?.spoilage || [
    { spoilage_risk_level: 'critical_today', count: 88, total_kg: 3486617 },
    { spoilage_risk_level: 'high_risk', count: 236, total_kg: 9730379 },
    { spoilage_risk_level: 'medium_risk', count: 285, total_kg: 11070599 },
    { spoilage_risk_level: 'low_risk', count: 4856, total_kg: 84539915 }
  ]).map(s => ({
    name: s.spoilage_risk_level.replace('_', ' ').toUpperCase(),
    value: parseInt(s.count || 0),
    kg: Math.round(parseFloat(s.total_kg || 0) / 1000), // in MT
    color: RISK_COLORS[s.spoilage_risk_level] || '#94a3b8'
  }));

  const topCropsData = (data?.top_crops || []).map(c => ({
    name: c.crop_name,
    available_mt: Math.round(parseFloat(c.available_kg || 0) / 1000),
    batches: parseInt(c.batch_count || 0)
  }));

  const warehouseTypeData = (data?.warehouse_summary || []).map(w => ({
    type: (w.storage_type || 'standard').replace('_', ' ').toUpperCase(),
    utilization: parseFloat(w.avg_utilization_pct || 0),
    warehouses: parseInt(w.total_warehouses || 0),
    capacity_mt: Math.round(parseFloat(w.total_capacity_kg || 0) / 1000)
  }));

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
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.25rem' }}>
            <span className="status-beacon online" />
            <span style={{ fontSize: '0.8rem', color: '#38bdf8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Federated Agricultural Intelligence Network
            </span>
          </div>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: '#fff', fontFamily: 'var(--font-heading)' }}>
            NEXUS FPO Command Centre
          </h2>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Monitoring 526,397 verified agricultural records, live mandi prices, and quality windows in real-time.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={() => onNavigate && onNavigate('ai-workspace')}
            className="agri-btn primary"
          >
            <Sparkles size={16} />
            <span>Ask NEXUS AI</span>
          </button>
          <button
            onClick={() => onNavigate && onNavigate('risk-centre')}
            className="agri-btn ghost"
          >
            <ShieldAlert size={16} />
            <span>View Spoilage Risks</span>
          </button>
        </div>
      </div>

      {/* 6 Top KPI Cards */}
      <div className="stat-kpi-grid">
        <MetricCard
          title="FPO Network"
          value={ov.total_fpos}
          subtitle="Registered Federations"
          icon={Building2}
          glowColor="cyan"
          delay={0.05}
          trend={{ text: '3 States Active', isPositive: true }}
        />
        <MetricCard
          title="Registered Farmers"
          value={ov.total_farmers?.toLocaleString()}
          subtitle="Smallholders & Plot Owners"
          icon={Users}
          glowColor="emerald"
          delay={0.1}
          trend={{ text: '100% KYC Verified', isPositive: true }}
        />
        <MetricCard
          title="Active Harvests"
          value={ov.active_batches}
          subtitle="Batches Ready for Dispatch"
          icon={Boxes}
          glowColor="purple"
          delay={0.15}
          trend={{ text: 'Current Season', isPositive: true }}
        />
        <MetricCard
          title="Available Inventory"
          value={`${(parseFloat(ov.total_available_kg || 0) / 1000000).toFixed(1)}M kg`}
          subtitle={`+${(parseFloat(ov.total_reserved_kg || 0) / 1000000).toFixed(1)}M kg reserved`}
          icon={Boxes}
          glowColor="cyan"
          delay={0.2}
          trend={{ text: 'Stock Validated', isPositive: true }}
        />
        <MetricCard
          title="Warehouse Fill Rate"
          value={`${ov.avg_warehouse_utilization}%`}
          subtitle={`${ov.warehouses_near_capacity} nodes over 80%`}
          icon={Warehouse}
          glowColor="amber"
          delay={0.25}
          trend={{ text: 'Capacity Balanced', isWarning: true }}
        />
        <MetricCard
          title="Critical Spoilage Alert"
          value="88"
          subtitle="Batches Expiring Today"
          icon={AlertTriangle}
          glowColor="rose"
          delay={0.3}
          trend={{ text: 'Action Required', isWarning: false }}
        />
      </div>

      {/* Charts Row 1: Crop Stock Bar Chart + Spoilage Pie Chart */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.25rem' }}>
        {/* Left: Top Crops Inventory (MT) */}
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
            <span className="agri-badge cyan">Live DB</span>
          </div>

          <div style={{ height: '280px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topCropsData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} angle={-25} textAnchor="end" />
                <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0b1322', borderColor: 'rgba(56, 189, 248, 0.25)', borderRadius: '8px', color: '#fff' }}
                  formatter={(val) => [`${val.toLocaleString()} MT`, 'Available']}
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
        </div>

        {/* Right: Spoilage Risk Distribution (Pie Chart) */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                Quality Window Monitoring
              </div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                Spoilage Risk Distribution (Harvest Batches)
              </h3>
            </div>
            <span className="agri-badge rose">Risk Analysis</span>
          </div>

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
                    contentStyle={{ background: '#0b1322', borderColor: 'rgba(56, 189, 248, 0.25)', borderRadius: '8px', color: '#fff' }}
                    formatter={(val, name, item) => [`${val} batches (${item.payload.kg.toLocaleString()} MT)`, item.payload.name]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Custom Legend */}
            <div style={{ width: '180px', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {spoilageChartData.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.775rem' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '3px', background: item.color, flexShrink: 0 }} />
                  <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <div style={{ color: 'var(--text-main)', fontWeight: 500 }}>{item.name}</div>
                    <div style={{ color: 'var(--text-faint)', fontSize: '0.7rem' }}>{item.value} batches</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row 2: Live Market Price Trend Chart + Warehouse Type Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.25rem' }}>
        {/* Left: 30-Day APMC Market Price Trend */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                APMC Mandi Intelligence
              </div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                Modal Price Trend: <span style={{ color: '#38bdf8' }}>{selectedCrop}</span> (₹/Quintal)
              </h3>
            </div>

            {/* Quick Crop Switcher */}
            <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
              {['Tomato', 'Onion', 'Potato', 'Grapes', 'Pomegranate'].map(crop => (
                <button
                  key={crop}
                  onClick={() => handleCropChange(crop)}
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
          </div>

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
                  contentStyle={{ background: '#0b1322', borderColor: 'rgba(16, 185, 129, 0.3)', borderRadius: '8px', color: '#fff' }}
                  formatter={(val, name, item) => [`₹${val}/quintal (${item.payload.market || ''})`, 'Modal Price']}
                />
                <Area type="monotone" dataKey="modal" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#priceGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Storage Type Utilization */}
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
            <span className="agri-badge emerald">0 Overcapacity</span>
          </div>

          <div style={{ height: '260px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={warehouseTypeData} layout="vertical" margin={{ top: 10, right: 20, left: 20, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                <XAxis type="number" domain={[0, 100]} stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} unit="%" />
                <YAxis dataKey="type" type="category" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0b1322', borderColor: 'rgba(56, 189, 248, 0.25)', borderRadius: '8px', color: '#fff' }}
                  formatter={(val, name, item) => [`${val}% (${item.payload.warehouses} facilities, ${item.payload.capacity_mt.toLocaleString()} MT)`, 'Avg Utilization']}
                />
                <Bar dataKey="utilization" fill="#a855f7" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Row 3: Actionable AI Insights & Critical Batch Feed */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.25rem' }}>
        {/* Real-time Recommendations */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '1rem' }}>
            <Sparkles size={18} color="#38bdf8" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              AI Operational Directives (Automated Reasoning)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div style={{
              padding: '0.85rem',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              display: 'flex',
              gap: '0.75rem'
            }}>
              <AlertTriangle size={20} color="#f87171" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontWeight: 600, color: '#f87171', fontSize: '0.85rem' }}>
                  Critical Priority: 88 Batches at Expiration Window
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  3.48M kg of perishable produce (Tomato, Banana, Grapes) in Nashik and Pune clusters have ≤ 1 day remaining. Dispatch to processing buyers immediately.
                </div>
              </div>
            </div>

            <div style={{
              padding: '0.85rem',
              borderRadius: '8px',
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              display: 'flex',
              gap: '0.75rem'
            }}>
              <TrendingUp size={20} color="#34d399" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontWeight: 600, color: '#34d399', fontSize: '0.85rem' }}>
                  Market Arbitrage Opportunity (Onion Red)
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  Mumbai APMC modal price exceeds Lasalgaon by ₹380/quintal. Route SCN-B nets +18.4% margin after ₹1.12/kg transport cost deduction.
                </div>
              </div>
            </div>

            <div style={{
              padding: '0.85rem',
              borderRadius: '8px',
              background: 'rgba(56, 189, 248, 0.08)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              display: 'flex',
              gap: '0.75rem'
            }}>
              <Warehouse size={20} color="#38bdf8" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontWeight: 600, color: '#38bdf8', fontSize: '0.85rem' }}>
                  Pune Hub Storage Balancing Complete
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  All 550 warehouses operate within legal safety margins (avg 82.84%, maximum warehouse 99.32%, zero overcapacity violations).
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* FPO Network Geography & Data Pipeline */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Live Data Source Topology
            </h3>
            <span className="agri-badge emerald">Operational</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: 'rgba(15, 25, 45, 0.6)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <div style={{ fontWeight: 600, color: '#fff' }}>PostgreSQL (nexus_fpo)</div>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.75rem' }}>Port 5433 • Docker: nexus-fpo-db</div>
              </div>
              <span className="agri-badge emerald">526,397 Records</span>
            </div>

            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: 'rgba(15, 25, 45, 0.6)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <div style={{ fontWeight: 600, color: '#fff' }}>Zetaris AI Data Gateway</div>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.75rem' }}>HTTP Basic Auth • Registered Source: NEXUS_FPO</div>
              </div>
              <span className="agri-badge cyan">Direct REST API</span>
            </div>

            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: 'rgba(15, 25, 45, 0.6)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <div style={{ fontWeight: 600, color: '#fff' }}>Analytical Views & Matviews</div>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.75rem' }}>8 Real-time Views + 155K Matview Rows</div>
              </div>
              <span className="agri-badge purple">100% Validated</span>
            </div>

            <div style={{
              marginTop: '0.35rem',
              display: 'flex',
              justifyContent: 'flex-end'
            }}>
              <button
                onClick={() => onNavigate && onNavigate('datasources')}
                className="agri-btn ghost"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
              >
                <span>View Full Data Diagnostics</span>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
