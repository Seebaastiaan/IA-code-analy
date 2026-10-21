const rtf = new Intl.RelativeTimeFormat('es', { numeric: 'auto' })

/** "hace 2 h", "ayer", "hace 3 días" a partir de una fecha ISO. */
export function timeAgo(iso: string, now = Date.now()): string {
  const diff = (new Date(iso).getTime() - now) / 1000
  const abs = Math.abs(diff)
  if (abs < 60) return rtf.format(Math.round(diff), 'second')
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour')
  return rtf.format(Math.round(diff / 86400), 'day')
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat('es', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m ? `${m} min ${s} s` : `${s} s`
}
