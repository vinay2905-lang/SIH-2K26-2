import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
  width?: 'md' | 'lg'
}

/** Native <dialog>: focus trapping, Escape-to-close and backdrop come from the browser. */
export function Dialog({ open, onClose, title, description, children, footer, width = 'md' }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal?.()
    if (!open && dialog.open) dialog.close?.()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      className={`m-auto w-[calc(100%-2rem)] ${width === 'lg' ? 'max-w-2xl' : 'max-w-lg'} rounded-xl border border-line bg-white p-0 text-ink shadow-2xl backdrop:bg-slate-900/40 backdrop:backdrop-blur-[1px]`}
    >
      {open && (
        <div>
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div>
              <h2 className="text-base font-semibold">{title}</h2>
              {description && <p className="mt-0.5 text-[13px] text-ink-3">{description}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-1 text-ink-3 hover:bg-slate-100 hover:text-ink"
              aria-label="Close dialog"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
          <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
          {footer && (
            <div className="flex justify-end gap-2 border-t border-line bg-slate-50/60 px-5 py-3">
              {footer}
            </div>
          )}
        </div>
      )}
    </dialog>
  )
}
