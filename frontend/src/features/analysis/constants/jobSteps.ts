/**
 * Pasos del análisis en el Sprint 4 (mismo orden que backend/app/analysis/steps.py). El backend envía el
 * nombre y el comando real por WebSocket.
 */
export const JOB_STEPS: { name: string; command: string }[] = [
  { name: 'Clonando repositorio', command: 'git clone --depth 1 --branch {branch} {url}' },
  { name: 'Creando entorno aislado', command: 'uv venv .venv  (sandbox)' },
]

/** Lo que llega en los siguientes sprints (se muestra deshabilitado en la lista de pasos). */
export const NEXT_STEPS: { name: string; sprint: number }[] = [
  { name: 'Instalando dependencias', sprint: 5 },
  { name: 'Analizadores (Bandit, pip-audit, pytest, coverage, Ruff, Radon)', sprint: 5 },
  { name: 'Calculando score', sprint: 6 },
  { name: 'Indexando para el asistente', sprint: 7 },
]

/** Lo que verá el usuario antes de iniciar (columna lateral del formulario). */
export const WHAT_HAPPENS: [string, string][] = [
  ['Clonado', 'Se descarga la rama indicada y se detectan sus lenguajes'],
  ['Entorno', 'Se crea un entorno virtual aislado (uv venv)'],
  ['Repositorio', 'El análisis queda guardado en el historial del repo'],
]
