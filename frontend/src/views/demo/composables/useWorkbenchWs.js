import { onMounted, onUnmounted } from 'vue'
import { getToken } from '../../../api'

export function useWorkbenchWs({ onMessage, onTaskUpdate }) {
  let ws = null
  let reconnectTimer = null

  function connect() {
    const token = getToken()
    if (!token) return
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/api/v1/ws?token=${encodeURIComponent(token)}`)
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type === 'message' && onMessage) onMessage(data.data)
        if (data.type === 'task_update' && onTaskUpdate) onTaskUpdate(data.data)
      } catch {
        /* ignore */
      }
    }
    ws.onclose = () => {
      reconnectTimer = setTimeout(connect, 5000)
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) {
      ws.close()
      ws = null
    }
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return { connect, disconnect }
}
