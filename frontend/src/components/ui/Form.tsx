import { cn } from '@/lib/cn'
import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'

const control =
  'block w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink shadow-xs placeholder:text-ink-3 focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none disabled:bg-slate-50 disabled:text-ink-3 aria-[invalid=true]:border-critical aria-[invalid=true]:focus:ring-red-100'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(control, 'h-10', className)} {...rest} />
  },
)

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select ref={ref} className={cn(control, 'h-10 pr-8', className)} {...rest}>
        {children}
      </select>
    )
  },
)

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={cn(control, 'min-h-20 py-2', className)} {...rest} />
  },
)

interface FieldProps {
  label: ReactNode
  htmlFor: string
  hint?: ReactNode
  error?: string
  required?: boolean
  children: ReactNode
  className?: string
}

export function Field({ label, htmlFor, hint, error, required, children, className }: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-ink">
        {label}
        {required && (
          <span className="ml-0.5 text-critical" aria-hidden>
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="text-xs text-critical-ink" role="alert">
          {error}
        </p>
      ) : (
        hint && <p className="text-xs text-ink-3">{hint}</p>
      )}
    </div>
  )
}

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
  label: ReactNode
  description?: ReactNode
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, description, id, className, ...rest },
  ref,
) {
  return (
    <label htmlFor={id} className={cn('flex cursor-pointer items-start gap-2.5', className)}>
      <input
        ref={ref}
        id={id}
        type="checkbox"
        className="mt-0.5 size-4 rounded border-line-strong text-brand-600 accent-brand-600"
        {...rest}
      />
      <span>
        <span className="block text-sm text-ink">{label}</span>
        {description && <span className="block text-xs text-ink-3">{description}</span>}
      </span>
    </label>
  )
})
