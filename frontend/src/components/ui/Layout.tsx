import { cn } from '@/lib/cn'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { formatNumber } from '@/lib/format'
import { Button } from './Button'

interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  back?: { to: string; label: string }
  meta?: ReactNode
}

export function PageHeader({ title, description, actions, back, meta }: PageHeaderProps) {
  return (
    <header className="mb-6">
      {back && (
        <Link
          to={back.to}
          className="no-print mb-2 inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-brand-600"
        >
          <ChevronLeft className="size-4" aria-hidden />
          {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] leading-tight font-semibold tracking-tight text-ink">{title}</h1>
          {description && <p className="mt-1 max-w-3xl text-sm text-ink-2">{description}</p>}
          {meta && <div className="mt-2 flex flex-wrap items-center gap-2">{meta}</div>}
        </div>
        {actions && <div className="no-print flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
  className?: string
}

export function Pagination({ page, pageSize, total, onPage, className }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)
  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-[13px] text-ink-3',
        className,
      )}
    >
      <span className="tabular">
        {formatNumber(from)}–{formatNumber(to)} of {formatNumber(total)}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" aria-hidden />
        </Button>
        <span className="tabular px-2">
          Page {page} of {pages}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          aria-label="Next page"
        >
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>
    </div>
  )
}

interface TabsProps<T extends string> {
  value: T
  onChange: (value: T) => void
  items: { value: T; label: ReactNode; count?: number }[]
  label: string
  className?: string
}

export function SegmentedTabs<T extends string>({
  value,
  onChange,
  items,
  label,
  className,
}: TabsProps<T>) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn('inline-flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1', className)}
    >
      {items.map((item) => {
        const selected = item.value === value
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(item.value)}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors',
              selected ? 'bg-white text-ink shadow-xs' : 'text-ink-2 hover:text-ink',
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span
                className={cn(
                  'tabular rounded px-1.5 text-[11px]',
                  selected ? 'bg-brand-50 text-brand-700' : 'bg-slate-200/70 text-ink-2',
                )}
              >
                {formatNumber(item.count)}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export function DescriptionList({
  items,
  className,
}: {
  items: { label: ReactNode; value: ReactNode }[]
  className?: string
}) {
  return (
    <dl className={cn('grid gap-x-6 gap-y-3 sm:grid-cols-2', className)}>
      {items.map((item, index) => (
        <div key={index} className="min-w-0">
          <dt className="text-xs font-medium text-ink-3">{item.label}</dt>
          <dd className="mt-0.5 text-sm break-words text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}
