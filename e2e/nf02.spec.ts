/**
 * NF-02 · Compatibilidad de navegadores (RNF-20). El mismo recorrido de 10 pantallas en cada
 * navegador. Cada paso VERIFICA el contenido de la pantalla (no solo toma la captura) y no se
 * modifica ningún dato: las confirmaciones se cancelan y la cuenta "abc" no llega a enviarse.
 */
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Locator, type Page } from '@playwright/test';
import {
  PANTALLAS,
  RESULTADOS,
  SALIDA,
  archivo,
  sinSecretos,
  variable,
  type ResultadoNavegador,
  type ResultadoPantalla,
} from './comun';

/** Escribe un valor secreto en un campo sin que aparezca en los registros de Playwright. */
async function escribirSecreto(campo: Locator, valor: string): Promise<void> {
  await campo.evaluate((el, v) => {
    const input = el as HTMLInputElement;
    input.value = v;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }, valor);
}

async function ingresar(page: Page, usuario: string, contrasena: string): Promise<void> {
  await page.getByLabel('Usuario').fill(usuario);
  await escribirSecreto(page.getByLabel('Contraseña'), contrasena);
  await page.getByRole('button', { name: 'Ingresar' }).click();
}

async function cerrarSesion(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page).toHaveURL(/\/ingresar/);
}

const menu = (page: Page) => page.getByRole('navigation', { name: 'Navegación principal' });

test('NF-02: recorrido de las 10 pantallas', async ({ page, browser }, testInfo) => {
  const navegador = testInfo.project.name;
  const adminUsuario = variable('ADMIN_USUARIO');
  const adminClave = variable('ADMIN_CONTRASENA');
  const martaClave = variable('MARTA_CONTRASENA');

  // Ninguna solicitud debe modificar datos (solo se permiten las de sesión).
  const escrituras: string[] = [];
  page.on('request', (r) => {
    const ruta = new URL(r.url()).pathname;
    if (!['GET', 'HEAD', 'OPTIONS'].includes(r.method()) && !ruta.startsWith('/auth/')) {
      escrituras.push(`${r.method()} ${ruta}`);
    }
  });

  const pasos: Record<string, () => Promise<void>> = {
    ingreso: async () => {
      await page.goto('/ingresar');
      await expect(page.getByRole('heading', { level: 1, name: 'Ingresar' })).toBeVisible();
      await expect(page.getByLabel('Usuario')).toBeVisible();
      await expect(page.getByLabel('Contraseña')).toHaveAttribute('type', 'password');
      await expect(page.locator('select')).toHaveCount(0); // sin selector de rol (D1)
    },
    error_credenciales: async () => {
      await ingresar(page, adminUsuario, 'clave-incorrecta-1');
      await expect(page.getByRole('alert')).toHaveText('Usuario o contraseña inválidos.');
      await expect(page).toHaveURL(/\/ingresar/);
    },
    inicio_administrador: async () => {
      await ingresar(page, adminUsuario, adminClave);
      await expect(menu(page)).toBeVisible();
      await expect(page).not.toHaveURL(/\/ingresar/);
      await expect(menu(page).getByRole('link', { name: 'Cuentas de usuario' })).toBeVisible();
      await expect(page.getByText('Administrador · ' + adminUsuario)).toBeVisible();
    },
    cuentas: async () => {
      await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
      await expect(page.getByRole('heading', { level: 1, name: 'Cuentas de usuario' })).toBeVisible();
      await expect(page.getByRole('cell', { name: 'diego.arango', exact: true })).toBeVisible();
      await expect(page.getByRole('cell', { name: 'marta.usuga', exact: true })).toBeVisible();
    },
    crear_cuenta_abc: async () => {
      await page.getByRole('button', { name: 'Nueva cuenta' }).click();
      await page.getByLabel('Nombre completo').fill('Prueba NF-02');
      await page.getByLabel('Nombre de usuario').fill('abc');
      await page.getByLabel('Contraseña inicial').fill('clave1234');
      await page.locator('#rol').selectOption('OPERADOR'); // hay otra etiqueta "Rol" en los filtros
      await page.getByRole('button', { name: 'Crear cuenta' }).click();
      await expect(page.getByText('Usa de 4 a 30 caracteres')).toBeVisible();
    },
    confirmar_desactivar: async () => {
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click(); // cierra el formulario
      await page.getByRole('button', { name: 'Desactivar la cuenta de Diego Arango (Portería 2)' }).click();
      const dialogo = page.getByRole('alertdialog');
      await expect(dialogo).toContainText('Diego Arango (Portería 2) (diego.arango)');
      await expect(dialogo.getByRole('button', { name: 'Sí, desactivar' })).toBeVisible();
    },
    celdas_administrador: async () => {
      await page.getByRole('alertdialog').getByRole('button', { name: 'Cancelar' }).click();
      await expect(page.getByRole('alertdialog')).toHaveCount(0);
      const diego = page.getByRole('row').filter({ hasText: 'diego.arango' });
      await expect(diego).toContainText('Activa'); // cancelar no cambió nada
      await menu(page).getByRole('link', { name: 'Celdas' }).click();
      // El título (nivel 1): la lista tiene otro encabezado "Celdas" con su contador.
      await expect(page.getByRole('heading', { level: 1, name: 'Celdas', exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Nueva celda' })).toBeVisible();
      await expect(page.getByRole('rowheader', { name: 'C01', exact: true })).toBeVisible();
    },
    confirmar_inhabilitar: async () => {
      const boton = page.getByRole('button', { name: /^Inhabilitar [CM]\d{2}$/ }).first();
      const etiqueta = (await boton.getAttribute('aria-label')) ?? '';
      const codigo = etiqueta.replace('Inhabilitar ', '');
      await boton.click();
      const dialogo = page.getByRole('alertdialog');
      await expect(dialogo).toContainText(`¿Inhabilitar la celda ${codigo}`);
      await expect(dialogo.getByRole('button', { name: 'Sí, inhabilitar' })).toBeVisible();
    },
    inicio_operador: async () => {
      await page.getByRole('alertdialog').getByRole('button', { name: 'Cancelar' }).click();
      await expect(page.getByRole('alertdialog')).toHaveCount(0);
      await cerrarSesion(page);
      await ingresar(page, 'marta.usuga', martaClave);
      await expect(menu(page)).toBeVisible();
      await expect(page.getByText('Operador · marta.usuga')).toBeVisible();
      await expect(menu(page).getByRole('link', { name: 'Control de acceso' })).toBeVisible();
      await expect(menu(page).getByRole('link', { name: 'Cuentas de usuario' })).toHaveCount(0);
    },
    celdas_operador: async () => {
      await menu(page).getByRole('link', { name: 'Celdas' }).click();
      await expect(page.getByRole('rowheader', { name: 'C01', exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Nueva celda' })).toHaveCount(0);
      await expect(page.getByRole('button', { name: /^Inhabilitar / })).toHaveCount(0);
      await expect(page.getByRole('button', { name: /^Editar / })).toHaveCount(0);
    },
  };

  const resultados: ResultadoPantalla[] = [];
  let fallo = '';
  for (const [numero, clave] of PANTALLAS) {
    if (fallo) {
      resultados.push({ numero, clave, estado: 'No ejecutada', detalle: 'Depende de una pantalla anterior que falló.' });
      continue;
    }
    try {
      await test.step(`${numero} ${clave}`, pasos[clave]);
      await page.screenshot({ path: join(SALIDA, archivo(navegador, numero, clave)), fullPage: true });
      resultados.push({ numero, clave, estado: 'Sí', detalle: '' });
    } catch (error) {
      // Mensaje legible para el reporte: sin códigos de color y con el elemento que falló.
      fallo = sinSecretos(String(error instanceof Error ? error.message : error))
        .replace(/\u001b\[[0-9;]*m/g, '')
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith('Call log') && !l.startsWith('-'))
        .slice(0, 4)
        .join(' · ');
      await page.screenshot({ path: join(SALIDA, archivo(navegador, numero, clave)), fullPage: true }).catch(() => {});
      resultados.push({ numero, clave, estado: 'No', detalle: fallo });
    }
  }
  if (!fallo) await cerrarSesion(page);
  if (escrituras.length) fallo = fallo || `Se intentó modificar datos: ${escrituras.join(', ')}`;

  const agente = await page.evaluate(() => navigator.userAgent).catch(() => 'no disponible');
  const resultado: ResultadoNavegador = { navegador, version: browser.version(), agente, pantallas: resultados };
  writeFileSync(join(RESULTADOS, `${navegador}.json`), JSON.stringify(resultado, null, 2));
  expect(escrituras, 'Ninguna solicitud debe modificar datos').toEqual([]);
  expect(fallo, 'Todas las pantallas deben funcionar').toBe('');
});
