import { cn } from '@/lib/cn'
import { CircleAlert, CircleCheck, Info, LoaderCircle, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '@/lib/api'
import { Button } from './Button'

export function Spinner({ label = 'Loading', className }: { label?: string; className?: string }) {
  return (
    <span role="status" className={cn('inline-flex items-center gap-2 text-sm text-ink-3', className)}>
      <LoaderCircle className="size-4 animate-spin" aria-hidden />
      {label}
    </span>
  )
}

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center">
      <Spinner label={label} />
    </div>
  )
}

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: ReactNode
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && (
        <div className="mb-3 flex size-11 items-center justify-center rounded-full bg-slate-100 text-ink-3">
          {icon}
        </div>
      )}
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description && <p className="mt-1 max-w-md text-[13px] text-ink-3">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong'
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const requestId = error instanceof ApiError ? error.requestId : undefined
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center" role="alert">
      <div className="mb-3 flex size-11 items-center justify-center rounded-full bg-red-50 text-critical">
        <CircleAlert className="size-5" aria-hidden />
      </div>
      <p className="text-sm font-semibold text-ink">Couldn’t load this</p>
      <p className="mt-1 max-w-md text-[13px] text-ink-3">{errorMessage(error)}</p>
      {requestId && <p className="mt-1 font-mono text-[11px] text-ink-3">Request ID {requestId}</p>}
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

type AlertTone = 'info' | 'success' | 'warning' | 'danger'

const alertStyles: Record<AlertTone, { box: string; icon: ReactNode }> = {
  info: {
    box: 'border-brand-100 bg-brand-50 text-brand-800',
    icon: <Info className="size-4 text-brand-600" aria-hidden />,
  },
  success: {
    box: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    icon: <CircleCheck className="size-4 text-good" aria-hidden />,
  },
  warning: {
    box: 'border-amber-200 bg-amber-50 text-amber-900',
    icon: <TriangleAlert className="size-4 text-warning-ink" aria-hidden />,
  },
  danger: {
    box: 'border-red-200 bg-red-50 text-red-900',
    icon: <CircleAlert className="size-4 text-critical" aria-hidden />,
  },
}

interface AlertProps {
  tone?: AlertTone
  title?: ReactNode
  children?: ReactNode
  className?: string
  action?: ReactNode
}

export function Alert({ tone = 'info', title, children, className, action }: AlertProps) {
  const style = alertStyles[tone]
  return (
    <div
      className={cn('flex gap-3 rounded-lg border px-4 py-3 text-[13px]', style.box, className)}
      role={tone === 'danger' ? 'alert' : 'note'}
    >
      <div className="pt-0.5">{style.icon}</div>
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && 'mt-0.5', 'leading-relaxed')}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
