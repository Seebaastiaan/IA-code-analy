import type { ScoreTone } from '@/shared/types/common'

export const TONE: Record<ScoreTone, { text: string; hex: string; bar: string; label: string; range: string }> = {
  good: { text: 'text-emerald-600 dark:text-emerald-400', hex: '#10b981', bar: 'bg-emerald-500', label: 'Saludable', range: '80 – 100' },
  warn: { text: 'text-amber-600 dark:text-amber-400', hex: '#f59e0b', bar: 'bg-amber-500', label: 'Mejorable', range: '60 – 79' },
  bad: { text: 'text-rose-600 dark:text-rose-400', hex: '#f43f5e', bar: 'bg-rose-500', label: 'Crítico', range: '0 – 59' },
}

export const tone = (v: number): ScoreTone => (v >= 80 ? 'good' : v >= 60 ? 'warn' : 'bad')

export const BRAND_HEX = '#5f45e4'
