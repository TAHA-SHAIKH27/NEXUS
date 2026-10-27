import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  MapPin,
  Calendar,
  Building2,
  AlertCircle,
  RefreshCw,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend
} from 'recharts';

export default function MarketIntelligence() {
  const [selectedCrop, setSelectedCrop] = useState('Tomato');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const cropsList = [
    'Tomato', 'Onion', 'Potato', 'Grapes', 'Pomegranate',
    'Banana', 'Turmeric', 'Chilli', 'Cotton', 'Soybean', 'Wheat'
  ];

  useEffect(() => {
    fetchMarketData(selectedCrop);
  }, [selectedCrop]);

  const fetchMarketData = async (crop) => {
    try {
      setLoading(true);
      const res = await fetch(`/api/fpo/market-prices?crop_name=${encodeURIComponent(crop)}`);
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

  const trends = (data?.trends || []).slice(0, 30).reverse().map(t => ({
    date: t.observation_date ? t.observation_date.slice(5) : '',
    modal: parseFloat(t.avg_modal_price || 0),
    min: parseFloat(t.min_price || 0),
    max: parseFloat(t.max_price || 0),
    market: t.market_name
  }));

  const comparison = (data?.market_comparison || []).map(m => ({
    market: m.market_name,
    avg: parseFloat(m.avg_price || 0),
    min: parseFloat(m.min_price || 0),
    max: parseFloat(m.max_price || 0),
    district: m.district,
    state: m.state
  }));

  const buyers = data?.top_buyers || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header with Crop Switcher */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <TrendingUp size={20} color="#34d399" />
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                APMC Market Price Trends & Regional Arbitrage
              </h2>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Aggregating wholesale mandi price observations across Maharashtra, Telangana, and Karnataka trading hubs.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span className="agri-badge amber" style={{ fontSize: '0.7rem' }}>
              <AlertCircle size={12} />
              <span>Synthetic Demo Dataset (Labeled)</span>
            </span>
            <button onClick={() => fetchMarketData(selectedCrop)} className="agri-btn ghost">
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Crop Pills */}
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {cropsList.map(c => (
            <button
              key={c}
              onClick={() => setSelectedCrop(c)}
              style={{
                background: selectedCrop === c ? 'linear-gradient(135deg, #0284c7, #10b981)' : 'rgba(255, 255, 255, 0.04)',
                color: selectedCrop === c ? '#fff' : 'var(--text-muted)',
                border: `1px solid ${selectedCrop === c ? 'transparent' : 'rgba(255, 255, 255, 0.08)'}`,
                borderRadius: '8px',
                padding: '0.35rem 0.85rem',
                fontSize: '0.8rem',
                cursor: 'pointer',
                fontWeight: selectedCrop === c ? 600 : 400,
                transition: 'all 0.15s ease'
              }}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: '1.25rem' }}>
        {/* Price History Area Chart */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Price Discovery Over Time
            </div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Historical Modal Price: {selectedCrop} (₹/Quintal)
            </h3>
          </div>

          <div style={{ height: '300px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="mktPriceGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                <XAxis dataKey="date" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0b1322', borderColor: 'rgba(56, 189, 248, 0.3)', borderRadius: '8px', color: '#fff' }}
                  formatter={(val, name, item) => [`₹${val} / Quintal (${item.payload.market || ''})`, 'Price']}
                />
                <Area type="monotone" dataKey="modal" stroke="#38bdf8" strokeWidth={2} fillOpacity={1} fill="url(#mktPriceGrad)" name="Modal Price" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Mandi Comparison Bar Chart */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Regional Mandi Rates
            </div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Cross-Market Price Comparison (₹/Quintal)
            </h3>
          </div>

          <div style={{ height: '300px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={comparison.slice(0, 8)} margin={{ top: 10, right: 10, left: -10, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                <XAxis dataKey="market" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} angle={-25} textAnchor="end" />
                <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0b1322', borderColor: 'rgba(16, 185, 129, 0.3)', borderRadius: '8px', color: '#fff' }}
                  formatter={(val, name, item) => [`₹${val} (Range: ₹${item.payload.min} - ₹${item.payload.max})`, 'Avg Modal Price']}
                />
                <Bar dataKey="avg" fill="#10b981" radius={[6, 6, 0, 0]} name="Avg Modal Price" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Top Wholesale Buyers Table */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Top Commercial Buyers & Procurement Partners ({selectedCrop})
            </h3>
            <p style={{ margin: '0.2rem 0 0', color: 'var(--text-faint)', fontSize: '0.75rem' }}>
              Historical procurement volume and realized price benchmarks per buyer type.
            </p>
          </div>
          <span className="agri-badge purple">Sales Intelligence</span>
        </div>

        <div className="agri-table-wrapper">
          <table className="agri-table">
            <thead>
              <tr>
                <th>Buyer Name</th>
                <th>Category</th>
                <th>Primary Market</th>
                <th>Total Orders</th>
                <th>Total Procurement (INR)</th>
                <th>Avg Realized Unit Price</th>
              </tr>
            </thead>
            <tbody>
              {buyers.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-faint)' }}>
                    No buyer procurement transactions recorded for this crop.
                  </td>
                </tr>
              ) : (
                buyers.map((b, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, color: '#fff' }}>{b.buyer_name}</td>
                    <td>
                      <span className="agri-badge cyan" style={{ fontSize: '0.68rem' }}>
                        {b.buyer_type}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-muted)' }}>
                        <MapPin size={13} />
                        <span>{b.market}</span>
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>{b.total_orders}</td>
                    <td style={{ fontWeight: 600, color: '#34d399' }}>
                      ₹{parseFloat(b.total_purchase_inr || 0).toLocaleString()}
                    </td>
                    <td style={{ fontWeight: 600, color: '#38bdf8' }}>
                      ₹{parseFloat(b.avg_unit_price_inr || 0).toFixed(2)} / kg
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
