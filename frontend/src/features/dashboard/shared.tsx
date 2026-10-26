import { CircleAlert, CircleCheck, CircleHelp } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Form'
import { Meter } from '@/components/ui/Stat'
import { formatDateTime, formatNumber, formatPercent } from '@/lib/format'
import { useAppConfig } from '@/lib/queries'

export function YearSelect({ value, onChange }: { value: string | undefined; onChange: (v: string) => void }) {
  const config = useAppConfig()
  const years = config.data?.academic_years ?? []
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="year" className="text-[13px] font-medium whitespace-nowrap text-ink-2">
        Academic year
      </label>
      <Select
        id="year"
        className="h-9 w-32"
        value={value ?? years[0] ?? ''}
        onChange={(event) => onChange(event.target.value)}
      >
        {years.map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
      </Select>
    </div>
  )
}

export function IntakeStatusBadge({ status }: { status: string }) {
  if (status === 'exceeded') {
    return (
      <Badge tone="danger" icon={<CircleAlert className="size-3" aria-hidden />}>
        Over intake
      </Badge>
    )
  }
  if (status === 'within') {
    return (
      <Badge tone="success" icon={<CircleCheck className="size-3" aria-hidden />}>
        Within intake
      </Badge>
    )
  }
  if (status === 'not_configured') {
    return (
      <Badge tone="warning" icon={<CircleHelp className="size-3" aria-hidden />}>
        Intake not configured
      </Badge>
    )
  }
  return <Badge tone="neutral">No admissions</Badge>
}

export function UtilisationCell({
  used,
  limit,
  pct,
  status,
}: {
  used: number
  limit: number | null
  pct: number | null
  status: string
}) {
  return (
    <div className="min-w-36">
      <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
        <span className="font-semibold text-ink tabular">{formatPercent(pct, 0)}</span>
        <span className="text-ink-3 tabular">
          {formatNumber(used)} / {limit === null ? '—' : formatNumber(limit)}
        </span>
      </div>
      <Meter
        value={used}
        max={limit ?? used}
        label={`${used} of ${limit ?? 'unconfigured'} seats used`}
        status={status === 'exceeded' ? 'exceeded' : limit === null ? 'neutral' : 'within'}
      />
    </div>
  )
}

export function Definitions({ definitions, generatedAt }: { definitions: Record<string, string>; generatedAt: string }) {
  return (
    <details className="mt-6 rounded-xl border border-line bg-white px-5 py-3 text-[13px]">
      <summary className="cursor-pointer font-medium text-ink-2 hover:text-ink">
        How these figures are calculated
      </summary>
      <dl className="mt-3 grid gap-x-8 gap-y-2 sm:grid-cols-2">
        {Object.entries(definitions).map(([key, text]) => (
          <div key={key}>
            <dt className="text-xs font-semibold text-ink capitalize">{key.replace(/_/g, ' ')}</dt>
            <dd className="text-xs text-ink-3">{text}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-ink-3">
        Computed live from stored records at {formatDateTime(generatedAt)}. Intake figures and records are
        synthetic demo data.
      </p>
    </details>
  )
}
