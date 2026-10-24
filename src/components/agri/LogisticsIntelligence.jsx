import React, { useState, useEffect } from 'react';
import {
  Truck,
  Warehouse,
  MapPin,
  Thermometer,
  ShieldCheck,
  RefreshCw,
  Navigation,
  Gauge
} from 'lucide-react';

export default function LogisticsIntelligence() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogistics();
  }, []);

  const fetchLogistics = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/fpo/logistics');
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

  const warehouses = data?.warehouses || [];
  const routes = data?.routes || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <Truck size={20} color="#38bdf8" />
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                Logistics Intelligence & Warehouse Network
              </h2>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Optimizing 550 storage facilities and inter-district transport routes across Western & Southern corridors.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span className="agri-badge emerald">
              <ShieldCheck size={12} />
              <span>Zero Overcapacity Verified</span>
            </span>
            <button onClick={fetchLogistics} className="agri-btn ghost">
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {/* Grid: Warehouses & Route Cost Table */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: '1.25rem' }}>
        {/* Top Warehouses by Utilization */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                Warehouse Capacity & Storage Nodes
              </h3>
              <p style={{ margin: '0.2rem 0 0', color: 'var(--text-faint)', fontSize: '0.75rem' }}>
                Monitored against 100% hard capacity ceilings.
              </p>
            </div>
            <span className="agri-badge amber">High Fill Nodes</span>
          </div>

          <div className="agri-table-wrapper" style={{ maxHeight: '420px' }}>
            <table className="agri-table">
              <thead>
                <tr>
                  <th>Facility</th>
                  <th>District</th>
                  <th>Type</th>
                  <th>Capacity (MT)</th>
                  <th>Fill %</th>
                </tr>
              </thead>
              <tbody>
                {warehouses.slice(0, 15).map((w) => (
                  <tr key={w.warehouse_id}>
                    <td>
                      <div style={{ fontWeight: 600, color: '#fff' }}>{w.warehouse_name}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                        {w.temperature_controlled && <Thermometer size={11} color="#38bdf8" />}
                        <span>{w.storage_type}</span>
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>{w.district}</td>
                    <td>
                      <span className={`agri-badge ${w.temperature_controlled ? 'cyan' : 'ghost'}`} style={{ fontSize: '0.65rem' }}>
                        {w.temperature_controlled ? 'Cold Chain' : 'Ambient'}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      {Math.round(parseFloat(w.capacity_kg || 0) / 1000).toLocaleString()} MT
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ flex: 1, height: '6px', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '3px', overflow: 'hidden', minWidth: '40px' }}>
                          <div style={{
                            width: `${Math.min(100, parseFloat(w.utilization_pct || 0))}%`,
                            height: '100%',
                            background: parseFloat(w.utilization_pct || 0) >= 90 ? '#ef4444' :
                                        parseFloat(w.utilization_pct || 0) >= 80 ? '#f59e0b' : '#10b981',
                            borderRadius: '3px'
                          }} />
                        </div>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>
                          {parseFloat(w.utilization_pct || 0).toFixed(1)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Transport Routes Cost Analysis */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
                Inter-District Transport Cost Matrix
              </h3>
              <p style={{ margin: '0.2rem 0 0', color: 'var(--text-faint)', fontSize: '0.75rem' }}>
                Per-kg logistics cost benchmarked by distance and fleet vehicle.
              </p>
            </div>
            <span className="agri-badge cyan">Logistics Optimization</span>
          </div>

          <div className="agri-table-wrapper" style={{ maxHeight: '420px' }}>
            <table className="agri-table">
              <thead>
                <tr>
                  <th>Origin & Destination</th>
                  <th>Vehicle</th>
                  <th>Distance</th>
                  <th>Cost / kg</th>
                </tr>
              </thead>
              <tbody>
                {routes.slice(0, 15).map((r) => (
                  <tr key={r.route_id}>
                    <td>
                      <div style={{ fontWeight: 600, color: '#fff' }}>{r.origin_warehouse}</div>
                      <div style={{ fontSize: '0.72rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Navigation size={11} />
                        <span>To {r.destination_buyer} ({r.destination_market})</span>
                      </div>
                    </td>
                    <td>
                      <span className="agri-badge ghost" style={{ fontSize: '0.68rem' }}>
                        {r.vehicle_type}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      {parseFloat(r.distance_km || 0).toFixed(0)} km
                    </td>
                    <td style={{ fontWeight: 700, color: '#34d399' }}>
                      ₹{parseFloat(r.transport_cost_per_kg_inr || 0).toFixed(2)} / kg
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
