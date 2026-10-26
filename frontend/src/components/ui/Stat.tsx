import { cn } from '@/lib/cn'
import type { ReactNode } from 'react'

interface StatTileProps {
  label: string
  value: ReactNode
  detail?: ReactNode
  icon?: ReactNode
  tone?: 'default' | 'attention'
}

/** KPI tile: sentence-case label, proportional-figure value, optional secondary line. */
export function StatTile({ label, value, detail, icon, tone = 'default' }: StatTileProps) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-[0_1px_2px_rgba(15,27,45,0.04)]">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[13px] font-medium text-ink-2">{label}</p>
        {icon && (
          <span
            className={cn(
              'flex size-7 items-center justify-center rounded-lg',
              tone === 'attention' ? 'bg-red-50 text-critical' : 'bg-brand-50 text-brand-600',
            )}
            aria-hidden
          >
            {icon}
          </span>
        )}
      </div>
      <p className="mt-2 text-[26px] leading-none font-semibold tracking-tight text-ink">{value}</p>
      {detail && <p className="mt-2 text-xs text-ink-3">{detail}</p>}
    </div>
  )
}

interface MeterProps {
  value: number
  max: number
  label: string
  /** Over the limit: the fill switches to the critical status colour (with a text label). */
  status?: 'within' | 'exceeded' | 'neutral'
  className?: string
}

/** Single ratio against a limit. The track is a lighter step of the fill's own hue. */
export function Meter({ value, max, label, status = 'within', className }: MeterProps) {
  const ratio = max > 0 ? value / max : 0
  const width = `${Math.min(100, Math.round(ratio * 100))}%`
  const exceeded = status === 'exceeded'
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className={cn(
        'h-2 w-full overflow-hidden rounded-full',
        exceeded ? 'bg-red-100' : status === 'neutral' ? 'bg-slate-100' : 'bg-brand-100',
        className,
      )}
    >
      <div
        className={cn(
          'h-full rounded-full',
          exceeded ? 'bg-critical' : status === 'neutral' ? 'bg-slate-400' : 'bg-series-1',
        )}
        style={{ width }}
      />
    </div>
  )
}
