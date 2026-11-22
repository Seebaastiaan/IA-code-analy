import { describe, expect, it } from 'vitest'
import { toToml } from '@/features/settings/utils/toToml'
import { tone } from '@/shared/constants/tones'
import { calcScore, f1, usesNeg } from '@/shared/utils/score'

describe('calcScore', () => {
  it('pondera con los pesos por defecto (50/30/20)', () => {
    expect(f1(calcScore({ seg: 50, test: 30, prac: 20 }, { seg: 68, test: 85, prac: 73 }))).toBe('74.1')
  })

  it('normaliza si los pesos no suman 100', () => {
    expect(calcScore({ seg: 1, test: 1, prac: 0 }, { seg: 60, test: 80, prac: 0 })).toBe(70)
  })

  it('no divide entre cero si todos los pesos son 0', () => {
    expect(calcScore({ seg: 0, test: 0, prac: 0 }, { seg: 60, test: 80, prac: 90 })).toBe(0)
  })
})

describe('reglas de negocio en el score (neg)', () => {
  const cats = { seg: 100, test: 100, prac: 100 }

  it('con peso 0 o sin nota no entra, ni su peso al total', () => {
    expect(calcScore({ seg: 50, test: 30, prac: 20, neg: 0 }, { ...cats, neg: 0 })).toBe(100)
    expect(calcScore({ seg: 50, test: 30, prac: 20, neg: 20 }, { ...cats, neg: null })).toBe(100)
    expect(usesNeg({ seg: 50, test: 30, prac: 20, neg: 20 }, { neg: null })).toBe(false)
  })

  it('con peso y nota pondera como el backend', () => {
    expect(f1(calcScore({ seg: 50, test: 30, prac: 20, neg: 20 }, { ...cats, neg: 0 }))).toBe('83.3')
  })

  it('el .ia_voy.toml lleva negocio', () => {
    const toml = toToml({ weights: { seg: 40, test: 20, prac: 20, neg: 20 }, thresholds: { score: 70, cov: 60 }, ignored: [], excluded: [] })
    expect(toml).toContain('negocio   = 0.20')
  })
})

describe('tone', () => {
  it('usa los rangos 80/60', () => {
    expect([tone(80), tone(79.9), tone(60), tone(59)]).toEqual(['good', 'warn', 'warn', 'bad'])
  })
})

describe('toToml', () => {
  it('escribe pesos normalizados, umbrales y listas', () => {
    const toml = toToml({ weights: { seg: 50, test: 30, prac: 20 }, thresholds: { score: 70, cov: 60 }, ignored: ['S101'], excluded: ['migrations/'] })
    expect(toml).toContain('seguridad = 0.50')
    expect(toml).toContain('score_minimo     = 70')
    expect(toml).toContain('ignorar = ["S101"]')
    expect(toml).toContain('excluir = ["migrations/"]')
  })
})
