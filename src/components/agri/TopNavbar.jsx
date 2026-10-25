import React from 'react';
import {
  Search,
  Bell,
  Volume2,
  VolumeX,
  RefreshCw,
  Database,
  Wifi,
  Sparkles
} from 'lucide-react';

export default function TopNavbar({
  activeTab,
  onRefresh,
  refreshing = false,
  voiceEnabled,
  onToggleVoice,
  unreadCount = 0,
  onOpenNotifications,
  searchQuery,
  onSearchChange,
  isSpeaking = false
}) {
  const titles = {
    'overview': 'Overview Dashboard',
    'ai-workspace': 'AI Intelligence Workspace',
    'inventory': 'Inventory Intelligence',
    'markets': 'Market Intelligence & Mandi Trends',
    'logistics': 'Logistics & Warehouse Optimization',
    'risk-centre': 'Risk Centre & Spoilage Prevention',
    'decisions': 'Strategic Decisions & Reports',
    'datasources': 'Data Sources & Zetaris Connectivity',
    'settings': 'Platform Configuration',
    'code': 'Code Core Developer Console',
    'phone': 'Mobile Device Hub',
    'files': 'Media & Document Archives'
  };

  return (
    <header style={{
      height: '64px',
      background: 'rgba(11, 19, 34, 0.8)',
      backdropFilter: 'blur(12px)',
      borderBottom: '1px solid var(--border-subtle)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 1.5rem',
      gap: '1rem',
      zIndex: 30
    }}>
      {/* Title & Breadcrumb */}
      <div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Agricultural Command / <span style={{ color: 'var(--accent-cyan)' }}>{titles[activeTab] || 'Platform'}</span>
        </div>
        <h1 style={{
          fontSize: '1.2rem',
          fontWeight: 700,
          color: '#fff',
          margin: 0,
          fontFamily: 'var(--font-heading)'
        }}>
          {titles[activeTab] || 'NEXUS Agri-Intelligence'}
        </h1>
      </div>

      {/* Center Search Input */}
      <div style={{ flex: '1', maxWidth: '420px', position: 'relative' }}>
        <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }} />
        <input
          type="text"
          value={searchQuery || ''}
          onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
          placeholder="Search batches, crops, APMC markets, warehouses..."
          className="agri-input"
          style={{ width: '100%', paddingLeft: '36px', height: '36px', fontSize: '0.825rem' }}
        />
      </div>

      {/* Right Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {/* Zetaris RO Pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.35rem 0.65rem',
          background: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          borderRadius: '9999px',
          fontSize: '0.75rem',
          color: '#34d399',
          fontWeight: 500
        }}>
          <span className="status-beacon online" />
          <span>Zetaris: NEXUS_FPO</span>
        </div>

        {/* Voice Toggle */}
        <button
          onClick={onToggleVoice}
          style={{
            background: voiceEnabled ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.05)',
            border: `1px solid ${voiceEnabled ? 'rgba(56, 189, 248, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
            borderRadius: '8px',
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: voiceEnabled ? '#38bdf8' : 'var(--text-faint)',
            transition: 'all 0.15s ease'
          }}
          title={voiceEnabled ? 'Voice Synthesis Active' : 'Voice Synthesis Muted'}
        >
          {voiceEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
        </button>

        {/* Refresh Data */}
        <button
          onClick={onRefresh}
          disabled={refreshing}
          style={{
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '8px',
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: refreshing ? 'not-allowed' : 'pointer',
            color: 'var(--text-muted)',
            transition: 'all 0.15s ease'
          }}
          title="Refresh Data & Calculations"
        >
          <RefreshCw size={17} className={refreshing ? 'animate-spin' : ''} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
        </button>

        {/* Notification Bell */}
        <button
          onClick={onOpenNotifications}
          style={{
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '8px',
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: unreadCount > 0 ? '#fbbf24' : 'var(--text-muted)',
            position: 'relative'
          }}
          title="Notification Center"
        >
          <Bell size={18} />
          {unreadCount > 0 && (
            <span style={{
              position: 'absolute',
              top: '-4px',
              right: '-4px',
              background: '#f43f5e',
              color: '#fff',
              fontSize: '0.65rem',
              fontWeight: 700,
              width: '18px',
              height: '18px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px solid #0b1322'
            }}>
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
