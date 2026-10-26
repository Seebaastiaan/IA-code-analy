import type { HealthResponse } from '@/features/settings'

export const health: HealthResponse = {
  tunnel_host: null,
  services: [
    { id: 'llm', name: 'Gemini 3.8 Flash', role: 'Modelo principal', status: 'ok', label: 'Configurado' },
    { id: 'tunnel', name: 'Cloudflare Tunnel', role: 'Acceso público', status: 'down', label: 'Inactivo' },
    { id: 'sandbox', name: 'Sandbox WSL2 (Ubuntu-24.04)', role: 'Ejecuta pytest, coverage y pip-audit', status: 'ok', label: 'Activo' },
  ],
}
