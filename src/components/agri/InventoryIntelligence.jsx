import React, { useState, useEffect } from 'react';
import {
  Boxes,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Calendar,
  MapPin,
  Clock,
  ArrowUpDown,
  RefreshCw,
  Eye,
  X
} from 'lucide-react';

export default function InventoryIntelligence() {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [crop, setCrop] = useState('All');
  const [district, setDistrict] = useState('All');
  const [risk, setRisk] = useState('All');
  const [search, setSearch] = useState('');
  const [filterOpts, setFilterOpts] = useState({ crops: [], districts: [], risk_levels: [] });
  const [selectedBatch, setSelectedBatch] = useState(null);

  useEffect(() => {
    fetchFilters();
  }, []);

  useEffect(() => {
    fetchBatches();
  }, [page, crop, district, risk]);

  const fetchFilters = async () => {
    try {
      const res = await fetch('/api/fpo/filters');
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success') {
          setFilterOpts(json);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchBatches = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        crop_name: crop,
        district: district,
        risk_level: risk,
        search: search
      });
      const res = await fetch(`/api/fpo/inventory?${params.toString()}`);
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success') {
          setBatches(json.batches || []);
          setTotal(json.total || 0);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchBatches();
  };

  const getRiskBadge = (level) => {
    switch (level) {
      case 'critical_today':
        return <span className="agri-badge rose">Critical Today</span>;
      case 'high_risk':
        return <span className="agri-badge amber">High Risk</span>;
      case 'medium_risk':
        return <span className="agri-badge purple">Medium Risk</span>;
      default:
        return <span className="agri-badge emerald">Optimal</span>;
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Controls / Filter Bar */}
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
              Harvest Batches & Crop Stock Inventory
            </h2>
            <p style={{ margin: '0.2rem 0 0', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Querying {total.toLocaleString()} validated batches across Maharashtra & Telangana clusters.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button onClick={fetchBatches} className="agri-btn ghost" style={{ height: '36px' }}>
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          {/* Search box */}
          <div style={{ flex: '1', minWidth: '220px', position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }} />
            <input
              type="text"
              placeholder="Search batch code (e.g. HB-), crop, district..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="agri-input"
              style={{ width: '100%', paddingLeft: '34px', height: '36px' }}
            />
          </div>

          {/* Crop Dropdown */}
          <select
            value={crop}
            onChange={(e) => { setCrop(e.target.value); setPage(1); }}
            className="agri-select"
            style={{ height: '36px' }}
          >
            <option value="All">All Crops ({filterOpts.crops?.length || 0})</option>
            {(filterOpts.crops || []).map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          {/* District Dropdown */}
          <select
            value={district}
            onChange={(e) => { setDistrict(e.target.value); setPage(1); }}
            className="agri-select"
            style={{ height: '36px' }}
          >
            <option value="All">All Districts ({filterOpts.districts?.length || 0})</option>
            {(filterOpts.districts || []).map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>

          {/* Risk Level Dropdown */}
          <select
            value={risk}
            onChange={(e) => { setRisk(e.target.value); setPage(1); }}
            className="agri-select"
            style={{ height: '36px' }}
          >
            <option value="All">All Risk Levels</option>
            <option value="critical_today">Critical Today (≤ 0d)</option>
            <option value="high_risk">High Risk (1-3d)</option>
            <option value="medium_risk">Medium Risk (4-7d)</option>
            <option value="low_risk">Low Risk / Optimal</option>
          </select>

          <button type="submit" className="agri-btn primary" style={{ height: '36px' }}>
            Apply Filter
          </button>
        </form>
      </div>

      {/* Main Batch Table */}
      <div className="agri-card" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="agri-table-wrapper" style={{ maxHeight: '600px' }}>
          <table className="agri-table">
            <thead>
              <tr>
                <th>Batch Code</th>
                <th>Crop & Variety</th>
                <th>District</th>
                <th>Harvest Date</th>
                <th>Quality Window End</th>
                <th>Days Left</th>
                <th>Available (kg)</th>
                <th>Reserved (kg)</th>
                <th>Risk Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={10} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-faint)' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.75rem' }}>
                      <RefreshCw size={20} className="animate-spin" />
                      <span>Querying database batch catalog...</span>
                    </div>
                  </td>
                </tr>
              ) : batches.length === 0 ? (
                <tr>
                  <td colSpan={10} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-faint)' }}>
                    No harvest batches matched the selected filters.
                  </td>
                </tr>
              ) : (
                batches.map((b) => (
                  <tr key={b.batch_id}>
                    <td style={{ fontWeight: 600, color: '#38bdf8', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                      {b.batch_code}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: '#fff' }}>{b.crop_name}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>{b.variety} • {b.perishability_category}</div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <MapPin size={13} color="var(--text-faint)" />
                        <span>{b.farm_district}, {b.farm_state}</span>
                      </div>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {b.harvest_date}
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {b.estimated_quality_window_end}
                    </td>
                    <td>
                      <span style={{
                        fontWeight: 600,
                        color: b.days_until_quality_window_end <= 0 ? '#ef4444' :
                               b.days_until_quality_window_end <= 3 ? '#f97316' : '#10b981'
                      }}>
                        {b.days_until_quality_window_end <= 0 ? 'EXPIRED' : `${b.days_until_quality_window_end} days`}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      {parseFloat(b.total_available_kg || 0).toLocaleString()} kg
                    </td>
                    <td style={{ color: 'var(--text-faint)' }}>
                      {parseFloat(b.total_reserved_kg || 0).toLocaleString()} kg
                    </td>
                    <td>
                      {getRiskBadge(b.spoilage_risk_level)}
                    </td>
                    <td>
                      <button
                        onClick={() => setSelectedBatch(b)}
                        className="agri-btn ghost"
                        style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }}
                      >
                        <Eye size={13} />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div style={{
          padding: '0.85rem 1.25rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '0.8rem',
          color: 'var(--text-muted)'
        }}>
          <div>
            Showing Page <span style={{ color: '#fff', fontWeight: 600 }}>{page}</span> of <span style={{ color: '#fff', fontWeight: 600 }}>{totalPages}</span> ({total.toLocaleString()} total batches)
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="agri-btn ghost"
              style={{ padding: '0.35rem 0.65rem' }}
            >
              <ChevronLeft size={16} />
              <span>Previous</span>
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="agri-btn ghost"
              style={{ padding: '0.35rem 0.65rem' }}
            >
              <span>Next</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Detail Modal */}
      {selectedBatch && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: '1rem'
        }}>
          <div className="agri-card elevated" style={{ width: '100%', maxWidth: '580px', padding: '1.5rem', position: 'relative' }}>
            <button
              onClick={() => setSelectedBatch(null)}
              style={{
                position: 'absolute',
                top: '1rem',
                right: '1rem',
                background: 'rgba(255, 255, 255, 0.08)',
                border: 'none',
                borderRadius: '6px',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '4px'
              }}
            >
              <X size={18} />
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <Boxes size={20} color="#38bdf8" />
              <h3 style={{ margin: 0, color: '#fff', fontSize: '1.2rem', fontWeight: 700 }}>
                Batch Inspection: {selectedBatch.batch_code}
              </h3>
            </div>
            <div style={{ color: 'var(--text-faint)', fontSize: '0.8rem', marginBottom: '1.25rem' }}>
              UUID: {selectedBatch.batch_id}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.85rem' }}>
              <div style={{ padding: '0.75rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px' }}>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>CROP & VARIETY</div>
                <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px' }}>{selectedBatch.crop_name} ({selectedBatch.variety})</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Category: {selectedBatch.perishability_category}</div>
              </div>

              <div style={{ padding: '0.75rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px' }}>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>ORIGIN LOCATION</div>
                <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px' }}>{selectedBatch.farm_district}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>State: {selectedBatch.farm_state}</div>
              </div>

              <div style={{ padding: '0.75rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px' }}>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>STOCK AVAILABLE</div>
                <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '1.1rem', marginTop: '2px' }}>
                  {parseFloat(selectedBatch.total_available_kg || 0).toLocaleString()} kg
                </div>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.75rem' }}>
                  Reserved: {parseFloat(selectedBatch.total_reserved_kg || 0).toLocaleString()} kg
                </div>
              </div>

              <div style={{ padding: '0.75rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px' }}>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>QUALITY STATUS</div>
                <div style={{ marginTop: '4px' }}>
                  {getRiskBadge(selectedBatch.spoilage_risk_level)}
                </div>
                <div style={{ color: 'var(--text-faint)', fontSize: '0.75rem', marginTop: '4px' }}>
                  Days Remaining: {selectedBatch.days_until_quality_window_end}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button onClick={() => setSelectedBatch(null)} className="agri-btn primary" style={{ width: '100%' }}>
                Close Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
