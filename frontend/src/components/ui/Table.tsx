import { cn } from '@/lib/cn'
import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'

export function TableWrap({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('overflow-x-auto', className)} {...rest} />
}

export function Table({ className, ...rest }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn('w-full border-collapse text-sm', className)} {...rest} />
}

export function THead({ className, ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn('border-b border-line bg-slate-50/70 text-left', className)}
      {...rest}
    />
  )
}

export function TH({ className, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn(
        'px-4 py-2.5 text-[11px] font-semibold tracking-wide text-ink-3 uppercase whitespace-nowrap',
        className,
      )}
      {...rest}
    />
  )
}

export function TR({ className, ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn('border-b border-line last:border-b-0 hover:bg-slate-50/60', className)}
      {...rest}
    />
  )
}

export function TD({ className, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('px-4 py-3 align-middle text-ink', className)} {...rest} />
}
