import { cn } from '@/lib/cn'
import type { ReactNode } from 'react'

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'violet' | 'outline'

const tones: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  info: 'bg-brand-50 text-brand-700 ring-brand-100',
  success: 'bg-emerald-50 text-good-ink ring-emerald-200',
  warning: 'bg-amber-50 text-warning-ink ring-amber-200',
  danger: 'bg-red-50 text-critical-ink ring-red-200',
  violet: 'bg-violet-50 text-violet-700 ring-violet-200',
  outline: 'bg-white text-ink-2 ring-line-strong',
}

interface BadgeProps {
  tone?: Tone
  icon?: ReactNode
  children: ReactNode
  className?: string
  title?: string
}

export function Badge({ tone = 'neutral', icon, children, className, title }: BadgeProps) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap',
        tones[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}
