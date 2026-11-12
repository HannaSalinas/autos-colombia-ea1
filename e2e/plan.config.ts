import { defineConfig } from '@playwright/test';

/**
 * Ejecución automatizada del plan de pruebas de la EA2 (PP-02): los casos US, PE y CE contra el
 * sistema real, en Google Chrome (la compatibilidad con Edge y Firefox es el caso NF-02).
 * - Un solo test que recorre los casos en orden (comparten datos: cuentas, celdas, sesiones).
 *   Cada caso atrapa sus propios errores y queda Fallido o Bloqueado sin detener a los demás.
 * - Sin trazas, videos ni reporte HTML: las trazas guardarían lo que se escribe (contraseñas).
 */
export default defineConfig({
  testDir: './plan',
  testMatch: 'plan.spec.ts',
  outputDir: '/tmp/test-results-plan',
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
  },
  projects: [{ name: 'chrome', use: { browserName: 'chromium', channel: 'chrome' } }],
});
