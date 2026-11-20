/**
 * RNF-26 (caso NF-02 del plan PP-03) · Compatibilidad de navegadores de la Iteración 3. El mismo
 * recorrido de 10 pantallas en Chrome, Edge y Firefox. Cada paso VERIFICA el contenido de la pantalla
 * antes de capturarla y no se modifica ningún dato: el pago llega hasta el resumen (una consulta),
 * la tarifa y la anulación hasta su confirmación, y las tres se cancelan. Usa las semillas: tarifas
 * iniciales, clientes y el pago de ejemplo de STU852.
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

const menu = (page: Page) => page.getByRole('navigation', { name: 'Navegación principal' });
const opcion = (page: Page, nombre: string) => menu(page).getByRole('link', { name: nombre, exact: true });
const titulo = (page: Page, nombre: string) => page.getByRole('heading', { level: 1, name: nombre, exact: true });

test('RNF-26: recorrido de las 10 pantallas de la Iteración 3', async ({ page, browser }, testInfo) => {
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
    tarifas_administrador: async () => {
      await page.goto('/ingresar');
      await ingresar(page, adminUsuario, adminClave);
      await expect(menu(page)).toBeVisible();
      await opcion(page, 'Tarifas').click();
      await expect(titulo(page, 'Tarifas')).toBeVisible();
      for (const tipo of ['MOTO', 'AUTOMOVIL', 'CAMIONETA'])
        await expect(page.getByRole('article', { name: `Tarifa de ${tipo}` })).toBeVisible();
      await expect(page.getByRole('article', { name: 'Tarifa de MOTO' })).toContainText('$ 60.000');
      await expect(page.getByRole('article', { name: 'Tarifa de AUTOMOVIL' })).toContainText('$ 120.000');
      await expect(page.getByRole('article', { name: 'Tarifa de CAMIONETA' })).toContainText('$ 140.000');
      await expect(page.getByRole('heading', { name: /Historial de tarifas/ })).toBeVisible();
      await expect(page.getByRole('cell', { name: 'Sistema (semillas)' }).first()).toBeVisible();
    },
    confirmar_tarifa: async () => {
      await page.getByRole('button', { name: 'Nueva tarifa' }).click();
      await page.locator('#tipo-vehiculo').selectOption('MOTO');
      await page.locator('#valor').fill('65000');
      await page.getByRole('button', { name: 'Guardar tarifa' }).click();
      const dialogo = page.getByRole('alertdialog');
      await expect(dialogo).toContainText('¿Fijar la tarifa mensual de MOTO de $ 60.000 a $ 65.000?');
      await expect(dialogo.getByRole('button', { name: 'Sí, guardar la tarifa' })).toBeVisible();
    },
    clientes: async () => {
      await page.getByRole('alertdialog').getByRole('button', { name: 'Cancelar' }).click();
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click(); // cierra el formulario
      await opcion(page, 'Clientes').click();
      await expect(titulo(page, 'Clientes')).toBeVisible();
      await page.getByLabel('Buscar por nombre o documento').fill('Laura');
      await page.getByRole('button', { name: 'Buscar', exact: true }).click();
      const fila = page.getByRole('row').filter({ hasText: 'Laura Gómez' });
      await expect(fila).toContainText('ABC123');
      await expect(fila).toContainText('KLM45D');
      await page.getByRole('button', { name: 'Ver detalle de Laura Gómez' }).click();
      await expect(page.getByRole('heading', { name: 'Detalle de Laura Gómez' })).toBeVisible();
      await expect(page.getByText('Antes de la Iteración 3 (semillas)')).toBeVisible();
    },
    registrar_cliente_errores: async () => {
      await page.getByRole('button', { name: 'Registrar cliente' }).click();
      await page.locator('#documento').fill('1234');
      await page.locator('#nombre').fill('Al');
      await page.locator('#telefono').fill('300');
      await page.locator('#correo').fill('ana@');
      await page.getByRole('button', { name: 'Guardar cliente' }).click();
      await expect(page.getByText('El número de documento debe tener de 5 a 15 caracteres')).toBeVisible();
      await expect(page.getByText('El nombre completo debe tener de 3 a 80 caracteres.')).toBeVisible();
      await expect(page.getByText('El teléfono debe tener 10 dígitos, sin espacios ni otros caracteres.')).toBeVisible();
      await expect(page.getByText('El correo no tiene un formato válido (ej. ana@correo.com).')).toBeVisible();
    },
    pagos_estado: async () => {
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
      await opcion(page, 'Pagos').click();
      await expect(titulo(page, 'Pagos')).toBeVisible();
      await page.getByLabel('Placa').fill('stu852');
      await page.getByRole('button', { name: 'Consultar estado' }).click();
      await expect(page.getByText(/Vigente hasta el \d{2}\/\d{2}\/\d{4}/)).toBeVisible();
      // La fila "Pagado hacia adelante" muestra el periodo del pago de ejemplo con su comprobante.
      const adelante = page.getByText('Pagado hacia adelante').locator('..');
      await expect(adelante).toContainText(/Del \d{2}\/\d{2}\/\d{4} al \d{2}\/\d{2}\/\d{4}/);
      await expect(adelante).toContainText(/RC-\d{6}/);
      await expect(page.getByText('$ 120.000 al mes (AUTOMOVIL)')).toBeVisible();
    },
    pagos_resumen: async () => {
      await page.getByRole('button', { name: 'Revisar pago' }).click();
      await expect(page.getByRole('heading', { name: 'Resumen del pago' })).toBeVisible();
      await expect(page.getByText('1 mes × $ 120.000')).toBeVisible();
      await expect(page.getByText('Monto a pagar')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Confirmar pago' })).toBeVisible();
    },
    comprobante: async () => {
      await page.getByRole('button', { name: 'Volver y corregir' }).click();
      await expect(page.getByRole('heading', { name: 'Resumen del pago' })).toHaveCount(0);
      await opcion(page, 'Pagos registrados').click();
      await expect(titulo(page, 'Pagos registrados')).toBeVisible();
      await page.locator('#filtro-placa').fill('STU852');
      await page.getByRole('button', { name: 'Buscar', exact: true }).click();
      await page.getByRole('link', { name: /^Ver comprobante RC-\d{6}$/ }).first().click();
      await expect(titulo(page, 'Detalle del pago')).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Comprobante de pago' })).toBeVisible();
      await expect(page.getByText('Total pagado')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Anular pago' })).toBeVisible();
    },
    confirmar_anulacion: async () => {
      await page.getByRole('button', { name: 'Anular pago' }).click();
      await page.getByLabel('Motivo de la anulación').fill('Prueba de compatibilidad, se cancela');
      await page.getByRole('button', { name: 'Continuar' }).click();
      const dialogo = page.getByRole('alertdialog');
      await expect(dialogo).toContainText(/¿Anular el pago RC-\d{6} de STU852 por \$ 120\.000/);
      await expect(dialogo.getByRole('button', { name: 'Sí, anular el pago' })).toBeVisible();
    },
    recaudo: async () => {
      await page.getByRole('alertdialog').getByRole('button', { name: 'Cancelar' }).click();
      await expect(page.getByRole('alertdialog')).toHaveCount(0);
      await expect(page.getByText('PAGO ANULADO')).toHaveCount(0); // cancelar no cambió nada
      await opcion(page, 'Recaudo').click();
      await expect(titulo(page, 'Recaudo')).toBeVisible();
      await expect(page.getByText('Total recaudado (pagos válidos)')).toBeVisible();
      await expect(page.getByText('Pagos anulados (no suman)')).toBeVisible();
      await expect(page.getByRole('table', { name: 'Por método de pago' })).toBeVisible();
      await expect(page.getByRole('table', { name: 'Por tipo de vehículo' })).toBeVisible();
    },
    operador_pagos: async () => {
      await page.getByRole('button', { name: 'Cerrar sesión' }).click();
      await expect(page).toHaveURL(/\/ingresar/);
      await ingresar(page, 'marta.usuga', martaClave);
      await expect(page.getByText('Operador · marta.usuga')).toBeVisible();
      await expect(opcion(page, 'Pagos registrados')).toBeVisible();
      await expect(opcion(page, 'Recaudo')).toHaveCount(0);
      await opcion(page, 'Pagos registrados').click();
      await page.getByRole('link', { name: /^Ver comprobante RC-\d{6}$/ }).first().click();
      await expect(page.getByRole('heading', { name: 'Comprobante de pago' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Anular pago' })).toHaveCount(0);
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
  if (!fallo) {
    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await expect(page).toHaveURL(/\/ingresar/);
  }
  if (escrituras.length) fallo = fallo || `Se intentó modificar datos: ${escrituras.join(', ')}`;

  const agente = await page.evaluate(() => navigator.userAgent).catch(() => 'no disponible');
  const resultado: ResultadoNavegador = { navegador, version: browser.version(), agente, pantallas: resultados };
  writeFileSync(join(RESULTADOS, `${navegador}.json`), JSON.stringify(resultado, null, 2));
  expect(escrituras, 'Ninguna solicitud debe modificar datos').toEqual([]);
  expect(fallo, 'Todas las pantallas deben funcionar').toBe('');
});
