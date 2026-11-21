import { expect, test, type Page } from '@playwright/test'

/**
 * Los 5 flujos de usuario de docs/FRONTEND_SPEC.md §9, de punta a punta en el navegador.
 * Backend simulado con MSW (`.env.e2e`): su estado vive en memoria de la pestaña, así que cada flujo
 * navega dentro de la app (sin recargar) y empieza con datos limpios.
 */

const REPO = 'r1'

/** Monaco tarda en compilarse la primera vez que Vite lo sirve. */
const EDITOR_TIMEOUT = 45_000

async function openReport(page: Page) {
  await page.goto(`/repos/${REPO}/reports/latest`)
  await expect(page.getByRole('heading', { name: 'equipo/api-pagos', level: 1 })).toBeVisible()
}

test('1 · analizar un repositorio y abrir su reporte', async ({ page }) => {
  // Recorre varias páginas diferidas: con Vite en frío y varios navegadores a la vez se acerca a los 30 s
  test.slow()
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Resumen del equipo' })).toBeVisible()
  await page.getByRole('main').getByRole('link', { name: 'Nuevo análisis' }).click()

  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/api-pagos')
  await page.getByLabel('Rama').fill('main')
  await page.getByRole('button', { name: 'Iniciar análisis' }).click()

  // Progreso en vivo por WebSocket
  await expect(page).toHaveURL(/\/analyze\/jobs\//)
  await expect(page.getByText('[01/12] Clonando repositorio')).toBeVisible()
  await expect(page.getByRole('main').getByText('Análisis completado')).toBeVisible({ timeout: 20_000 })

  await page.getByRole('link', { name: 'Ver reporte' }).click()
  await expect(page).toHaveURL(/\/repos\/r1\/reports\/r1-\d+/)
  await expect(page.getByRole('tab', { name: 'Hallazgos' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('button', { name: /^Seguridad \d+/ })).toBeVisible()
})

test('1b · un análisis con error se puede reintentar', async ({ page }) => {
  await page.goto('/analyze')
  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/cli-utilidades')
  await page.getByRole('button', { name: 'Iniciar análisis' }).click()
  await expect(page.getByText('pytest no pudo importar un módulo').first()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: /Reintentar/ })).toBeVisible()
})

test('2 · corregir un hallazgo desde el reporte', async ({ page }) => {
  test.setTimeout(90_000)
  await openReport(page)
  await page.getByRole('button', { name: /F401 Import sin usar/ }).click()

  const drawer = page.getByRole('dialog')
  await expect(drawer.getByRole('heading', { name: 'Import sin usar: os' })).toBeVisible()
  await drawer.getByRole('button', { name: 'Aplicar corrección automática' }).click()

  // El editor abre el archivo en modo diff con la propuesta
  // React Router cambia la URL cuando termina de cargar la página del editor (Monaco)
  await expect(page).toHaveURL(/\/repos\/r1\/editor\?file=api\.py&diff=1/, { timeout: EDITOR_TIMEOUT })
  const save = page.getByRole('button', { name: 'Guardar', exact: true })
  await expect(save).toBeEnabled({ timeout: EDITOR_TIMEOUT })
  await save.click()

  // Re-análisis del archivo: el hallazgo corregido desaparece y el toast lleva al tablero
  const toast = page.getByRole('status').filter({ hasText: 'Guardado y re-analizado.' })
  await expect(toast).toBeVisible({ timeout: 10_000 })
  await expect(page.getByRole('button', { name: 'Línea 3' })).toHaveCount(0)
  await toast.getByRole('button', { name: 'Ver tablero' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
})

test('3 · compartir el reporte y verlo como invitado', async ({ page }) => {
  await openReport(page)
  await page.getByRole('button', { name: 'Compartir' }).click()

  const modal = page.getByRole('dialog')
  await expect(modal.getByRole('heading', { name: 'Compartir reporte' })).toBeVisible()
  await modal.getByRole('switch', { name: 'Proteger con contraseña' }).click()
  await modal.getByPlaceholder(/contraseña/i).fill('equipo123')
  await modal.getByLabel('Expiración').selectOption({ label: '30 días' })
  await modal.getByRole('button', { name: 'Crear enlace' }).click()
  await expect(modal.getByLabel('Enlace público')).toHaveValue(/\/r\/[\w-]+$/)

  await modal.getByRole('link', { name: 'Ver como invitado' }).click()
  await expect(page.getByText('Solo lectura')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Reporte protegido' })).toBeVisible()

  await page.getByLabel('Contraseña').fill('mala')
  await page.getByRole('button', { name: 'Ver reporte' }).click()
  await expect(page.getByText('Contraseña incorrecta')).toBeVisible()

  await page.getByLabel('Contraseña').fill('equipo123')
  await page.getByRole('button', { name: 'Ver reporte' }).click()
  await expect(page.getByRole('heading', { name: 'equipo/api-pagos' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Hallazgos principales' })).toBeVisible()
  await expect(page.getByText(/Este enlace expira en \d+ día/)).toBeVisible()
  // Sin menú de la app: es una vista pública
  await expect(page.getByRole('navigation')).toHaveCount(0)
})

test('4 · preguntar a la IA y abrir la fuente en el editor', async ({ page }) => {
  test.setTimeout(90_000)
  await openReport(page)
  // Bandit no corrige solo: la corrección la propone la IA
  await expect(page.getByRole('button', { name: /B105 Clave secreta/ })).toContainText('Fix IA')
  await page.getByRole('button', { name: /B105 Clave secreta/ }).click()
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Corregir con IA' })).toBeVisible()
  await page.getByRole('dialog').getByRole('link', { name: 'Preguntar a la IA' }).click()

  await expect(page).toHaveURL(/\/repos\/r1\/assistant/)
  // La pregunta llega prellenada y se envía sola
  await expect(page.getByText('Explícame el hallazgo B105 en auth.py:15').first()).toBeVisible()
  const source = page.getByRole('link', { name: /auth\.py:\d+/ }).first()
  await expect(source).toBeVisible({ timeout: 10_000 })
  await source.click()

  await expect(page).toHaveURL(/\/repos\/r1\/editor\?file=auth\.py&line=\d+/, { timeout: EDITOR_TIMEOUT })
  await expect(page.getByRole('heading', { name: 'Hallazgos en este archivo' })).toBeVisible({ timeout: EDITOR_TIMEOUT })
})

test('5 · seguir la evolución: tablero, comparativa y configuración', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.getByRole('img', { name: 'Tendencia de puntuación' })).toBeVisible()
  await page.getByRole('link', { name: 'Comparar' }).click()

  await expect(page.getByRole('heading', { name: 'Comparativa' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Nuevos en B' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Resueltos en B' })).toBeVisible()
  // La fecha de la etiqueta depende del día en que corre la prueba: se elige por el número del análisis
  const base = page.getByLabel('Base (A)')
  const option = base.locator('option', { hasText: /^#120 · / })
  await base.selectOption((await option.getAttribute('value'))!)
  await expect(base).toHaveValue(/-120$/)
  await expect(page.getByRole('heading', { name: 'Nuevos en B' })).toBeVisible()

  await page.getByRole('navigation').getByRole('link', { name: 'Configuración' }).click()
  await expect(page.getByRole('heading', { name: 'Configuración', level: 1 })).toBeVisible()
  const save = page.getByRole('button', { name: 'Guardar configuración' })
  await expect(save).toBeDisabled()

  await page.getByPlaceholder('p. ej. E501').fill('E501')
  await page.getByPlaceholder('p. ej. E501').press('Enter')
  await expect(page.getByRole('button', { name: 'Quitar E501' })).toBeVisible()
  await expect(page.getByText('ignorar = ["S101", "D100", "E501"]')).toBeVisible()
  await save.click()
  await expect(page.getByText('Configuración guardada')).toBeVisible()
})

test('reglas de negocio: matriz del reporte y carga desde configuración', async ({ page }) => {
  await openReport(page)
  await page.getByRole('tab', { name: 'Reglas' }).click()
  await expect(page).toHaveURL(/tab=reglas/)
  await expect(page.getByRole('heading', { name: 'Reglas de negocio · API de pagos' })).toBeVisible()
  await expect(page.getByLabel('Resumen de reglas').getByText('2 no cumplen')).toBeVisible()
  await expect(page.getByText(/usa RN-099, que no está/)).toBeVisible()

  // Detalle: la prueba que verifica la regla, con enlace al editor
  await page.getByRole('button', { name: /RN-004/ }).click()
  await expect(page.getByRole('link', { name: /tests\/test_procesador\.py:15/ })).toBeVisible()
  await page.getByRole('button', { name: 'Cumple', exact: true }).click()
  await expect(page.getByRole('button', { name: /RN-002/ })).toHaveCount(0)

  // Un repo sin reglas_negocio.toml: se cargan desde Configuración
  await page.goto('/repos/r2/settings?tab=reglas')
  await expect(page.getByRole('tab', { name: 'Reglas de negocio' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText('Sin reglas')).toBeVisible()
  const editor = page.getByLabel('Contenido de reglas_negocio.toml')
  await editor.fill('[proyecto]\nnombre = "ETL"\n\n[[regla]]\nid = "RN-1"\ntitulo = "T"\ndescripcion = "D"\nseveridad = "alta"\n')
  await page.getByRole('button', { name: 'Guardar en la app' }).click()
  await expect(page.getByRole('alert')).toContainText('línea 4: `RN-1` no cumple el formato')

  await editor.fill('[proyecto]\nnombre = "ETL"\n\n[[regla]]\nid = "RN-001"\ntitulo = "Ventas sin duplicados"\ndescripcion = "D"\nseveridad = "alta"\n')
  await page.getByRole('button', { name: 'Validar' }).click()
  await expect(page.getByText('Válido · ETL · 1 regla(s)')).toBeVisible()
  await page.getByRole('button', { name: 'Guardar en la app' }).click()
  await expect(page.getByText('Reglas guardadas: se usarán en el siguiente análisis')).toBeVisible()
  await expect(page.getByText('Cargadas en la app', { exact: true })).toBeVisible()

  // Las reglas son de este proyecto: las rutas se revisan contra su repositorio
  await editor.fill('[proyecto]\nnombre = "ETL"\n\n[[regla]]\nid = "RN-001"\ntitulo = "T"\ndescripcion = "D"\nseveridad = "alta"\nrutas = ["no_existe/"]\n')
  await page.getByRole('button', { name: 'Validar' }).click()
  await expect(page.getByText(/Aviso: RN-001: la ruta `no_existe\/` no existe en/)).toBeVisible()
})

test('reglas de negocio al cargar el repo: revisar y corregir antes de analizar', async ({ page }) => {
  await page.goto('/analyze')
  const url = page.getByLabel('URL del repositorio')
  const rules = page.getByRole('region', { name: 'Reglas de negocio' })

  // Repo con un reglas_negocio.toml válido: se ve antes de clonar
  await url.fill('https://github.com/equipo/api-pagos')
  await expect(rules.getByText('5 regla(s) · API de pagos de negocio')).toBeVisible()

  // Repo con un archivo con errores: se ve el error con su línea y se corrige aquí
  await url.fill('https://github.com/ana-lopez/scraper-precios')
  await expect(rules.getByText('reglas_negocio.toml no es válido')).toBeVisible()
  await expect(rules.getByText(/`R1` no cumple el formato `RN-###`/)).toBeVisible()
  await expect(rules.getByRole('button', { name: 'Analizar sin reglas' })).toBeVisible()
  await rules.getByRole('button', { name: 'Corregir' }).click()

  const dialog = page.getByRole('dialog')
  const editor = dialog.getByLabel('Reglas de negocio para este análisis')
  await expect(editor).toHaveValue(/id {10}= "R1"/)
  await dialog.getByRole('button', { name: 'Usar en este análisis' }).click()
  // Con errores no se acepta
  await expect(dialog.getByRole('alert')).toContainText('no cumple el formato')
  await editor.fill((await editor.inputValue()).replace('"R1"', '"RN-001"'))
  await dialog.getByRole('button', { name: 'Validar' }).click()
  await expect(dialog.getByText('Válido · Scraper de precios · 1 regla(s)')).toBeVisible()
  await dialog.getByRole('button', { name: 'Usar en este análisis' }).click()
  await expect(dialog).toBeHidden()
  await expect(rules.getByText('1 regla(s) · Scraper de precios escritas aquí')).toBeVisible()
  await expect(rules.getByText(/usará estas reglas corregidas/)).toBeVisible()

  await page.getByRole('button', { name: 'Iniciar análisis' }).click()
  await expect(page).toHaveURL(/\/analyze\/jobs\//)
})

test('reglas de negocio desde el documento de requisitos del repo', async ({ page }) => {
  await page.goto('/analyze')
  const rules = page.getByRole('region', { name: 'Reglas de negocio' })

  // Sin reglas_negocio.toml pero con un documento de requisitos: la IA solo se usa al hacer clic
  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/bot-soporte')
  await expect(rules.getByText(/Encontré docs\/Requerimientos.pdf en el repositorio/)).toBeVisible()
  await rules.getByRole('button', { name: 'Sacar reglas de Requerimientos.pdf' }).click()
  await expect(rules.getByText(/Leyendo docs\/Requerimientos.pdf con IA/)).toBeVisible()

  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: 'Reglas sacadas de docs/Requerimientos.pdf' })).toBeVisible()
  await expect(dialog.getByText('3 regla(s) sacadas de')).toBeVisible()
  await expect(dialog.getByText('Dudas del documento')).toBeVisible()
  await expect(dialog.getByText('Válido · equipo/bot-soporte · 3 regla(s)')).toBeVisible()
  await expect(dialog.getByLabel('Reglas de negocio para este análisis')).toHaveValue(/# Fuente: pág. 3 · §2.1\n\[\[regla\]\]\nid {10}= "RN-001"/)
  await dialog.getByRole('button', { name: 'Usar en este análisis' }).click()
  await expect(dialog).toBeHidden()
  await expect(rules.getByText('3 regla(s) · equipo/bot-soporte escritas aquí')).toBeVisible()
  // Ya hay reglas en el formulario: no se vuelve a ofrecer el documento
  await expect(rules.getByRole('button', { name: /Sacar reglas de/ })).toBeHidden()

  // En Configuración, el mismo documento desde la copia del proyecto
  await page.goto('/repos/r3/settings?tab=reglas')
  await page.getByRole('button', { name: 'Sacar reglas de Requerimientos.pdf' }).click()
  await expect(page.getByText('3 regla(s) sacadas de')).toBeVisible()
  await expect(page.getByLabel('Contenido de reglas_negocio.toml')).toHaveValue(/nombre = "equipo\/bot-soporte"/)
  await page.getByRole('button', { name: 'Guardar en la app' }).click()
  await expect(page.getByText('Reglas guardadas: se usarán en el siguiente análisis')).toBeVisible()
})

test('equipo: invitar, ceder y quitar miembros', async ({ page }) => {
  await page.goto('/repos')
  await page.getByRole('navigation').getByRole('link', { name: 'Equipo' }).click()
  await expect(page.getByRole('heading', { name: 'Equipo IA VOY', level: 1 })).toBeVisible()
  await expect(page.getByText('6 miembro(s)')).toBeVisible()

  await page.getByRole('button', { name: 'Crear enlace de invitación' }).click()
  await expect(page.getByLabel('Enlace de invitación')).toHaveValue(/\/join\/\w+$/)

  // Quitar pide confirmación en un segundo clic
  const oscar = page.getByRole('listitem').filter({ hasText: 'Óscar Pérez' })
  await oscar.getByRole('button', { name: 'Quitar' }).click()
  await oscar.getByRole('button', { name: 'Sí, quitar a Óscar' }).click()
  await expect(page.getByText('Se quitó a la persona del equipo')).toBeVisible()
  await expect(page.getByRole('listitem').filter({ hasText: 'Óscar Pérez' })).toHaveCount(0)
  await expect(page.getByText('5 miembro(s)')).toBeVisible()
})

test('nuevo análisis exige un analizador por categoría', async ({ page }) => {
  await page.goto('/analyze')
  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/api-pagos')
  await page.getByRole('checkbox', { name: 'pytest', exact: true }).uncheck()
  await page.getByRole('checkbox', { name: 'coverage', exact: true }).uncheck()
  await page.getByRole('button', { name: 'Iniciar análisis' }).click()
  await expect(page.getByText('Elige al menos un analizador de: Pruebas')).toBeVisible()
  await expect(page).toHaveURL(/\/analyze$/)
})
