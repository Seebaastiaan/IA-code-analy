/**
 * Mapa del proyecto y arnés de pruebas simulados (backend: app.projects.arnes, docs/PROPUESTA_REGLAS_VERIFICABLES.md §7).
 * La prueba de humo "corre" unos segundos y pasa, salvo que el arnés no autentique (token cambiado a mano).
 */
import type { Harness, HarnessView, MapSummary, SmokeTest } from '@/features/rules/types'
import { getRepo } from './db'

const SMOKE_MS = 2500

const MAPS: Record<string, MapSummary> = {
  default: {
    framework: 'fastapi', frameworks: ['fastapi'], endpoints: 14, models: 5, schemas: 9, roles: ['cliente', 'ventas', 'finanzas', 'admin'],
    integrations: ['pagos', 'correo'], uses_time: true, entry: ['app.main:app'], warnings: [],
  },
}

const CODE = `"""
Arnés de las pruebas de reglas de negocio, propuesto por IA voy (docs/PROPUESTA_REGLAS_VERIFICABLES.md §7).
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.modelos import Usuario


class PreparacionFallida(Exception):
    """El *Dado* del escenario no se pudo preparar: la prueba está rota, no el código."""


def preparar(condicion: bool, motivo: str) -> None:
    if not condicion:
        raise PreparacionFallida(motivo)


@pytest.fixture
def sesiones():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: (yield fabrica())
    yield fabrica
    app.dependency_overrides.clear()


@pytest.fixture
def api(sesiones):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def como(sesiones):
    clientes = {}

    def cliente(rol: str):
        if rol not in clientes:
            with sesiones() as db:
                db.add(Usuario(nombre=rol, rol=rol, token=f"prueba-{rol}"))
                db.commit()
            clientes[rol] = TestClient(app, headers={"Authorization": f"Bearer prueba-{rol}"}, raise_server_exceptions=False)
        return clientes[rol]

    return cliente


@pytest.fixture
def crear_pago(como):
    folio = count(1)

    def crear(monto="100.00", **campos):
        r = como("ventas").post("/pagos", json={"folio": f"P-{next(folio):04d}", "monto": monto, **campos})
        preparar(r.status_code == 201, f"no se pudo crear el pago: {r.status_code} {r.text}")
        return r.json()

    return crear
`

const views = new Map<string, Harness>()
const timers = new Map<string, ReturnType<typeof setTimeout>>()

const now = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z')

function check(code: string): Pick<Harness, 'fixtures' | 'errors' | 'warnings'> {
  const fixtures = [...code.matchAll(/@pytest\.fixture[^\n]*\ndef (\w+)/g)].map((m) => m[1])
  const errors: string[] = []
  for (const name of ['api', 'como']) if (!fixtures.includes(name)) errors.push(`Falta el fixture \`${name}\``)
  if (!/def preparar\(/.test(code)) errors.push('Falta la función `preparar(condicion, motivo)`')
  const denied = /^\s*(?:import|from) (subprocess|socket|shutil)\b/m.exec(code)
  if (denied) errors.push(`el arnés no puede importar \`${denied[1]}\``)
  const warnings = fixtures.includes('reloj') ? [] : ['El proyecto usa la hora (datetime.now…) y el arnés no tiene `reloj`: las reglas con plazos no serán deterministas']
  return { fixtures, errors, warnings }
}

function harness(code: string, origin: Harness['origin'], extra: Partial<Harness> = {}): Harness {
  return {
    code, origin, source_path: null, assumptions: [], model: null, commit: null, updated_at: now(), ...check(code),
    smoke: 'pendiente', smoke_message: null, smoke_tests: [], smoke_at: null, approved: false, approved_by: null, approved_at: null, ...extra,
  }
}

export function harnessView(repoId: string): HarnessView {
  const repo = getRepo(repoId)
  const cloned = repo.reports.length > 0
  const h = views.get(repoId) ?? null
  return {
    cloned, map: cloned ? MAPS[repoId] ?? MAPS.default : null, harness: h, repo_harness: null, can_generate: true, sandbox: true,
    ready: Boolean(h?.approved),
  }
}

export function proposeHarness(repoId: string): HarnessView {
  const repo = getRepo(repoId)
  views.set(repoId, harness(CODE, 'ia', {
    model: 'Gemini 3.8 Flash', commit: repo.reports.at(-1)?.commit ?? null,
    assumptions: ['El token del usuario va en `Authorization: Bearer …`', 'Un pago se crea como el rol «ventas»'],
  }))
  return harnessView(repoId)
}

export function editHarness(repoId: string, code: string): HarnessView | null {
  const h = views.get(repoId)
  if (!h) return null
  views.set(repoId, harness(code, h.origin === 'repo' ? 'repo' : 'manual', { assumptions: h.assumptions, model: h.model, commit: h.commit, source_path: h.source_path }))
  return harnessView(repoId)
}

export function removeHarness(repoId: string): HarnessView {
  views.delete(repoId)
  clearTimeout(timers.get(repoId))
  return harnessView(repoId)
}

function smokeResult(h: Harness, roles: string[]): Pick<Harness, 'smoke' | 'smoke_message' | 'smoke_tests'> {
  // El arnés autentica con un token distinto al que guardó: como(rol) responde 401
  const broken = !h.code.includes('Bearer prueba-{rol}')
  const como: SmokeTest[] = roles.map((rol) => ({
    name: `test_humo_como[${rol}]`, outcome: broken ? 'failed' : 'passed',
    message: broken ? `AssertionError: como('${rol}'): GET /pagos respondió 401, el usuario no quedó autenticado` : '',
  }))
  const tests: SmokeTest[] = [{ name: 'test_humo_api', outcome: 'passed', message: '' }, ...como, { name: 'test_humo_crear[crear_pago]', outcome: broken ? 'failed' : 'passed', message: broken ? 'PreparacionFallida: no se pudo crear el pago: 401' : '' }]
  const failed = tests.filter((t) => t.outcome !== 'passed')
  if (!failed.length) return { smoke: 'paso', smoke_message: `${tests.length} comprobaciones pasaron`, smoke_tests: tests }
  return { smoke: 'fallo', smoke_message: `como('${roles[0]}'): ${failed[0].message}${failed.length > 1 ? ` (y ${failed.length - 1} más)` : ''}`, smoke_tests: tests }
}

/** Un texto = no se puede correr (el handler responde 422 con ese mensaje). */
export function runSmoke(repoId: string): HarnessView | string {
  const h = views.get(repoId)
  if (!h) return 'Todavía no hay arnés: propónlo con la IA o usa el del repo'
  if (h.errors.length) return `Corrige el arnés antes de probarlo: ${h.errors[0]}`
  views.set(repoId, { ...h, smoke: 'corriendo', smoke_message: null, smoke_tests: [], smoke_at: now() })
  const roles = (MAPS[repoId] ?? MAPS.default).roles
  timers.set(repoId, setTimeout(() => {
    const current = views.get(repoId)
    if (current?.smoke === 'corriendo') views.set(repoId, { ...current, ...smokeResult(current, roles), smoke_at: now() })
  }, SMOKE_MS))
  return harnessView(repoId)
}

export function approveHarness(repoId: string, user: string): HarnessView | string {
  const h = views.get(repoId)
  if (!h) return 'Todavía no hay arnés: propónlo con la IA o usa el del repo'
  if (h.smoke !== 'paso') return 'Aprueba el arnés cuando su prueba de humo haya pasado con este mismo código'
  views.set(repoId, { ...h, approved: true, approved_by: user, approved_at: now() })
  return harnessView(repoId)
}
