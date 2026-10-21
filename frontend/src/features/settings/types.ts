import type { Thresholds, Weights } from '@/shared/types/common'

export interface ProjectConfig {
  /** Se normalizan si no suman 100 */
  weights: Weights
  thresholds: Thresholds
  /** Códigos de Bandit/Ruff ignorados */
  ignored: string[]
  /** Rutas que no se analizan */
  excluded: string[]
}

export type ServiceStatus = 'ok' | 'standby' | 'down'

export interface ServiceHealth {
  id: 'llm' | 'llm_fallback' | 'tunnel' | 'sandbox'
  name: string
  role: string
  status: ServiceStatus
  label: string
}

export interface HealthResponse {
  services: ServiceHealth[]
  /** Host público del túnel, p. ej. ia-voy.trycloudflare.com */
  tunnel_host: string | null
}
