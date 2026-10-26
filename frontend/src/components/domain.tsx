/** Small domain-specific display components shared across features. */
import {
  CircleAlert,
  CircleCheck,
  CircleDot,
  CircleX,
  Clock,
  FlaskConical,
  ShieldAlert,
  TriangleAlert,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge, type Tone } from '@/components/ui/Badge'
import { humanize } from '@/lib/format'

export const SIMULATED_LABEL = 'SIMULATED — NOT OFFICIAL APAAR VERIFICATION'

const findingStatus: Record<string, { tone: Tone; label: string }> = {
  open: { tone: 'warning', label: 'Open' },
  in_review: { tone: 'info', label: 'In review' },
  escalated: { tone: 'violet', label: 'Escalated' },
  resolved: { tone: 'success', label: 'Resolved' },
  dismissed: { tone: 'neutral', label: 'Dismissed' },
}

export function FindingStatusBadge({ status }: { status: string }) {
  const meta = findingStatus[status] ?? { tone: 'neutral' as Tone, label: humanize(status) }
  return <Badge tone={meta.tone}>{meta.label}</Badge>
}

const severity: Record<string, { tone: Tone; label: string; icon: ReactNode }> = {
  high: { tone: 'danger', label: 'High', icon: <CircleAlert className="size-3" aria-hidden /> },
  medium: { tone: 'warning', label: 'Medium', icon: <TriangleAlert className="size-3" aria-hidden /> },
  low: { tone: 'neutral', label: 'Low', icon: <CircleDot className="size-3" aria-hidden /> },
}

export function SeverityBadge({ value }: { value: string }) {
  const meta = severity[value] ?? { tone: 'neutral' as Tone, label: humanize(value), icon: null }
  return (
    <Badge tone={meta.tone} icon={meta.icon}>
      {meta.label}
    </Badge>
  )
}

const batchStatus: Record<string, { tone: Tone; label: string }> = {
  completed: { tone: 'success', label: 'Accepted' },
  partial: { tone: 'warning', label: 'Partially accepted' },
  rejected: { tone: 'danger', label: 'Rejected' },
  failed: { tone: 'danger', label: 'Failed' },
  processing: { tone: 'info', label: 'Processing' },
}

export function BatchStatusBadge({ status }: { status: string }) {
  const meta = batchStatus[status] ?? { tone: 'neutral' as Tone, label: humanize(status) }
  return <Badge tone={meta.tone}>{meta.label}</Badge>
}

const rowStatus: Record<string, { tone: Tone; label: string }> = {
  created: { tone: 'success', label: 'Created' },
  updated: { tone: 'info', label: 'Updated' },
  unchanged: { tone: 'neutral', label: 'Unchanged' },
  rejected: { tone: 'danger', label: 'Rejected' },
}

export function RowStatusBadge({ status }: { status: string }) {
  const meta = rowStatus[status] ?? { tone: 'neutral' as Tone, label: humanize(status) }
  return <Badge tone={meta.tone}>{meta.label}</Badge>
}

export function EnrolmentBadge({ status }: { status: string }) {
  const tone: Tone = status === 'ENROLLED' ? 'success' : status === 'WITHDRAWN' ? 'warning' : 'neutral'
  return <Badge tone={tone}>{humanize(status)}</Badge>
}

export function ConsentBadge({ status }: { status: string | null | undefined }) {
  if (status === 'granted') return <Badge tone="success">Consent granted</Badge>
  if (status === 'withdrawn') return <Badge tone="warning">Consent withdrawn</Badge>
  return <Badge tone="outline">Not recorded</Badge>
}

const outcomeMeta: Record<string, { tone: Tone; label: string; icon: ReactNode }> = {
  match: { tone: 'success', label: 'Match', icon: <CircleCheck className="size-3" aria-hidden /> },
  no_match: { tone: 'danger', label: 'No match', icon: <CircleX className="size-3" aria-hidden /> },
  pending: { tone: 'info', label: 'Pending', icon: <Clock className="size-3" aria-hidden /> },
  unavailable: {
    tone: 'warning',
    label: 'Provider unavailable',
    icon: <TriangleAlert className="size-3" aria-hidden />,
  },
  error: { tone: 'danger', label: 'Error', icon: <CircleAlert className="size-3" aria-hidden /> },
  format_invalid: {
    tone: 'danger',
    label: 'Invalid format',
    icon: <CircleX className="size-3" aria-hidden />,
  },
  valid: { tone: 'success', label: 'Valid', icon: <CircleCheck className="size-3" aria-hidden /> },
  changed_since_issue: {
    tone: 'warning',
    label: 'Changed since issue',
    icon: <TriangleAlert className="size-3" aria-hidden />,
  },
  superseded: { tone: 'warning', label: 'Superseded', icon: <Clock className="size-3" aria-hidden /> },
  not_found: { tone: 'neutral', label: 'Not found', icon: <CircleX className="size-3" aria-hidden /> },
}

export function OutcomeBadge({ outcome }: { outcome: string }) {
  const meta = outcomeMeta[outcome] ?? { tone: 'neutral' as Tone, label: humanize(outcome), icon: null }
  return (
    <Badge tone={meta.tone} icon={meta.icon}>
      {meta.label}
    </Badge>
  )
}

/** Unmissable label for anything produced by the mock identity provider. */
export function SimulatedTag({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-warning-ink uppercase"
      title={SIMULATED_LABEL}
    >
      <FlaskConical className="size-3" aria-hidden />
      {compact ? 'Simulated' : SIMULATED_LABEL}
    </span>
  )
}

export function MaskedId({ value }: { value: string }) {
  return (
    <span className="font-mono text-[13px] tracking-tight text-ink-2" title="Masked APAAR ID">
      {value}
    </span>
  )
}

export function ReviewSignalNote() {
  return (
    <p className="flex items-start gap-1.5 text-xs text-ink-3">
      <ShieldAlert className="mt-px size-3.5 shrink-0" aria-hidden />
      Findings are review signals produced by documented rules. They are not determinations of
      fraud or misconduct.
    </p>
  )
}

export function YesNo({ value }: { value: boolean }) {
  return <span className={value ? 'font-medium text-ink' : 'text-ink-3'}>{value ? 'Yes' : 'No'}</span>
}
