import type { HTMLAttributes } from 'react'
import { cn } from '@/shared/utils/cn'
import { cardClass } from './styles'

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn(cardClass, className)} {...props} />
}
