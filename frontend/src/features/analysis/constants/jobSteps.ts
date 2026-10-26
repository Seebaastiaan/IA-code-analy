import type { Category } from '@/shared/types/common'
import type { AnalyzerId } from '../types'

/** Los 11 pasos del análisis. El backend envía el nombre y el comando real por WebSocket. */
export const JOB_STEPS: { name: string; command: string }[] = [
  { name: 'Clonando repositorio', command: 'git clone --depth 1 --branch {branch} {url}' },
  { name: 'Creando entorno aislado', command: 'uv venv .venv  (sandbox)' },
  { name: 'Instalando dependencias', command: 'uv pip install -r requirements.txt' },
  { name: 'Bandit', command: 'bandit -r . -f json' },
  { name: 'pip-audit', command: 'pip-audit --path .venv/…/site-packages -f json' },
  { name: 'pytest', command: 'coverage run -m pytest -q --maxfail=50' },
  { name: 'coverage', command: 'coverage json' },
  { name: 'Ruff', command: 'ruff check . --output-format json' },
  { name: 'Radon', command: 'radon cc . -j && radon mi . -j' },
  { name: 'Calculando score', command: 'agregación ponderada (.ia_voy.toml)' },
  { name: 'Indexando para el asistente', command: 'ast → embeddings (Gemini) → SQLite' },
]

export const ANALYZERS: Record<Category, { id: AnalyzerId; label: string }[]> = {
  seg: [
    { id: 'bandit', label: 'Bandit' },
    { id: 'pip-audit', label: 'pip-audit' },
  ],
  test: [
    { id: 'pytest', label: 'pytest' },
    { id: 'coverage', label: 'coverage' },
  ],
  prac: [
    { id: 'ruff', label: 'Ruff' },
    { id: 'radon', label: 'Radon' },
  ],
}

/** Lo que verá el usuario antes de iniciar (columna lateral del formulario). */
export const WHAT_HAPPENS: [string, string][] = [
  ['Clonado', 'Se descarga la rama indicada'],
  ['Entorno', 'Se instalan dependencias aisladas'],
  ['Análisis', 'Seis herramientas en paralelo'],
  ['Score', 'Promedio ponderado por categoría'],
  ['Reporte', 'Listo para revisar y compartir'],
]
