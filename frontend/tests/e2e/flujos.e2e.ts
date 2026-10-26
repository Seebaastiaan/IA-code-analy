import { expect, test } from '@playwright/test'

/**
 * Flujos del Sprint 6 de punta a punta en el navegador: analizar con los 10 pasos, ver el score en
 * Repositorios y en el tablero, los archivos del clon, la configuración y el equipo.
 * Backend simulado con MSW (`.env.e2e`): su estado vive en memoria de la pestaña, así que cada flujo
 * navega dentro de la app (sin recargar) y empieza con datos limpios.
 */

test.beforeEach(async ({ page }) => {
  // Pasos rápidos del job simulado
  await page.addInitScript(() => localStorage.setItem('iavoy-mock-speed', '500'))
})

test('1 · analizar un repositorio y ver su score en Repositorios', async ({ page }) => {
  await page.goto('/repos')
  await expect(page.getByRole('heading', { name: 'Repositorios', level: 1 })).toBeVisible()
  await page.getByRole('navigation').getByRole('link', { name: 'Nuevo análisis' }).click()

  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/servicio-facturas')
  await page.getByLabel('Rama').fill('main')
  await page.getByRole('button', { name: 'Iniciar análisis' }).click()

  // Progreso en vivo por WebSocket: 10 pasos en el Sprint 6
  await expect(page).toHaveURL(/\/analyze\/jobs\//)
  await expect(page.getByText('[01/10] Clonando repositorio')).toBeVisible()
  await expect(page.getByText('[06/10] pytest')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('[10/10] Calculando score')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('main').getByText('Análisis completado · score en el tablero')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Análisis #1 completado.')).toBeVisible()

  await page.getByRole('link', { name: 'Ver en Repositorios' }).click()
  await expect(page).toHaveURL(/\/repos$/)
  await expect(page.getByText('equipo/servicio-facturas')).toBeVisible()
  await expect(page.getByLabel('Re-analizar equipo/servicio-facturas')).toBeVisible()
})

test('1b · una rama que no existe detiene el análisis y se puede reintentar', async ({ page }) => {
  await page.goto('/analyze')
  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/api-pagos')
  await page.getByLabel('Rama').fill('no-existe')
  await page.getByRole('button', { name: 'Iniciar análisis' }).click()
  await expect(page.getByText('La rama no existe').first()).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /Reintentar/ }).click()
  await expect(page.getByRole('main').getByText('Análisis completado · score en el tablero')).toBeVisible({ timeout: 15_000 })
})

test('1c · un repositorio sin Python se detiene con un mensaje claro', async ({ page }) => {
  await page.goto('/analyze')
  await page.getByLabel('URL del repositorio').fill('https://github.com/equipo/landing-web')
  await page.getByRole('button', { name: 'Iniciar análisis' }).click()
  await expect(page.getByText('El repositorio no tiene código Python').first()).toBeVisible({ timeout: 10_000 })
})

test('2 · tablero: score, tendencia y hallazgos prioritarios; archivos del clon', async ({ page }) => {
  await page.goto('/repos')
  await page.getByRole('navigation').getByRole('link', { name: 'Tablero' }).click()
  await expect(page.getByRole('heading', { name: 'Resumen del equipo', level: 1 })).toBeVisible()
  await expect(page.getByText('Score global')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Tendencia' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Atención prioritaria' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Análisis recientes' })).toBeVisible()

  await page.getByRole('navigation').getByRole('link', { name: 'Repositorios' }).click()
  await page.getByRole('link', { name: 'Ver archivos de equipo/api-pagos' }).click()
  await expect(page).toHaveURL(/\/repos\/r1\/files/)
  await page.getByRole('button', { name: 'utils.py' }).click()
  await expect(page.getByText('import hashlib').first()).toBeVisible()
})

test('3 · configuración del proyecto y .ia_voy.toml', async ({ page }) => {
  await page.goto('/repos/r1/settings')
  await expect(page.getByRole('heading', { name: 'Configuración', level: 1 })).toBeVisible()
  const save = page.getByRole('button', { name: 'Guardar configuración' })
  await expect(save).toBeDisabled()

  await page.getByPlaceholder('p. ej. E501').fill('E501')
  await page.getByPlaceholder('p. ej. E501').press('Enter')
  await expect(page.getByRole('button', { name: 'Quitar E501' })).toBeVisible()
  await expect(page.getByText('ignorar = ["B101", "E501"]')).toBeVisible()
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

test('fuera del Sprint 6: reporte, editor, asistente y comparativa no existen todavía', async ({ page }) => {
  await page.goto('/repos')
  const nav = page.getByRole('navigation')
  for (const name of ['Reporte', 'Editor', 'Asistente IA', 'Comparativa']) {
    await expect(nav.getByRole('link', { name })).toHaveCount(0)
  }
  await page.goto('/repos/r1/reports/latest')
  await expect(page.getByText(/no existe|no encontrada|404/i).first()).toBeVisible()
})
