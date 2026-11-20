import { defineConfig } from '@playwright/test';

/**
 * RNF-20 y RNF-26 (caso de prueba NF-02 de los planes PP-02 y PP-03): el mismo recorrido en tres navegadores.
 * - Un navegador a la vez (workers: 1): el equipo tiene 2 núcleos y así las capturas son estables.
 * - Sin trazas, videos ni reporte HTML: las trazas guardan lo que se escribe (las contraseñas).
 */
export default defineConfig({
  testDir: '.',
  // RECORRIDO=rnf26 (EA3) ejecuta las pantallas de la Iteración 3; por defecto, las de la EA2.
  testMatch: process.env.RECORRIDO === 'rnf26' ? 'rnf26.spec.ts' : 'nf02.spec.ts',
  // Se ejecuta con el usuario del equipo: los archivos internos de Playwright van a /tmp.
  outputDir: '/tmp/test-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  globalSetup: './preparar.ts',
  globalTeardown: './reporte.ts',
  use: {
    baseURL: process.env.BASE_URL ?? 'http://frontend',
    viewport: { width: 1280, height: 900 },
    locale: 'es-CO',
    timezoneId: 'America/Bogota',
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
  // Sin los perfiles "devices" de Playwright: reemplazan el user agent por uno fijo (el de
  // "Desktop Edge" dice "Edg/" aunque se abra otro navegador). Así el reporte muestra el real.
  projects: [
    { name: 'chrome', use: { browserName: 'chromium', channel: 'chrome' } },
    { name: 'edge', use: { browserName: 'chromium', channel: 'msedge' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
  ],
});
