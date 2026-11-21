import { defineConfig } from '@playwright/test';

/**
 * Ejecución automatizada del plan de pruebas de la EA3 (PP-03): los casos TA, CL, ME, PA, AN, RE y PE
 * contra el sistema real, en Google Chrome (la compatibilidad con Edge y Firefox es el caso NF-02).
 * Igual que el PP-02: un solo test que recorre los casos en orden de dependencias, cada caso atrapa
 * sus errores, y sin trazas, videos ni reporte HTML (guardarían las contraseñas que se escriben).
 */
export default defineConfig({
  testDir: './plan3',
  testMatch: 'plan3.spec.ts',
  outputDir: '/tmp/test-results-plan3',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60 * 60_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://frontend',
    viewport: { width: 1280, height: 900 },
    locale: 'es-CO',
    timezoneId: 'America/Bogota',
    trace: 'off',
    video: 'off',
    screenshot: 'off',
    actionTimeout: 20_000,
  },
  projects: [{ name: 'chrome', use: { browserName: 'chromium', channel: 'chrome' } }],
});
