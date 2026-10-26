import type { HealthResponse } from '@/features/settings'

export const health: HealthResponse = {
  tunnel_host: null,
  services: [
    { id: 'github', name: 'GitHub OAuth', role: 'Inicio de sesión y repos privados', status: 'ok', label: 'Configurado' },
    { id: 'sandbox', name: 'Sandbox WSL2 (Ubuntu-24.04)', role: 'Ejecuta pytest, coverage y pip-audit', status: 'ok', label: 'Activo' },
    { id: 'tunnel', name: 'Cloudflare Tunnel', role: 'Acceso público', status: 'down', label: 'Inactivo' },
  ],
}
