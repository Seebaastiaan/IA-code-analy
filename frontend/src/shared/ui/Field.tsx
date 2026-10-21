import type { InputHTMLAttributes, LabelHTMLAttributes, SelectHTMLAttributes } from 'react'
import { cn } from '@/shared/utils/cn'
import { inputClass } from './styles'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(inputClass, className)} {...props} />
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(inputClass, className)} {...props} />
}

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('block text-sm font-medium mb-1.5 text-slate-700 dark:text-slate-300', className)} {...props} />
}
