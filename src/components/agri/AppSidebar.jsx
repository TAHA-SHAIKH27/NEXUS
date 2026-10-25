import React, { useState } from 'react';
import {
  LayoutDashboard,
  Brain,
  Boxes,
  TrendingUp,
  Truck,
  ShieldAlert,
  FileCheck2,
  Database,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sprout,
  Terminal,
  Smartphone,
  FolderArchive,
  Layers
} from 'lucide-react';

export default function AppSidebar({ activeTab, setActiveTab, unreadCount = 0, riskCount = 0 }) {
  const [collapsed, setCollapsed] = useState(false);

  const mainNav = [
    { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard },
    { id: 'ai-workspace', label: 'AI Intelligence Workspace', icon: Brain, badge: 'NEXUS-AI' },
    { id: 'inventory', label: 'Inventory Intelligence', icon: Boxes },
    { id: 'markets', label: 'Market Intelligence', icon: TrendingUp },
    { id: 'logistics', label: 'Logistics Intelligence', icon: Truck },
    { id: 'risk-centre', label: 'Risk Centre', icon: ShieldAlert, badge: riskCount > 0 ? `${riskCount}` : null, badgeColor: 'rose' },
    { id: 'decisions', label: 'Decisions & Reports', icon: FileCheck2 },
    { id: 'datasources', label: 'Data Sources & Zetaris', icon: Database },
  ];

  const toolsNav = [
    { id: 'code', label: 'Code Core Studio', icon: Terminal },
    { id: 'phone', label: 'Mobile Device Hub', icon: Smartphone },
    { id: 'files', label: 'Media & File Archives', icon: FolderArchive },
  ];

  return (
    <aside style={{
      width: collapsed ? '72px' : '260px',
      background: 'rgba(7, 12, 22, 0.95)',
      backdropFilter: 'blur(16px)',
      borderRight: '1px solid var(--border-subtle)',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      transition: 'width 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      zIndex: 40,
      userSelect: 'none',
    }}>
      {/* Brand Header */}
      <div>
        <div style={{
          padding: '1.25rem 1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', overflow: 'hidden' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #0284c7, #10b981)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              boxShadow: '0 0 15px rgba(16, 185, 129, 0.35)',
              flexShrink: 0
            }}>
              <Sprout size={22} />
            </div>
            {!collapsed && (
              <div>
                <div style={{
                  fontFamily: 'var(--font-heading)',
                  fontWeight: 800,
                  fontSize: '1.05rem',
                  letterSpacing: '0.08em',
                  background: 'linear-gradient(to right, #38bdf8, #34d399)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  lineHeight: 1.1
                }}>
                  NEXUS
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  FPO Agri-Platform
                </div>
              </div>
            )}
          </div>
          
          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: 'none',
              borderRadius: '6px',
              padding: '4px',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: collapsed ? 'none' : 'flex'
            }}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            <ChevronLeft size={16} />
          </button>
        </div>

        {/* Main Nav Items */}
        <div style={{ padding: '0.75rem 0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {!collapsed && (
            <div style={{
              padding: '0.35rem 0.65rem',
              fontSize: '0.68rem',
              color: 'var(--text-faint)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              fontWeight: 700
            }}>
              Core Intelligence
            </div>
          )}

          {mainNav.map(item => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: collapsed ? '0.7rem 0' : '0.65rem 0.85rem',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  borderRadius: '8px',
                  border: 'none',
                  cursor: 'pointer',
                  background: active ? 'linear-gradient(90deg, rgba(14, 165, 233, 0.18), rgba(16, 185, 129, 0.08))' : 'transparent',
                  color: active ? '#38bdf8' : 'var(--text-muted)',
                  borderLeft: active ? '3px solid #38bdf8' : '3px solid transparent',
                  transition: 'all 0.15s ease',
                  position: 'relative',
                  textAlign: 'left'
                }}
                title={collapsed ? item.label : undefined}
              >
                <Icon size={19} color={active ? '#38bdf8' : 'currentColor'} />
                {!collapsed && (
                  <span style={{ fontSize: '0.85rem', fontWeight: active ? 600 : 400, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.label}
                  </span>
                )}
                {!collapsed && item.badge && (
                  <span className={`agri-badge ${item.badgeColor || 'cyan'}`} style={{ fontSize: '0.65rem', padding: '0.1rem 0.45rem' }}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}

          {/* Tools & Utilities */}
          {!collapsed && (
            <div style={{
              padding: '0.75rem 0.65rem 0.35rem',
              fontSize: '0.68rem',
              color: 'var(--text-faint)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              fontWeight: 700
            }}>
              System Utilities
            </div>
          )}

          {toolsNav.map(item => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: collapsed ? '0.65rem 0' : '0.55rem 0.85rem',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  borderRadius: '8px',
                  border: 'none',
                  cursor: 'pointer',
                  background: active ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                  color: active ? '#fff' : 'var(--text-faint)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
                title={collapsed ? item.label : undefined}
              >
                <Icon size={17} />
                {!collapsed && (
                  <span style={{ fontSize: '0.8rem', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.label}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Profile / Settings */}
      <div style={{
        padding: '0.75rem',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)'
      }}>
        <button
          onClick={() => setActiveTab('settings')}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: collapsed ? '0.65rem 0' : '0.65rem 0.85rem',
            justifyContent: collapsed ? 'center' : 'flex-start',
            borderRadius: '8px',
            border: 'none',
            cursor: 'pointer',
            background: activeTab === 'settings' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
            color: activeTab === 'settings' ? '#38bdf8' : 'var(--text-muted)'
          }}
          title={collapsed ? 'Settings' : undefined}
        >
          <Settings size={18} />
          {!collapsed && <span style={{ fontSize: '0.85rem' }}>Platform Settings</span>}
        </button>

        {!collapsed && (
          <div style={{
            marginTop: '0.65rem',
            padding: '0.65rem',
            background: 'rgba(15, 25, 45, 0.6)',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.72rem',
            color: 'var(--text-faint)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.2rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#34d399' }}>
              <span className="status-beacon online" />
              <span style={{ fontWeight: 600 }}>NEXUS_FPO Gateway</span>
            </div>
            <div>Postgres: 526K Records</div>
            <div>Zetaris: Active (Port 8888)</div>
          </div>
        )}
      </div>
    </aside>
  );
}
