/**
 * Pasos del análisis en el Sprint 5 (mismo orden que backend/app/analysis/steps.py). El backend envía el
 * nombre y el comando real por WebSocket.
 */
export const JOB_STEPS: { name: string; command: string }[] = [
  { name: 'Clonando repositorio', command: 'git clone --depth 1 --branch {branch} {url}' },
  { name: 'Creando entorno aislado', command: 'uv venv .venv  (sandbox)' },
  { name: 'Instalando dependencias', command: 'uv pip install -r requirements.txt' },
  { name: 'Bandit', command: 'bandit -r . -f json' },
  { name: 'pip-audit', command: 'pip-audit --path .venv/…/site-packages -f json' },
]

/** Lo que llega en los siguientes sprints (se muestra deshabilitado en la lista de pasos). */
export const NEXT_STEPS: { name: string; sprint: number }[] = [
  { name: 'pytest', sprint: 6 },
  { name: 'coverage', sprint: 6 },
  { name: 'Ruff', sprint: 6 },
  { name: 'Radon', sprint: 6 },
  { name: 'Calculando score', sprint: 6 },
  { name: 'Indexando para el asistente', sprint: 7 },
]

/** Lo que verá el usuario antes de iniciar (columna lateral del formulario). */
export const WHAT_HAPPENS: [string, string][] = [
  ['Clonado', 'Se descarga la rama indicada y se detectan sus lenguajes'],
  ['Entorno', 'Se crea un entorno virtual aislado (uv venv)'],
  ['Dependencias', 'Se instalan las del proyecto dentro del sandbox'],
  ['Seguridad', 'Bandit revisa el código y pip-audit las dependencias'],
  ['Repositorio', 'El análisis y sus hallazgos quedan en el historial del repo'],
]
