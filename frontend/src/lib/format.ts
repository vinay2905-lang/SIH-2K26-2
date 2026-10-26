const numberFormat = new Intl.NumberFormat('en-IN')
const dateFormat = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
const dateTimeFormat = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : numberFormat.format(value)
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : `${value.toFixed(digits)}%`
}

/** Dates without a time ("2026-08-01") are calendar dates: format them without timezone shifts. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const plain = /^\d{4}-\d{2}-\d{2}$/.test(value)
  const date = plain ? new Date(`${value}T00:00:00`) : new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateTimeFormat.format(date)
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return '—'
  const diff = Date.now() - new Date(value).getTime()
  const minutes = Math.round(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 45) return `${days} d ago`
  return formatDate(value)
}

export const ROLE_LABELS: Record<string, string> = {
  institution_operator: 'Institution data operator',
  institution_admin: 'Institution administrator',
  central_reviewer: 'Central reviewer',
  authorized_verifier: 'Authorised verifier',
  system_admin: 'System administrator',
}

export function roleLabel(role: string | null | undefined): string {
  return role ? (ROLE_LABELS[role] ?? role) : '—'
}

export function humanize(value: string | null | undefined): string {
  if (!value) return '—'
  const text = value.replace(/[_.]/g, ' ').toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}
