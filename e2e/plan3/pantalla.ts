/** Ayudas de pantalla del plan PP-03: sesión en el navegador y registro de lo que la pantalla envía a la API. */
import type { Browser, BrowserContext, Page } from '@playwright/test';
import { casoActual, ingresarUI, limpiar, menu, nuevaPagina } from '../plan/contexto';
import { cuenta } from './escenario';

const abiertos: BrowserContext[] = [];

/** Abre el navegador con la sesión de una cuenta del escenario y espera el menú. */
export async function conSesionUI(browser: Browser, usuario: string, ruta?: string): Promise<Page> {
  const { contexto, page } = await nuevaPagina(browser);
  abiertos.push(contexto);
  await page.goto('/ingresar');
  await ingresarUI(page, usuario, cuenta(usuario).contrasena);
  await menu(page).waitFor();
  if (ruta) await irA(page, ruta);
  return page;
}

export async function irA(page: Page, ruta: string): Promise<void> {
  await page.goto(ruta);
  await page.waitForLoadState('networkidle');
}

export async function cerrarPantallas(): Promise<void> {
  await Promise.all(abiertos.splice(0).map((c) => c.close().catch(() => undefined)));
}

/**
 * Hace una acción en la pantalla y guarda en la evidencia del caso la solicitud que la pantalla envió y
 * la respuesta de la API (sin encabezados: nunca el token).
 */
export async function conRespuesta(page: Page, metodo: string, fragmento: string, accion: () => Promise<void>, nota: string): Promise<{ status: number; body: any }> {
  const espera = page.waitForResponse((r) => r.request().method() === metodo && new URL(r.url()).pathname.startsWith(fragmento), { timeout: 20_000 });
  await accion();
  const r = await espera;
  let body: any = null;
  try {
    body = await r.json();
  } catch {
    body = await r.text().catch(() => null);
  }
  const url = new URL(r.url());
  const datos = r.request().postData();
  casoActual()?.api.push({
    sesion: 'pantalla', metodo, ruta: url.pathname + url.search, codigo: r.status(),
    ...(datos ? { solicitud: limpiar(JSON.parse(datos)) } : {}), respuesta: limpiar(body), nota,
  });
  await page.waitForTimeout(300);
  return { status: r.status(), body };
}

/** Cuenta las solicitudes con ese método a rutas que empiezan por el fragmento durante la acción. */
export async function solicitudesDurante(page: Page, metodo: string, fragmento: string, accion: () => Promise<void>): Promise<number> {
  let n = 0;
  const escuchar = (req: any) => {
    if (req.method() === metodo && new URL(req.url()).pathname.startsWith(fragmento)) n++;
  };
  page.on('request', escuchar);
  await accion();
  await page.waitForTimeout(600);
  page.off('request', escuchar);
  return n;
}

export async function texto(page: Page, selector: string): Promise<string> {
  return ((await page.locator(selector).first().textContent()) ?? '').replace(/\s+/g, ' ').trim();
}

/** El texto de un dato (<dt>…</dt><dd>…</dd>) de la pantalla. */
export async function dato(page: Page, etiqueta: string, dentro = 'body'): Promise<string> {
  const dd = page.locator(dentro).locator('dl > div').filter({ has: page.locator('dt', { hasText: new RegExp(`^\\s*${etiqueta}\\s*$`) }) }).locator('dd');
  return ((await dd.first().textContent()) ?? '').replace(/\s+/g, ' ').trim();
}
