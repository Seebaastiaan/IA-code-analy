import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Une clases y resuelve conflictos de Tailwind (p. ej. `w-full` + `w-auto` → `w-auto`). */
export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))
