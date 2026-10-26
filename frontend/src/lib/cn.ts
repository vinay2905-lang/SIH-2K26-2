import clsx, { type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Join class names; later Tailwind utilities win over conflicting earlier ones (e.g. w-56 over w-full). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
