import { cn } from '@/lib/cn'
import { CircleAlert, CircleCheck, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

interface ToastItem {
  id: number
  tone: 'success' | 'error'
  message: string
}

interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (tone: ToastItem['tone'], message: string) => {
      const id = Date.now() + Math.random()
      setItems((current) => [...current.slice(-2), { id, tone, message }])
      window.setTimeout(() => dismiss(id), tone === 'error' ? 7000 : 4000)
    },
    [dismiss],
  )

  const api = useMemo<ToastApi>(
    () => ({ success: (m) => push('success', m), error: (m) => push('error', m) }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="no-print pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(380px,calc(100%-2rem))] flex-col gap-2"
        aria-live="polite"
      >
        {items.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg border bg-white px-4 py-3 text-sm shadow-lg',
              toast.tone === 'success' ? 'border-emerald-200' : 'border-red-200',
            )}
            role={toast.tone === 'error' ? 'alert' : 'status'}
          >
            {toast.tone === 'success' ? (
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-good" aria-hidden />
            ) : (
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-critical" aria-hidden />
            )}
            <p className="flex-1 text-ink">{toast.message}</p>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="text-ink-3 hover:text-ink"
              aria-label="Dismiss notification"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside ToastProvider')
  return context
}
