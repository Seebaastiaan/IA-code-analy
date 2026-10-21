const WS_URL = (import.meta.env.VITE_WS_URL ?? '').replace(/\/$/, '')

function wsBase() {
  if (WS_URL) return WS_URL
  const { protocol, host } = window.location
  return `${protocol === 'https:' ? 'wss' : 'ws'}://${host}`
}

interface SocketOptions<M> {
  onMessage: (msg: M) => void
  onClose?: (ev: CloseEvent) => void
  /** Reintentos de reconexión ante cierres inesperados */
  retries?: number
}

/** WebSocket JSON con reconexión exponencial. Devuelve una función para cerrarlo. */
export function openSocket<M>(path: string, { onMessage, onClose, retries = 5 }: SocketOptions<M>) {
  let ws: WebSocket
  let attempt = 0
  let closedByUser = false

  const connect = () => {
    ws = new WebSocket(wsBase() + path)
    ws.onopen = () => { attempt = 0 }
    ws.onmessage = (ev) => {
      try { onMessage(JSON.parse(ev.data) as M) } catch { /* mensaje no JSON: se ignora */ }
    }
    ws.onclose = (ev) => {
      if (!closedByUser && !ev.wasClean && attempt < retries) {
        setTimeout(connect, 500 * 2 ** attempt++)
        return
      }
      onClose?.(ev)
    }
  }
  connect()

  return {
    send: (data: unknown) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(data)),
    close: () => { closedByUser = true; ws.close() },
  }
}
