import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDate, formatNumber } from '@/lib/format'
import type { CategoryCount } from '@/types/api'

/* Chart tokens: validated categorical slots 1-2 (see docs/architecture.md, dataviz notes). */
const SERIES_1 = '#2a78d6'
const SERIES_2 = '#eb6834'
const SURFACE = '#ffffff'
const GRID = '#e8eaee'
const AXIS = '#c9ced6'
const MUTED = '#6b778a'

/**
 * Single-series horizontal bars (one hue for every bar). Value at the bar tip; each bar is
 * its own hover/focus target with a tooltip.
 */
export function CategoryBars({ data, emptyLabel }: { data: CategoryCount[]; emptyLabel: string }) {
  const [active, setActive] = useState<string | null>(null)
  const max = Math.max(1, ...data.map((d) => d.count))
  const total = data.reduce((sum, d) => sum + d.count, 0)
  if (total === 0) {
    return <p className="py-6 text-center text-[13px] text-ink-3">{emptyLabel}</p>
  }
  return (
    <ul className="space-y-3" aria-label="Open findings by category">
      {data.map((item) => (
        <li key={item.category}>
          <div
            className="group relative"
            tabIndex={0}
            onMouseEnter={() => setActive(item.category)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(item.category)}
            onBlur={() => setActive(null)}
            aria-label={`${item.label}: ${item.count} open`}
          >
            <div className="mb-1 flex items-baseline justify-between gap-2 text-[13px]">
              <span className="text-ink-2">{item.label}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative h-3 flex-1">
                <div
                  className="h-3 rounded-r-[4px] transition-opacity"
                  style={{
                    width: item.count ? `${Math.max(2, (item.count / max) * 100)}%` : 0,
                    background: SERIES_1,
                    opacity: active && active !== item.category ? 0.55 : 1,
                  }}
                />
              </div>
              <span className="w-8 text-right text-[13px] font-semibold text-ink tabular">
                {formatNumber(item.count)}
              </span>
            </div>
            {active === item.category && (
              <div
                role="tooltip"
                className="pointer-events-none absolute -top-9 left-0 z-10 rounded-md border border-line bg-white px-2.5 py-1.5 text-xs shadow-md"
              >
                <span className="font-semibold text-ink">{formatNumber(item.count)}</span>{' '}
                <span className="text-ink-3">open · {item.label}</span>
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

interface QualityPoint {
  date: string
  accepted: number
  rejected: number
}

function QualityTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: { dataKey?: string | number; value?: number }[]
  label?: string | number
}) {
  if (!active || !payload?.length) return null
  const value = (key: string) => payload.find((p) => p.dataKey === key)?.value ?? 0
  return (
    <div className="rounded-md border border-line bg-white px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-ink-2">{formatDate(String(label))}</p>
      {[
        ['accepted', 'Accepted rows', SERIES_1],
        ['rejected', 'Rejected rows', SERIES_2],
      ].map(([key, name, color]) => (
        <p key={key} className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-3 rounded" style={{ background: color }} aria-hidden />
          <span className="font-semibold text-ink tabular">{formatNumber(value(key))}</span>
          <span className="text-ink-3">{name}</span>
        </p>
      ))}
    </div>
  )
}

/** Accepted vs rejected rows per day: stacked columns, 2 validated categorical slots. */
export function UploadQualityChart({ data }: { data: QualityPoint[] }) {
  if (!data.length) {
    return <p className="py-10 text-center text-[13px] text-ink-3">No uploads in the last 30 days.</p>
  }
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-4 text-xs text-ink-2" aria-hidden>
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-sm" style={{ background: SERIES_1 }} />
          Accepted rows
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-sm" style={{ background: SERIES_2 }} />
          Rejected rows
        </span>
      </div>
      <div className="h-56" role="img" aria-label="Accepted and rejected upload rows per day, last 30 days">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="35%">
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis
              dataKey="date"
              tickFormatter={(v: string) => formatDate(v).replace(/ \d{4}$/, '')}
              tickLine={false}
              axisLine={{ stroke: AXIS }}
              tick={{ fill: MUTED, fontSize: 11 }}
            />
            <YAxis
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              width={40}
              tick={{ fill: MUTED, fontSize: 11 }}
              tickFormatter={(v: number) => (v >= 1000 ? `${Math.round(v / 100) / 10}K` : String(v))}
            />
            <Tooltip content={<QualityTooltip />} cursor={{ fill: 'rgba(15,27,45,0.04)' }} />
            <Bar dataKey="accepted" stackId="rows" fill={SERIES_1} maxBarSize={24} stroke={SURFACE} strokeWidth={2} />
            <Bar
              dataKey="rejected"
              stackId="rows"
              fill={SERIES_2}
              maxBarSize={24}
              radius={[4, 4, 0, 0]}
              stroke={SURFACE}
              strokeWidth={2}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-[13px]">
        <summary className="cursor-pointer text-ink-3 hover:text-ink">Show data table</summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead>
            <tr className="text-ink-3">
              <th className="py-1 font-medium">Date</th>
              <th className="py-1 text-right font-medium">Accepted</th>
              <th className="py-1 text-right font-medium">Rejected</th>
            </tr>
          </thead>
          <tbody>
            {data.map((point) => (
              <tr key={point.date} className="border-t border-line">
                <td className="py-1">{formatDate(point.date)}</td>
                <td className="py-1 text-right tabular">{formatNumber(point.accepted)}</td>
                <td className="py-1 text-right tabular">{formatNumber(point.rejected)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
