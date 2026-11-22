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
  const base = page.getByLabel('Base A')
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
  await page.getByText('Avanzado: archivo reglas_negocio.toml').click()
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

  // Las reglas son de este proyecto: las rutas se revisan contra su repositorio (al guardar, «Avanzado» vuelve a cerrarse)
  await page.getByText('Avanzado: archivo reglas_negocio.toml').click()
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
  await expect(dialog.getByLabel('Reglas de negocio para este análisis')).toHaveValue(/# Fuente: Cap. 2 «Tickets» · pág. 3\n\[\[regla\]\]\nid {10}= "RN-001"/)
  await dialog.getByRole('button', { name: 'Usar en este análisis' }).click()
  await expect(dialog).toBeHidden()
  await expect(rules.getByText('3 regla(s) · equipo/bot-soporte escritas aquí')).toBeVisible()
  // Ya hay reglas en el formulario: no se vuelve a ofrecer el documento
  await expect(rules.getByRole('button', { name: /Sacar reglas de/ })).toBeHidden()

  // En Configuración, el mismo documento desde la copia del proyecto
  await page.goto('/repos/r3/settings?tab=reglas')
  await page.getByRole('button', { name: 'Sacar reglas de Requerimientos.pdf' }).click()
  await expect(page.getByText('3 regla(s) sacadas de')).toBeVisible()
  await page.getByText('Avanzado: archivo reglas_negocio.toml').click()
  await expect(page.getByLabel('Contenido de reglas_negocio.toml')).toHaveValue(/nombre = "equipo\/bot-soporte"/)
  await page.getByRole('button', { name: 'Guardar en la app' }).click()
  await expect(page.getByText('Reglas guardadas: se usarán en el siguiente análisis')).toBeVisible()

  // Tabla de aprobación: lo importado entra en borrador y una regla con dudas no se aprueba
  const table = page.getByRole('heading', { name: 'Aprobación de las reglas' }).locator('xpath=../..')
  await expect(table.getByText(/3 de 3 reglas son borrador/)).toBeVisible()
  // Cada regla dice de qué capítulo y página del documento salió
  await expect(table.getByText('Cap. 2 «Tickets» · pág. 3').first()).toBeVisible()
  // Y la frase del documento que la respalda (en un PDF no se puede comprobar automáticamente)
  await table.getByRole('button', { name: 'Ver RN-001' }).click()
  await expect(table.getByText('«Solo un agente de soporte puede cerrar un ticket.»')).toBeVisible()
  await expect(table.getByText('Sin comprobar').first()).toBeVisible()
  await table.getByRole('button', { name: /Aprobar las que no tienen dudas/ }).click()
  await expect(table.getByText(/2 de 3 reglas son borrador/)).toBeVisible()
  await table.getByLabel('Elegir RN-002').check()
  await table.getByRole('button', { name: /Aprobar elegidas/ }).click()
  await expect(table.getByRole('alert')).toContainText('RN-002: tiene 1 duda(s) abierta(s)')

  // Resolver la duda (se quita de la lista) y entonces sí se aprueba
  await table.getByRole('button', { name: 'Ver RN-002' }).click()
  await table.getByRole('button', { name: 'Resuelta' }).click()
  await table.getByLabel('Elegir RN-002').check()
  await table.getByRole('button', { name: /Aprobar elegidas/ }).click()
  await expect(table.getByText(/1 de 3 reglas son borrador/)).toBeVisible()
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

test('reglas de negocio: mapa del proyecto y arnés de pruebas (proponer, probar, aprobar)', async ({ page }) => {
  await page.goto(`/repos/${REPO}/settings?tab=reglas`)
  const card = page.locator('section, div').filter({ has: page.getByRole('heading', { name: 'Mapa y arnés de pruebas' }) }).last()
  await expect(card.getByText('IA voy encontró 14 endpoints, 5 modelos y 4 roles en el código.')).toBeVisible()
  await expect(card.getByText('El arnés sustituye pagos, correo, la hora')).toBeVisible()

  await card.getByRole('button', { name: 'Proponer con IA' }).click()
  await expect(card.getByText('Propuesto por IA · Gemini 3.8 Flash')).toBeVisible()
  await expect(card.getByText('Un pago se crea como el rol «ventas»')).toBeVisible()
  // Sin prueba de humo no se aprueba
  await expect(card.getByRole('button', { name: 'Aprobar arnés' })).toBeDisabled()

  await card.getByRole('button', { name: 'Correr prueba de humo' }).click()
  await expect(card.getByText(/Corriendo la prueba de humo en el sandbox/)).toBeVisible()
  await expect(card.getByText('La prueba de humo pasó')).toBeVisible()
  await card.getByRole('button', { name: 'Ver las 6 comprobaciones' }).click()
  await expect(card.getByText("como('cliente')")).toBeVisible()
  await card.getByRole('button', { name: 'Aprobar arnés' }).click()
  await expect(card.getByText('Aprobado', { exact: true })).toBeVisible()

  // Editarlo a mano invalida la aprobación; un token distinto rompe como(rol) y sale un solo aviso
  await card.getByRole('button', { name: 'Ver y editar el código (conftest.py)' }).click()
  const code = card.getByLabel('Código del arnés (conftest.py)')
  await code.fill((await code.inputValue()).replaceAll('Bearer prueba-{rol}', 'Bearer otro-{rol}'))
  await card.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(card.getByText('Editado a mano')).toBeVisible()
  await card.getByRole('button', { name: 'Correr prueba de humo' }).click()
  await expect(card.getByText('La prueba de humo falló')).toBeVisible()
  await expect(card.getByText(/como\('cliente'\): AssertionError: como\('cliente'\): GET \/pagos respondió 401/)).toBeVisible()
})

test('reglas de negocio: pruebas generadas por IA voy (generar, correr, aprobar)', async ({ page }) => {
  test.slow()
  await page.goto(`/repos/${REPO}/settings?tab=reglas`)
  const harnessCard = page.locator('div').filter({ has: page.getByRole('heading', { name: 'Mapa y arnés de pruebas' }) }).last()
  const card = page.locator('div').filter({ has: page.getByRole('heading', { name: 'Pruebas de las reglas' }) }).last()
  await expect(card.getByText('Aprueba el arnés de pruebas (arriba)')).toBeVisible()

  // Primero el arnés: proponer, prueba de humo y aprobar
  await harnessCard.getByRole('button', { name: 'Proponer con IA' }).click()
  await harnessCard.getByRole('button', { name: 'Correr prueba de humo' }).click()
  await expect(harnessCard.getByText('La prueba de humo pasó')).toBeVisible()
  await harnessCard.getByRole('button', { name: 'Aprobar arnés' }).click()

  const generate = card.getByRole('button', { name: /^Generar pruebas \(\d+\)$/ })
  await expect(generate).toBeEnabled()
  await generate.click()
  await expect(card.getByText(/La IA está escribiendo la prueba/)).toBeVisible()
  await expect(card.getByRole('button', { name: /^Correr borradores \([1-9]\d*\)$/ })).toBeEnabled({ timeout: 20_000 })
  await card.getByRole('button', { name: /^Correr borradores/ }).click()
  await expect(card.getByText(/Corriendo \d+ prueba\(s\) en el sandbox/)).toBeVisible()
  await expect(card.getByRole('button', { name: /^Aprobar las listas \([1-9]\d*\)$/ })).toBeEnabled({ timeout: 20_000 })

  // El detalle de una regla: código, supuestos y la primera corrida
  await card.getByRole('button', { name: /^RN-001 / }).first().click()
  await expect(card.getByText('Primera corrida:')).toBeVisible()
  await expect(card.getByText('Un pago se cobra con POST /pagos/{id}/cobrar')).toBeVisible()

  await card.getByRole('button', { name: /^Aprobar las listas/ }).click()
  await expect(page.getByText('Pruebas aprobadas: cuentan desde el siguiente análisis')).toBeVisible()
  await expect(card.getByLabel('Resumen de pruebas').getByText(/^[1-9]\d* aprobada\(s\)$/)).toBeVisible()
  await expect(card.getByRole('button', { name: 'Exportar para el repo' })).toBeEnabled()
})

test('reglas de negocio: matriz de permisos, evidencia y prueba de fuerza (fase 5)', async ({ page }) => {
  test.slow()
  await page.goto(`/repos/${REPO}/settings?tab=reglas`)
  const harnessCard = page.locator('div').filter({ has: page.getByRole('heading', { name: 'Mapa y arnés de pruebas' }) }).last()
  const card = page.locator('div').filter({ has: page.getByRole('heading', { name: 'Pruebas de las reglas' }) }).last()
  await harnessCard.getByRole('button', { name: 'Proponer con IA' }).click()
  await harnessCard.getByRole('button', { name: 'Correr prueba de humo' }).click()
  await expect(harnessCard.getByText('La prueba de humo pasó')).toBeVisible()
  await harnessCard.getByRole('button', { name: 'Aprobar arnés' }).click()

  // RN-004 habla de autorización: la matriz se marca y la prueba sale de la tabla, sin IA
  await card.getByRole('button', { name: /^RN-004 / }).first().click()
  await card.getByRole('button', { name: 'Matriz de permisos' }).click()
  const save = card.getByRole('button', { name: /^Guardar y escribir la prueba/ })
  await expect(save).toBeDisabled()
  await card.getByRole('button', { name: 'POST /pagos/{pago_id}/reembolsar como cliente: fuera de la matriz' }).click()
  await expect(card.getByRole('button', { name: 'POST /pagos/{pago_id}/reembolsar como cliente: permitido' })).toBeVisible()
  await card.getByRole('button', { name: 'Usar lo que hace el código' }).click()
  await save.click()
  await expect(page.getByText('Prueba escrita desde la matriz: córrela y apruébala')).toBeVisible()
  await expect(card.getByText(/de la matriz de permisos \(sin IA\)/)).toBeVisible()

  // Evidencia de apoyo: dónde parece estar implementada (no cambia el resultado)
  await card.getByRole('button', { name: 'Dónde está en el código' }).click()
  await expect(card.getByText('Evidencia de apoyo:')).toBeVisible()
  await expect(card.getByText(/pagos\/servicio\.py:\d+-\d+/)).toBeVisible()

  // Prueba de fuerza: solo después de correrla y si pasa
  await expect(card.getByRole('button', { name: 'Prueba de fuerza', exact: true })).toBeDisabled()
  await card.getByRole('button', { name: /^Correr borradores/ }).click()
  await expect(card.getByRole('button', { name: /^Prueba de fuerza \([1-9]\d*\)$/ })).toBeEnabled({ timeout: 20_000 })
  await card.getByRole('button', { name: /^Prueba de fuerza \(/ }).click()
  await expect(card.getByText(/Prueba de fuerza de \d+ prueba\(s\)/)).toBeVisible()
  await expect(card.getByText(/cambios detectados/)).toBeVisible({ timeout: 20_000 })
})

test('reglas de negocio en el score: tablero y reporte muestran su nota aunque pese 0 %', async ({ page }) => {
  await page.goto('/dashboard')
  // api-pagos trae reglas medibles: su tarjeta lleva a la pestaña Reglas del reporte
  const card = page.getByRole('link', { name: /Reglas de negocio/ })
  await expect(card).toBeVisible()
  await expect(card).toContainText('63/100')
  await expect(page.getByRole('button', { name: 'Reglas de negocio' })).toBeVisible()
  await card.click()
  await expect(page).toHaveURL(/tab=reglas/)

  // En el encabezado del reporte dice que no cuenta (peso 0 %)
  await openReport(page)
  await expect(page.getByText(/Reglas de negocio:/)).toContainText('no cuenta en el score')
})

test('reglas del repositorio: se aprueban en la copia del proyecto y avisa que falta el commit', async ({ page }) => {
  await page.goto(`/repos/${REPO}/settings?tab=reglas`)
  await expect(page.getByText(/Son las reglas del repositorio: lo que cambies se guarda en su copia, no en GitHub/)).toBeVisible()
  await page.getByLabel('Elegir RN-001').check()
  await page.getByRole('button', { name: 'Volver a borrador' }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Guardado en la copia del proyecto' })).toBeVisible()
  await expect(page.getByText(/1 de \d+ reglas son borrador/)).toBeVisible()
})

test('reglas de negocio: solo se suben PDF y Word, con la fuente de cada regla', async ({ page }) => {
  await page.goto('/repos/r3/settings?tab=reglas')
  const upload = page.getByLabel('Documento de requisitos')
  await expect(upload).toHaveAttribute('accept', '.pdf,.docx')

  // Cualquier otro tipo se rechaza con un aviso, sin llamar a la IA
  await upload.setInputFiles({ name: 'notas.txt', mimeType: 'text/plain', buffer: Buffer.from('hola') })
  await expect(page.getByText('Tipo de archivo no válido: sube un PDF o un Word (.docx)')).toBeVisible()
  await expect(page.getByText(/Leyendo notas.txt/)).toBeHidden()

  // Un PDF sí: la IA saca las reglas (un documento que se contradice trae una más y el aviso)
  await upload.setInputFiles({ name: 'Requisitos.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 x') })
  await expect(page.getByText('4 regla(s) sacadas de')).toBeVisible()
})

test('repositorios: eliminar uno con confirmación', async ({ page }) => {
  await page.goto('/repos')
  await expect(page.getByText('equipo/cli-utilidades')).toBeVisible()
  await page.getByRole('button', { name: 'Eliminar equipo/cli-utilidades' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: '¿Eliminar equipo/cli-utilidades?' })).toBeVisible()
  // Cancelar no borra nada
  await dialog.getByRole('button', { name: 'Cancelar' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByText('equipo/cli-utilidades')).toBeVisible()
  await page.getByRole('button', { name: 'Eliminar equipo/cli-utilidades' }).click()
  await dialog.getByRole('button', { name: 'Eliminar' }).click()
  await expect(page.getByText('Se eliminó equipo/cli-utilidades')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Eliminar equipo/cli-utilidades' })).toBeHidden()
})

test('reglas de negocio: documento para presentar, sin TOML', async ({ page }) => {
  await page.goto(`/repos/${REPO}/settings?tab=reglas`)
  const popup = page.waitForEvent('popup')
  await page.getByRole('button', { name: 'Documento para presentar' }).click()
  const doc = await popup
  await expect(doc.getByRole('heading', { level: 1 })).toContainText('Reglas de negocio · ')
  await expect(doc.getByText('Fuente:').first()).toBeVisible()

  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Markdown' }).click()
  expect((await download).suggestedFilename()).toBe('reglas_de_negocio.md')
})

test('reglas de negocio: «Preparar todo» hace solo el arnés, las pruebas y la prueba de fuerza', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto(`/repos/${REPO}/settings?tab=reglas`)
  await page.getByRole('button', { name: 'Preparar todo' }).click()
  const steps = page.getByRole('list', { name: 'Avance de la preparación' })
  await expect(steps.getByText('Preparar el entorno de pruebas del proyecto')).toBeVisible()
  // Termina con el resumen y sin pasos fallidos
  await expect(page.getByText('Listo. El siguiente análisis usará estas reglas y pruebas.')).toBeVisible({ timeout: 90_000 })
  await expect(steps.getByText(/pruebas aprobadas por el programa/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Volver a preparar' })).toBeVisible()
})

/** Configuración de bot-soporte con las 3 reglas de «Requerimientos.pdf» importadas y guardadas (todas en borrador). */
async function importedRules(page: Page) {
  await page.goto('/repos/r3/settings?tab=reglas')
  await page.getByRole('button', { name: 'Sacar reglas de Requerimientos.pdf' }).click()
  await expect(page.getByText('3 regla(s) sacadas de')).toBeVisible()
  // Sin abrir «Avanzado»: el aviso de cambios sin guardar trae su propio botón
  await expect(page.getByLabel('Contenido de reglas_negocio.toml')).toBeHidden()
  await page.getByRole('button', { name: 'Guardar reglas' }).click()
  await expect(page.getByText('Reglas guardadas: se usarán en el siguiente análisis')).toBeVisible()
  return page.getByRole('heading', { name: 'Aprobación de las reglas' }).locator('xpath=../..')
}

test('reglas de negocio: dudas con sí o no, una regla con tus palabras y casos de control', async ({ page }) => {
  const table = await importedRules(page)
  await expect(table.getByText(/3 de 3 reglas son borrador/)).toBeVisible()

  // Una duda se contesta con Sí: la respuesta queda en la regla y ya se puede aprobar
  await table.getByRole('button', { name: 'Ver RN-002' }).click()
  await table.getByRole('button', { name: /^Responder sí:/ }).click()
  await expect(table.getByText(/Aclaración del equipo: .* Sí\./)).toBeVisible()
  await table.getByLabel('Elegir RN-002').check()
  await table.getByRole('button', { name: /Aprobar elegidas/ }).click()
  await expect(table.getByText(/2 de 3 reglas son borrador/)).toBeVisible()
  await expect(table.getByRole('alert')).toHaveCount(0)

  // «Escribe una regla con tus palabras»: entra en borrador con el siguiente número
  await page.getByLabel('Regla con tus palabras').fill('Un descuento de más del 20% lo aprueba el gerente')
  await page.getByRole('button', { name: 'Agregar la regla' }).click()
  await expect(page.getByText('RN-004 agregada en borrador: revísala y apruébala')).toBeVisible()
  await expect(table.getByRole('button', { name: 'Ver RN-004' })).toBeVisible()

  // Casos de control: lo que se sabe de una regla, comparado con el último análisis (no cambia ningún resultado)
  const control = page.getByRole('heading', { name: '¿Se le puede creer al programa?' }).locator('xpath=../..')
  await expect(control.getByRole('status')).toContainText('Marca las reglas que conoces')
  await control.getByLabel('Lo que sabes de RN-001').selectOption('cumple')
  await expect(control.getByRole('status')).toContainText(/Todavía no hay resultado para tus 1 reglas|Acertó|Falló/)
  await control.getByLabel('Lo que sabes de RN-001').selectOption('')
  await expect(control.getByRole('status')).toContainText('Marca las reglas que conoces')
})

test('reglas de negocio: lo que aprueba el programa se marca y se revierte en un clic', async ({ page }) => {
  test.setTimeout(90_000)
  const table = await importedRules(page)
  await page.getByRole('button', { name: 'Preparar todo' }).click()
  // El primer paso aprueba las reglas sin dudas; el resto no hace falta para esta comprobación
  await expect(table.getByText('Aprobada por el programa').first()).toBeVisible({ timeout: 30_000 })
  const stop = page.getByRole('button', { name: 'Detener' })
  if (await stop.isVisible()) await stop.click()

  const row = table.getByRole('listitem').filter({ hasText: 'Aprobada por el programa' }).first()
  await row.getByRole('button', { name: /^Ver RN-/ }).click()
  await expect(row.getByText(/La aprobó el programa/)).toBeVisible()
  await row.getByRole('button', { name: 'Revertir a borrador' }).click()
  await expect(table.getByText('Aprobada por el programa')).toHaveCount(0)
  await expect(table.getByText(/3 de 3 reglas son borrador/)).toBeVisible()
})

test('reglas de negocio: el resultado en palabras y «el documento manda» para corregir el código', async ({ page }) => {
  await openReport(page)
  await page.getByRole('tab', { name: 'Reglas' }).click()
  // Resumen y una frase por regla, con semáforo
  await expect(page.getByText(/reglas se cumplen · \d+ no se cumplen?/)).toBeVisible()

  await page.getByRole('button', { name: /RN-002/ }).click()
  await expect(page.getByText('El documento manda: el código tiene que seguir a la regla.')).toBeVisible()
  await page.getByRole('button', { name: 'Corregir con IA' }).click()
  // En la demo no hay IA: el error llega como aviso, sin romper la pantalla
  await expect(page.getByText('La corrección del código con IA no está disponible en la demo')).toBeVisible()
})
