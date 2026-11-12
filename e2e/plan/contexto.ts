/**
 * Herramientas comunes de la ejecución del plan de pruebas (PP-02): sesiones de API que registran cada
 * llamada, consultas a la base, capturas, limpieza de secretos y el ejecutor de casos.
 *
 * Reglas de evidencia (hoja Plan, «Evidencia mínima» y B28):
 * - Nada de contraseñas, tokens ni hashes: los campos con esos nombres se reemplazan por «omitido» y
 *   cualquier valor secreto conocido (de .env o generado aquí) se borra de los textos.
 * - Las contraseñas de las cuentas de prueba se generan en memoria y nunca se escriben.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { join } from 'node:path';
import { request, type APIRequestContext, type Browser, type BrowserContext, type Locator, type Page } from '@playwright/test';
import { Client } from 'pg';

export const SALIDA = process.env.SALIDA ?? '/e2e/salida';
export const BASE = process.env.BASE_URL ?? 'http://frontend';
mkdirSync(SALIDA, { recursive: true });

// ------------------------------------------------------------------ secretos
const secretos = new Set<string>();
export function registrarSecreto(valor: string | undefined | null): void {
  if (valor && valor.length >= 4) secretos.add(valor);
}
['ADMIN_CONTRASENA', 'MARTA_CONTRASENA', 'PGPASSWORD', 'TOKEN_VENCIDO'].forEach((n) => registrarSecreto(process.env[n]));

/** Contraseña aleatoria que cumple las reglas (8 a 64 caracteres, letra y número). Solo en memoria. */
export function contrasenaAleatoria(): string {
  const valor = `Pp${randomBytes(12).toString('base64url')}7k`;
  registrarSecreto(valor);
  return valor;
}

const CLAVE_SECRETA = /token|contrasena|password|hash|authorization/i;

export function ocultar(texto: string): string {
  let t = texto;
  for (const s of secretos) t = t.split(s).join('«omitido»');
  return t
    .replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g, '«token omitido»')
    .replace(/\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}/g, '«hash omitido»');
}

export function limpiar(valor: unknown): unknown {
  if (typeof valor === 'string') return ocultar(valor);
  if (Array.isArray(valor)) return valor.map(limpiar);
  if (valor && typeof valor === 'object')
    return Object.fromEntries(
      Object.entries(valor as Record<string, unknown>).map(([k, v]) => [k, CLAVE_SECRETA.test(k) ? '«omitido»' : limpiar(v)]),
    );
  return valor;
}

export function variable(nombre: string): string {
  const valor = process.env[nombre];
  if (!valor) throw new Error(`Falta la variable ${nombre} (se toma de .env a través de docker compose).`);
  return valor;
}

// ------------------------------------------------------------------ registro por caso
export interface LlamadaApi {
  sesion: string;
  metodo: string;
  ruta: string;
  codigo: number;
  solicitud?: unknown;
  respuesta: unknown;
  nota?: string;
}
interface ConsultaBd {
  nota: string;
  consulta: string;
  parametros: unknown[];
  filas: Record<string, unknown>[];
}

export class Caso {
  api: LlamadaApi[] = [];
  bd: ConsultaBd[] = [];
  capturas: string[] = [];
  /** Lo observado, en orden: se usa para el «Resultado real». */
  notas: string[] = [];
  constructor(readonly id: string) {}
  anotar(texto: string): void {
    this.notas.push(texto);
  }
}

let actual: Caso | undefined;
export const casoActual = (): Caso | undefined => actual;

/** El caso no se pudo ejecutar porque no se cumple su precondición. */
export class Bloqueo extends Error {}
/** El sistema no se comporta como dice el resultado esperado. */
export class Falla extends Error {}

export function verificar(condicion: boolean, mensaje: string): void {
  if (!condicion) throw new Falla(mensaje);
}
export function precondicion(condicion: boolean, mensaje: string): void {
  if (!condicion) throw new Bloqueo(mensaje);
}

// ------------------------------------------------------------------ API
export interface Respuesta {
  status: number;
  body: any;
}

export class Api {
  constructor(
    private readonly ctx: APIRequestContext,
    readonly etiqueta: string,
    /** Solo en memoria: se usa para reutilizar el token anterior en US-06, US-16 y US-17. */
    readonly token?: string,
  ) {}

  async llamar(metodo: string, ruta: string, cuerpo?: unknown, nota?: string): Promise<Respuesta> {
    const r = await this.ctx.fetch(ruta, { method: metodo, data: cuerpo, failOnStatusCode: false });
    const texto = await r.text();
    let body: unknown = texto;
    try {
      body = texto ? JSON.parse(texto) : null;
    } catch {
      /* respuesta que no es JSON: se guarda como texto */
    }
    actual?.api.push({
      sesion: this.etiqueta,
      metodo,
      ruta,
      codigo: r.status(),
      ...(cuerpo === undefined ? {} : { solicitud: limpiar(cuerpo) }),
      respuesta: limpiar(body),
      ...(nota ? { nota } : {}),
    });
    return { status: r.status(), body };
  }
  get = (ruta: string, nota?: string) => this.llamar('GET', ruta, undefined, nota);
  post = (ruta: string, cuerpo?: unknown, nota?: string) => this.llamar('POST', ruta, cuerpo, nota);
  patch = (ruta: string, cuerpo?: unknown, nota?: string) => this.llamar('PATCH', ruta, cuerpo, nota);
}

const contextos: APIRequestContext[] = [];
async function contexto(headers: Record<string, string> = {}): Promise<APIRequestContext> {
  const c = await request.newContext({ baseURL: BASE, extraHTTPHeaders: headers });
  contextos.push(c);
  return c;
}

/** Cliente sin sesión. */
export async function anonimo(etiqueta = 'sin sesión'): Promise<Api> {
  return new Api(await contexto(), etiqueta);
}

/** Cliente con un token ya conocido (por ejemplo, uno vencido o uno anterior). */
export async function conToken(token: string, etiqueta: string): Promise<Api> {
  registrarSecreto(token);
  return new Api(await contexto({ Authorization: `Bearer ${token}` }), etiqueta, token);
}

/** Inicia sesión por la API y devuelve un cliente con el token. Falla si el login no responde 200. */
export async function sesion(usuario: string, contrasena: string, nota?: string): Promise<Api> {
  const r = await (await anonimo(usuario)).post('/auth/login', { usuario, contrasena }, nota ?? `iniciar sesión como ${usuario}`);
  if (r.status !== 200) throw new Error(`No se pudo iniciar sesión como ${usuario}: HTTP ${r.status}`);
  return conToken(r.body.token, usuario);
}

// ------------------------------------------------------------------ base de datos
let pg: Client | undefined;
export async function conectarBd(): Promise<void> {
  pg = new Client(); // PGHOST, PGDATABASE, PGUSER y PGPASSWORD llegan por el entorno
  await pg.connect();
}
export async function cerrarBd(): Promise<void> {
  await pg?.end();
}

export async function consulta(nota: string, sql: string, parametros: unknown[] = []): Promise<Record<string, any>[]> {
  const r = await pg!.query(sql, parametros);
  actual?.bd.push({ nota, consulta: sql.trim(), parametros, filas: limpiar(r.rows) as Record<string, unknown>[] });
  return r.rows;
}

function tabla(filas: Record<string, unknown>[]): string {
  if (!filas.length) return '(sin filas)';
  const columnas = Object.keys(filas[0]);
  const texto = (v: unknown) => (v instanceof Date ? v.toISOString() : v === null ? 'NULL' : String(v));
  const anchos = columnas.map((c) => Math.max(c.length, ...filas.map((f) => texto(f[c]).length)));
  const linea = (vals: string[]) => vals.map((v, i) => v.padEnd(anchos[i])).join(' | ');
  return [linea(columnas), anchos.map((a) => '-'.repeat(a)).join('-+-'), ...filas.map((f) => linea(columnas.map((c) => texto(f[c]))))].join('\n');
}

// ------------------------------------------------------------------ pantalla
export async function nuevaPagina(browser: Browser): Promise<{ contexto: BrowserContext; page: Page }> {
  const ctx = await browser.newContext({ baseURL: BASE, locale: 'es-CO', timezoneId: 'America/Bogota', viewport: { width: 1280, height: 900 } });
  return { contexto: ctx, page: await ctx.newPage() };
}

/** Escribe un valor secreto en un campo sin que aparezca en los registros de Playwright. */
export async function escribirSecreto(campo: Locator, valor: string): Promise<void> {
  await campo.evaluate((el, v) => {
    const input = el as HTMLInputElement;
    input.value = v;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }, valor);
}

export async function ingresarUI(page: Page, usuario: string, contrasena: string): Promise<void> {
  if (!page.url().includes('/ingresar')) await page.goto('/ingresar');
  await page.getByLabel('Usuario').fill(usuario);
  await escribirSecreto(page.getByLabel('Contraseña'), contrasena);
  await page.getByRole('button', { name: 'Ingresar' }).click();
}

export const menu = (page: Page) => page.getByRole('navigation', { name: 'Navegación principal' });

export async function opcionesMenu(page: Page): Promise<string[]> {
  await menu(page).waitFor();
  return (await menu(page).getByRole('link').allInnerTexts()).map((t) => t.trim());
}

export async function captura(page: Page, sufijo = ''): Promise<void> {
  const nombre = `${actual!.id}${sufijo ? `_${sufijo}` : ''}.png`;
  await page.screenshot({ path: join(SALIDA, nombre), fullPage: true });
  actual!.capturas.push(nombre);
}

/** Token guardado por la pantalla (solo en memoria del programa). */
export async function tokenDePantalla(page: Page): Promise<string> {
  const token = await page.evaluate(() => sessionStorage.getItem('autos-colombia.token') ?? '');
  registrarSecreto(token);
  return token;
}

// ------------------------------------------------------------------ ejecución de casos
export interface Resultado {
  id: string;
  estado: 'Aprobado' | 'Fallido' | 'Bloqueado';
  resultado: string;
  incidencia: string;
  evidencias: string[];
  fecha: string;
}
export const resultados: Resultado[] = [];

function guardarEvidencias(c: Caso): string[] {
  const archivos = [...c.capturas];
  if (c.api.length) {
    writeFileSync(join(SALIDA, `${c.id}_api.json`), JSON.stringify(c.api, null, 2) + '\n');
    archivos.push(`${c.id}_api.json`);
  }
  if (c.bd.length) {
    const texto = c.bd
      .map((q) => `-- ${q.nota}\n${q.consulta};\n-- parámetros: ${JSON.stringify(q.parametros)}\n-- resultado:\n${tabla(q.filas)}\n`)
      .join('\n');
    writeFileSync(join(SALIDA, `${c.id}_bd.txt`), ocultar(texto));
    archivos.push(`${c.id}_bd.txt`);
  }
  return archivos;
}

function mensajeDe(error: unknown): string {
  const texto = String(error instanceof Error ? error.message : error)
    .replace(/\u001b\[[0-9;]*m/g, '')
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('Call log') && !l.startsWith('-'))
    .slice(0, 3)
    .join(' · ');
  return ocultar(texto);
}

export function guardarResultados(): void {
  writeFileSync(join(SALIDA, 'resultados.json'), JSON.stringify(resultados, null, 2) + '\n');
}

/**
 * Ejecuta un caso: nunca lanza. Aprobado si la función termina; Fallido si una verificación no se
 * cumple (o el sistema responde algo inesperado); Bloqueado si no se cumple su precondición.
 */
export async function ejecutarCaso(id: string, fn: (c: Caso) => Promise<void>): Promise<Resultado> {
  const c = new Caso(id);
  actual = c;
  let r: Resultado;
  try {
    await fn(c);
    r = { id, estado: 'Aprobado', resultado: c.notas.join(' '), incidencia: '', evidencias: [], fecha: '' };
  } catch (error) {
    const mensaje = mensajeDe(error);
    const bloqueado = error instanceof Bloqueo;
    r = {
      id,
      estado: bloqueado ? 'Bloqueado' : 'Fallido',
      resultado: [...c.notas, `${bloqueado ? 'Precondición no cumplida' : 'Diferencia observada'}: ${mensaje}`].join(' '),
      incidencia: `INC-${id}: ${mensaje}`,
      evidencias: [],
      fecha: '',
    };
  }
  r.evidencias = guardarEvidencias(c);
  r.fecha = new Date().toISOString();
  r.resultado = ocultar(r.resultado);
  resultados.push(r);
  guardarResultados();
  actual = undefined;
  return r;
}

export async function cerrarContextos(): Promise<void> {
  await Promise.all(contextos.map((c) => c.dispose()));
}
