import type { IconName } from '@/shared/ui/Icon'
import type { Category } from '@/shared/types/common'

interface CategoryMeta {
  label: string
  shortLabel: string
  icon: IconName
  hex: string
  tools: string
  /** Chip con borde (badge) */
  chip: string
  /** Fondo suave para contenedores de icono */
  soft: string
  /** Relleno de barras */
  bar: string
}

export const CAT: Record<Category, CategoryMeta> = {
  seg: {
    label: 'Seguridad',
    shortLabel: 'Seguridad',
    icon: 'shield',
    hex: '#d946ef',
    tools: 'Bandit · pip-audit',
    chip: 'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-600/20 dark:bg-fuchsia-500/10 dark:text-fuchsia-300 dark:ring-fuchsia-400/30',
    soft: 'bg-fuchsia-100 text-fuchsia-600 dark:bg-fuchsia-500/15 dark:text-fuchsia-300',
    bar: 'bg-fuchsia-500',
  },
  test: {
    label: 'Pruebas',
    shortLabel: 'Pruebas',
    icon: 'beaker',
    hex: '#0ea5e9',
    tools: 'pytest · coverage',
    chip: 'bg-sky-50 text-sky-700 ring-sky-600/20 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-400/30',
    soft: 'bg-sky-100 text-sky-600 dark:bg-sky-500/15 dark:text-sky-300',
    bar: 'bg-sky-500',
  },
  prac: {
    label: 'Buenas prácticas',
    shortLabel: 'Prácticas',
    icon: 'sparkle',
    hex: '#14b8a6',
    tools: 'Ruff · Radon',
    chip: 'bg-teal-50 text-teal-700 ring-teal-600/20 dark:bg-teal-500/10 dark:text-teal-300 dark:ring-teal-400/30',
    soft: 'bg-teal-100 text-teal-600 dark:bg-teal-500/15 dark:text-teal-300',
    bar: 'bg-teal-500',
  },
}
