import type { HealthResponse } from '@/features/settings'

export const health: HealthResponse = {
  tunnel_host: 'ia-voy.trycloudflare.com',
  services: [
    { id: 'llm', name: 'Gemini 2.5 Flash', role: 'Modelo principal', status: 'ok', label: 'Operativo' },
    { id: 'llm_fallback', name: 'Groq · Llama 3.3', role: 'Respaldo ante 429', status: 'standby', label: 'Groq en espera' },
    { id: 'tunnel', name: 'Cloudflare Tunnel', role: 'ia-voy.trycloudflare.com', status: 'ok', label: 'Activo' },
    { id: 'sandbox', name: 'Sandbox WSL2', role: 'Ejecución aislada', status: 'ok', label: 'Listo' },
  ],
}
