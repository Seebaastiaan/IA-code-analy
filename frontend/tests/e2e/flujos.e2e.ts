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
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Resumen del equipo' })).toBeVisible()
  await page.getByRole('main').getByRole('link', { name: 'Nuevo análisis' }).click()

  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/api-pagos')
  await page.getByLabel('Rama').fill('main')
  await page.getByRole('button', { name: 'Iniciar análisis' }).click()

  // Progreso en vivo por WebSocket
  await expect(page).toHaveURL(/\/analyze\/jobs\//)
  await expect(page.getByText('[01/11] Clonando repositorio')).toBeVisible()
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
  await page.getByRole('button', { name: /B105 Clave secreta/ }).click()
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
