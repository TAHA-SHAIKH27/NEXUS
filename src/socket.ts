import { io, type Socket } from 'socket.io-client'
import { useNexusStore } from './store/nexusStore'

let socket: Socket | null = null

export function connectNexusSocket(url = 'http://127.0.0.1:8000') {
  if (socket) return socket

  socket = io(url, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
  })

  socket.on('connect', () => {
    useNexusStore.getState().setOnline(true)
    useNexusStore.getState().setNetState('online')
  })

  socket.on('disconnect', () => {
    useNexusStore.getState().setOnline(false)
    useNexusStore.getState().setNetState('offline')
  })

  // Live telemetry push from backend
  socket.on('stats', (data: any) => {
    useNexusStore.getState().setStats({
      cpu: data.cpu ?? 0,
      memory: data.memory ?? 0,
      disk: data.disk ?? 0,
      processes: data.processes ?? [],
    })
  })

  // Notification push
  socket.on('notification', (data: any) => {
    const store = useNexusStore.getState()
    store.setNotices([...store.notices, data])
    store.setUnreadCount(store.unreadCount + 1)
  })

  // Reminder push
  socket.on('reminder', (data: any) => {
    useNexusStore.getState().setUnreadCount(
      useNexusStore.getState().unreadCount + 1
    )
  })

  return socket
}

export function getNexusSocket() {
  return socket
}

export function disconnectNexusSocket() {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}
