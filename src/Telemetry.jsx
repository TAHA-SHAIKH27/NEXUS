import React, { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNexusStore } from '../store/nexusStore'
import Gauge from './Gauge'

async function fetchStats() {
  const res = await fetch('/api/stats')
  if (!res.ok) throw new Error('stats fetch failed')
  return res.json()
}

export default function Telemetry() {
  const setStats = useNexusStore((s) => s.setStats)
  const stats = useNexusStore((s) => s.stats)

  const { data, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    refetchInterval: 4000,
  })

  useEffect(() => {
    if (data) setStats(data)
  }, [data, setStats])

  if (isLoading) {
    return (
      <div className="hud-telemetry panel">
        <p className="panel-label"><span>System Telemetry</span></p>
        <div className="gauge-row">
          <Gauge label="CPU" value={0} />
          <Gauge label="Memory" value={0} />
          <Gauge label="Disk" value={0} />
        </div>
      </div>
    )
  }

  return (
    <div className="hud-telemetry panel">
      <p className="panel-label"><span>System Telemetry</span></p>
      <div className="gauge-row">
        <Gauge label="CPU" value={stats.cpu} />
        <Gauge label="Memory" value={stats.memory} />
        <Gauge label="Disk" value={stats.disk} />
      </div>
      <div className="mt-2 flex gap-2 text-xs font-mono text-text-faint">
        <span>Processes: {stats.processes.length}</span>
      </div>
    </div>
  )
}
