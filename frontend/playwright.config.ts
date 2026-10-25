import { defineConfig, devices } from '@playwright/test'

const PORT = 5174

/**
 * Pruebas e2e de los 5 flujos de docs/FRONTEND_SPEC.md §9 contra el backend simulado (MSW, `.env.e2e`).
 * Usa el Chrome instalado (`PW_CHANNEL=chromium` para el de Playwright: `npx playwright install chromium`).
 */
export default defineConfig({
  testDir: 'tests/e2e',
  testMatch: '**/*.e2e.ts',
  fullyParallel: true,
  // Vite compila cada página diferida la primera vez que se pide: con varios navegadores a la vez tarda
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    channel: process.env.PW_CHANNEL ?? 'chrome',
  },
  webServer: {
    command: `npx vite --mode e2e --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
