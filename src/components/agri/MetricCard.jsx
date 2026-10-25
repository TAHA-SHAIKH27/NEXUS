import React from 'react';
import { motion } from 'framer-motion';

export default function MetricCard({ title, value, subtitle, icon: Icon, trend, glowColor = 'cyan', delay = 0 }) {
  const glowMap = {
    cyan: 'rgba(56, 189, 248, 0.18)',
    emerald: 'rgba(16, 185, 129, 0.18)',
    amber: 'rgba(245, 158, 11, 0.18)',
    rose: 'rgba(244, 63, 94, 0.18)',
    purple: 'rgba(168, 85, 247, 0.18)',
  };

  const accentColorMap = {
    cyan: '#38bdf8',
    emerald: '#10b981',
    amber: '#f59e0b',
    rose: '#f43f5e',
    purple: '#a855f7',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      className="agri-card kpi-card"
      style={{ '--kpi-glow': glowMap[glowColor] || glowMap.cyan }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
          {title}
        </span>
        {Icon && (
          <div style={{
            padding: '8px',
            borderRadius: '8px',
            background: `rgba(255, 255, 255, 0.04)`,
            border: `1px solid rgba(255, 255, 255, 0.08)`,
            color: accentColorMap[glowColor] || '#38bdf8'
          }}>
            <Icon size={18} />
          </div>
        )}
      </div>

      <div className="kpi-value" style={{ color: '#fff' }}>
        {value}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.775rem' }}>
        <span style={{ color: 'var(--text-faint)' }}>{subtitle}</span>
        {trend && (
          <span className={`agri-badge ${trend.isPositive ? 'emerald' : trend.isWarning ? 'amber' : 'rose'}`}>
            {trend.text}
          </span>
        )}
      </div>
    </motion.div>
  );
}
