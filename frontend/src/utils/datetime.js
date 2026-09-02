/**
 * Backend stores UTC. Naive ISO strings (no Z / offset) are treated as UTC,
 * then displayed in the browser's local timezone.
 */

export function parseServerTime(value) {
  if (value == null || value === '') return null
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  const s = String(value).trim()
  if (!s) return null
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(s)) {
    const d = new Date(s)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const normalized = s.includes('T') ? s : s.replace(' ', 'T')
  const d = new Date(`${normalized}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Local short datetime for inbox-style lists (MM-DD HH:mm). */
export function formatDateTimeShort(value, empty = '') {
  const d = parseServerTime(value)
  if (!d) return value == null || value === '' ? empty : String(value)
  return d.toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
