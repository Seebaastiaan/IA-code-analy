import type { ReactNode } from 'react'
import { CAT } from '@/shared/constants/categories'
import { SEV } from '@/shared/constants/severities'
import type { Category, RepoStatus, Severity } from '@/shared/types/common'
import { cn } from '@/shared/utils/cn'
import { Icon } from './Icon'
import { Spinner } from './Spinner'
import { CHIP_TONES, chipBase } from './styles'

export function Chip({ tone = 'neutral', className, children }: { tone?: keyof typeof CHIP_TONES; className?: string; children: ReactNode }) {
  return <span className={cn(chipBase, CHIP_TONES[tone], className)}>{children}</span>
}

export function SeverityBadge({ sev }: { sev: Severity }) {
  return (
    <span className={cn(chipBase, SEV[sev].chip)}>
      <span className={cn('w-1.5 h-1.5 rounded-full', SEV[sev].dot)} />
      {SEV[sev].label}
    </span>
  )
}

export function CategoryChip({ cat }: { cat: Category }) {
  return (
    <span className={cn(chipBase, CAT[cat].chip, 'shrink-0 whitespace-nowrap')}>
      <Icon name={CAT[cat].icon} className="w-3 h-3" />
      {CAT[cat].label}
    </span>
  )
}

export function StatusChip({ status }: { status: RepoStatus }) {
  if (status === 'listo')
    return (
      <Chip tone="success">
        <Icon name="check" className="w-3 h-3" />
        Listo
      </Chip>
    )
  if (status === 'analizando')
    return (
      <Chip tone="brand">
        <Spinner className="w-3 h-3" />
        Analizando
      </Chip>
    )
  return (
    <Chip tone="danger">
      <Icon name="alert" className="w-3 h-3" />
      Error
    </Chip>
  )
}
