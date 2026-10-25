import { create } from 'zustand'

export interface NexusStats {
  cpu: number
  memory: number
  disk: number
  processes: Array<{ name: string; cpu: number; mem: number }>
}

interface NexusStore {
  // Connection
  online: boolean
  netState: string
  setOnline: (v: boolean) => void
  setNetState: (v: string) => void

  // Live telemetry (pushed via socket / polled fallback)
  stats: NexusStats
  setStats: (s: NexusStats) => void

  // Notifications / reminders
  unreadCount: number
  setUnreadCount: (n: number) => void
  notices: any[]
  setNotices: (n: any[]) => void

  // Active view / UI
  activeView: string
  setActiveView: (v: string) => void
  voiceEnabled: boolean
  setVoiceEnabled: (v: boolean) => void
  busy: boolean
  setBusy: (v: boolean) => void

  // Files
  files: any[]
  setFiles: (f: any[]) => void
}

export const useNexusStore = create<NexusStore>((set) => ({
  online: true,
  netState: 'online',
  setOnline: (v) => set({ online: v }),
  setNetState: (v) => set({ netState: v }),

  stats: { cpu: 0, memory: 0, disk: 0, processes: [] },
  setStats: (s) => set({ stats: s }),

  unreadCount: 0,
  setUnreadCount: (n) => set({ unreadCount: n }),
  notices: [],
  setNotices: (n) => set({ notices: n }),

  activeView: 'core',
  setActiveView: (v) => set({ activeView: v }),
  voiceEnabled: true,
  setVoiceEnabled: (v) => set({ voiceEnabled: v }),
  busy: false,
  setBusy: (v) => set({ busy: v }),

  files: [],
  setFiles: (f) => set({ files: f }),
}))
