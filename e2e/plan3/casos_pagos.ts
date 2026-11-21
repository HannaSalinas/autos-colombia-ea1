/** Casos ME, PA, AN, RE y PE del plan PP-03. Los resultados esperados son los del Excel (hoja Casos). */
import type { Browser, Page } from '@playwright/test';
import { anonimo, captura, consulta, intentoBd, opcionesMenu, verificar, type Caso } from '../plan/contexto';
import {
  contar, E, entrar, fechaCorta, finDePeriodo, fijarTarifa, pagar, pesos, placa, PLACA_INEXISTENTE, sumarDias,
  topeDeAdelanto, VEHICULOS, type RolVehiculo,
} from './escenario';
import { conRespuesta, conSesionUI, dato, irA, solicitudesDurante, texto } from './pantalla';

type Funcion = (c: Caso, browser: Browser) => Promise<void>;
const OPERADOR = 'Operador de Prueba (operador_prueba)';
const ADMIN = 'Administradora de Prueba (admin_prueba)';
const FECHA_HORA = /\d{2}\/\d{2}\/\d{4}, \d{1,2}:\d{2} [ap]\. m\./;
const SIN_MENSUALIDAD = 'El vehículo no tiene mensualidad vigente. No puede ingresar.';
const placaReal = (rol: RolVehiculo) => `${rol} = ${placa(rol)} (${VEHICULOS[rol].tipo})`;

// ------------------------------------------------------------------ pantalla Pagos
async function buscarPlaca(page: Page, p: string): Promise<{ status: number; body: any }> {
  if (!page.url().includes('/registrar-pago')) await irA(page, '/registrar-pago');
  await page.locator('#placa').fill(p);
  const r = await conRespuesta(page, 'GET', '/pagos/estado/', () => page.getByRole('button', { name: 'Consultar estado' }).click(), `pantalla Pagos: consultar ${p}`);
  if (r.status === 200) await page.locator('#estado-titulo').waitFor();
  return r;
}
const etiqueta = (page: Page) => texto(page, '#estado-titulo .status-tag');

async function revisarPago(page: Page, meses: number, metodo: string, referencia = ''): Promise<{ status: number; body: any }> {
  await page.locator('#meses').selectOption({ label: meses === 1 ? '1 mes' : `${meses} meses` });
  await page.locator('#metodo').selectOption(metodo);
  if (referencia) await page.locator('#referencia').fill(referencia);
  const r = await conRespuesta(page, 'GET', '/pagos/cotizacion', () => page.getByRole('button', { name: 'Revisar pago' }).click(), `pantalla Pagos: revisar el pago (${meses} mes(es), ${metodo})`);
  await page.locator('#resumen-titulo').waitFor();
  return r;
}

async function confirmarPago(page: Page): Promise<{ status: number; body: any }> {
  const r = await conRespuesta(page, 'POST', '/pagos', () => page.getByRole('button', { name: 'Confirmar pago' }).click(), 'pantalla Pagos: confirmar el pago');
  if (r.status === 201) await page.locator('app-comprobante').waitFor();
  return r;
}

async function registrarEntradaUI(page: Page, p: string): Promise<{ status: number; body: any; aviso: string }> {
  await irA(page, '/control-acceso');
  await page.locator('#entry-plate').fill(p);
  const r = await conRespuesta(page, 'POST', '/estancias/entrada', () => page.getByRole('button', { name: 'Registrar entrada' }).click(), `pantalla Control de acceso: registrar la entrada de ${p}`);
  const selector = r.status === 201 ? 'section[aria-labelledby="entry-title"] p.notice.success' : 'section[aria-labelledby="entry-title"] p.notice.error';
  await page.locator(selector).first().waitFor().catch(() => undefined);
  const aviso = (await page.locator('p.notice').allInnerTexts()).map((t) => t.trim()).filter(Boolean).join(' | ');
  return { ...r, aviso };
}

async function periodos(nota: string, rol: RolVehiculo) {
  return consulta(nota, `SELECT m.id, m.fecha_inicio::text AS inicio, m.fecha_fin::text AS fin, p.comprobante, p.estado, p.meses, p.monto, p.metodo
    FROM mensualidad m LEFT JOIN pago p ON p.id = m.pago_id WHERE m.vehiculo_id = $1 ORDER BY m.fecha_inicio`, [E.vehiculoId[rol]]);
}
const pagosDe = (nota: string, rol: RolVehiculo) =>
  contar(nota, 'SELECT count(*) FROM pago p JOIN mensualidad m ON m.pago_id = p.id WHERE m.vehiculo_id = $1', [E.vehiculoId[rol]]);

async function filasPagos(page: Page): Promise<string[][]> {
  return page.locator('table tbody tr').evaluateAll((filas) =>
    filas.map((f) => Array.from(f.querySelectorAll('th, td')).map((c) => (c.textContent ?? '').replace(/\s+/g, ' ').trim())));
}
async function filtrarPagos(page: Page, f: { placa?: string; desde?: string; hasta?: string; metodo?: string; estado?: string }, nota: string) {
  await page.locator('#filtro-placa').fill(f.placa ?? '');
  await page.locator('#filtro-desde').fill(f.desde ?? '');
  await page.locator('#filtro-hasta').fill(f.hasta ?? '');
  await page.locator('#filtro-metodo').selectOption(f.metodo ?? '');
  await page.locator('#filtro-estado').selectOption(f.estado ?? '');
  const r = await conRespuesta(page, 'GET', '/pagos', () => page.getByRole('button', { name: 'Buscar', exact: true }).click(), nota);
  return { ...r, filas: await filasPagos(page) };
}

async function recaudoUI(page: Page, desde: string, hasta: string) {
  await page.locator('#desde').fill(desde);
  await page.locator('#hasta').fill(hasta);
  return conRespuesta(page, 'GET', '/reportes/recaudo', () => page.getByRole('button', { name: 'Consultar' }).click(), `pantalla Recaudo: del ${desde} al ${hasta}`);
}

const estadoPago = (nota: string, id: number) =>
  consulta(nota, `SELECT p.id, p.comprobante, p.estado, p.monto, p.valor_mensual, p.meses, p.anulado_en, u.nombre_usuario AS anulado_por, p.motivo_anulacion, m.pago_estado
    FROM pago p LEFT JOIN cuenta_usuario u ON u.id = p.anulado_por_cuenta_id LEFT JOIN mensualidad m ON m.pago_id = p.id WHERE p.id = $1`, [id]);

export const CASOS_PAGOS: Record<string, Funcion> = {
  'ME-05': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const r = await buscarPlaca(page, PLACA_INEXISTENTE);
    const aviso = await texto(page, '#placa-error');
    await captura(page);
    const api = await (await entrar('operador_prueba')).get(`/pagos/estado/${PLACA_INEXISTENTE}`, 'consultar ZZZ999 por la API');
    verificar(r.status === 404 && api.status === 404, `respuestas: pantalla ${r.status}, API ${api.status}`);
    verificar(aviso === `La placa ${PLACA_INEXISTENTE} no está registrada. Revísala o registra el vehículo en Vehículos.`, `la pantalla dice «${aviso}»`);
    c.anotar(`GET /pagos/estado/${PLACA_INEXISTENTE}: 404 «${api.body?.detail}». La pantalla dice «${aviso}», sin detalle técnico.`);
  },

  'ME-01': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const r = await buscarPlaca(page, placa('V-VIG'));
    const vence = sumarDias(E.hoy, 10);
    const tag = await etiqueta(page);
    const mensualidad = await dato(page, 'Mensualidad');
    const cliente = await dato(page, 'Cliente');
    const vehiculo = await dato(page, 'Vehículo');
    await captura(page);
    verificar(r.body.estado === 'VIGENTE' && r.body.vence === vence && r.body.dias_restantes === 10, `API: ${JSON.stringify({ estado: r.body.estado, vence: r.body.vence, dias: r.body.dias_restantes })}`);
    verificar(tag === 'Vigente' && mensualidad === `Vigente hasta el ${fechaCorta(vence)} · Faltan 10 días. Puede entrar.`, `pantalla: «${tag}», «${mensualidad}»`);
    verificar(cliente.startsWith('Cliente del Plan de Pruebas · CC 7003000001') && vehiculo.startsWith('CAMIONETA'), `cliente «${cliente}», vehículo «${vehiculo}»`);
    c.anotar(`Placa real: ${placaReal('V-VIG')}. Pantalla Pagos: etiqueta «${tag}»; Vehículo «${vehiculo}»; Cliente «${cliente}»; Mensualidad «${mensualidad}». API: VIGENTE, vence ${vence}, dias_restantes 10.`);
  },

  'ME-02': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const venc = await buscarPlaca(page, placa('V-VENC'));
    const vencio = sumarDias(E.hoy, -5);
    const tagVenc = await etiqueta(page);
    const textoVenc = await dato(page, 'Mensualidad');
    await captura(page, 'V-VENC');
    const sin = await buscarPlaca(page, placa('V-SIN'));
    const tagSin = await etiqueta(page);
    const textoSin = await dato(page, 'Mensualidad');
    await captura(page, 'V-SIN');
    verificar(venc.body.estado === 'VENCIDA' && venc.body.vence === vencio, `API V-VENC: ${venc.body.estado} ${venc.body.vence}`);
    verificar(tagVenc === 'Vencida' && textoVenc === `Venció el ${fechaCorta(vencio)}. No puede entrar hasta que pague.`, `pantalla V-VENC: «${tagVenc}», «${textoVenc}»`);
    verificar(sin.body.estado === 'SIN_MENSUALIDAD' && tagSin === 'Sin mensualidad' && textoSin === 'No tiene mensualidad. No puede entrar hasta que pague.',
      `V-SIN: API ${sin.body.estado}, pantalla «${tagSin}», «${textoSin}»`);
    c.anotar(`Placas reales: ${placaReal('V-VENC')} y ${placaReal('V-SIN')}.`);
    c.anotar(`V-VENC: etiqueta «${tagVenc}», «${textoVenc}» (API VENCIDA, vence ${vencio}). V-SIN: etiqueta «${tagSin}», «${textoSin}» (API SIN_MENSUALIDAD).`);
  },

  'ME-03': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const r = await buscarPlaca(page, placa('V-FUT'));
    const actual = await dato(page, 'Periodo actual');
    const adelante = await dato(page, 'Pagado hacia adelante');
    const tag = await etiqueta(page);
    await captura(page);
    const iniFut = sumarDias(E.hoy, 21);
    const finFut = finDePeriodo(iniFut, 1);
    const esperadoActual = `Del ${fechaCorta(sumarDias(E.hoy, -10))} al ${fechaCorta(sumarDias(E.hoy, 20))}`;
    const esperadoFuturo = `Del ${fechaCorta(iniFut)} al ${fechaCorta(finFut)} · ${E.pagos['V-FUT'].comprobante}`;
    verificar(actual === esperadoActual, `periodo actual «${actual}» (se esperaba «${esperadoActual}»)`);
    verificar(adelante === esperadoFuturo, `pagado hacia adelante «${adelante}» (se esperaba «${esperadoFuturo}»)`);
    verificar(r.body.periodos_futuros.length === 1 && r.body.periodo_actual?.fecha_fin === sumarDias(E.hoy, 20), `API: ${JSON.stringify(r.body.periodos_futuros)}`);
    c.anotar(`Placa real: ${placaReal('V-FUT')}. Etiqueta «${tag}». Periodo actual «${actual}» (periodo sin pago, insertado por SQL). Pagado hacia adelante «${adelante}» (pago registrado por la API al preparar).`);
  },

  'PA-07': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const p = placa('PA07');
    let resumen = { status: 0, body: {} as any };
    const posts = await solicitudesDurante(page, 'POST', '/pagos', async () => {
      await buscarPlaca(page, p);
      resumen = await revisarPago(page, 2, 'EFECTIVO');
    });
    const datos = {
      Placa: await dato(page, 'Placa', 'section.resumen'), Cliente: await dato(page, 'Cliente', 'section.resumen'),
      Periodo: await dato(page, 'Periodo', 'section.resumen'), Meses: await dato(page, 'Meses', 'section.resumen'),
      Método: await dato(page, 'Método', 'section.resumen'), 'Monto a pagar': await dato(page, 'Monto a pagar', 'section.resumen'),
    };
    await captura(page, 'resumen');
    const esperado = { Placa: `${p} · AUTOMOVIL`, Cliente: 'Cliente del Plan de Pruebas', Periodo: `Del ${fechaCorta(E.hoy)} al ${fechaCorta(finDePeriodo(E.hoy, 2))}`,
      Meses: '2 meses × $ 120.000', Método: 'Efectivo', 'Monto a pagar': '$ 240.000' };
    verificar(JSON.stringify(datos) === JSON.stringify(esperado), `resumen: ${JSON.stringify(datos)}`);
    const otros = await solicitudesDurante(page, 'POST', '/pagos', () => page.getByRole('button', { name: 'Volver y corregir' }).click());
    const sinResumen = await page.locator('#resumen-titulo').count();
    await captura(page);
    const api = await (await entrar('operador_prueba')).get(`/pagos?placa=${p}`, 'pagos del vehículo después de cancelar');
    const n = await pagosDe('pagos del vehículo en la base', 'PA07');
    verificar(posts + otros === 0 && sinResumen === 0, `se enviaron ${posts + otros} POST /pagos; resumen visible: ${sinResumen}`);
    verificar(api.body.total === 0 && n === 0, `pagos registrados: API ${api.body.total}, base ${n}`);
    c.anotar(`Resumen de ${p} (GET /pagos/cotizacion ${resumen.status}, no guarda nada): ${Object.entries(datos).map(([k, v]) => `${k} «${v}»`).join(', ')}.`);
    c.anotar(`«Volver y corregir» vuelve al formulario sin enviar ningún POST /pagos. GET /pagos?placa=${p}: total 0; en la base 0 pagos del vehículo.`);
  },

  'PA-04': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const op = await entrar('operador_prueba');
    await buscarPlaca(page, placa('PA04-1'));
    const opciones = (await page.locator('#meses option').allInnerTexts()).map((t) => t.trim());
    verificar(JSON.stringify(opciones) === JSON.stringify(['1 mes', '2 meses', '3 meses', '4 meses', '5 meses', '6 meses']), `opciones de meses: ${opciones.join(', ')}`);
    const api: string[] = [];
    for (const meses of [0, 7, 1.5]) {
      const r = await op.post('/pagos', { placa: placa('PA04-1'), meses, metodo: 'EFECTIVO', monto_confirmado: 120000 }, `registrar ${meses} meses por la API`);
      const cot = await op.get(`/pagos/cotizacion?placa=${placa('PA04-1')}&meses=${meses}`, `resumen de ${meses} meses por la API`);
      verificar(r.status === 422 && cot.status === 422, `${meses} meses: POST ${r.status}, resumen ${cot.status}`);
      api.push(`${meses} → 422`);
    }
    const ninguno = await pagosDe('pagos de PA04-1 después de los rechazos', 'PA04-1');
    verificar(ninguno === 0, `se crearon ${ninguno} pagos con meses inválidos`);
    await revisarPago(page, 1, 'EFECTIVO');
    const uno = await confirmarPago(page);
    await captura(page, '1_mes');
    await buscarPlaca(page, placa('PA04-6'));
    await revisarPago(page, 6, 'EFECTIVO');
    const seis = await confirmarPago(page);
    await captura(page, '6_meses');
    verificar(uno.status === 201 && uno.body.meses === 1 && uno.body.fecha_fin === finDePeriodo(E.hoy, 1) && uno.body.monto === 120000, `1 mes: ${uno.status} ${JSON.stringify(uno.body)}`);
    verificar(seis.status === 201 && seis.body.meses === 6 && seis.body.fecha_fin === finDePeriodo(E.hoy, 6) && seis.body.monto === 360000, `6 meses: ${seis.status} ${JSON.stringify(seis.body)}`);
    await periodos('periodos de PA04-1', 'PA04-1');
    await periodos('periodos de PA04-6', 'PA04-6');
    c.anotar(`La pantalla solo ofrece de 1 a 6 meses (lista: ${opciones.join(', ')}): 0, 7 y 1,5 no se pueden elegir. Por la API: ${api.join(', ')} (registro y resumen), sin crear pagos.`);
    c.anotar(`Desde la pantalla: ${placa('PA04-1')} 1 mes → 201 ${uno.body.comprobante} (${fechaCorta(uno.body.fecha_inicio)}–${fechaCorta(uno.body.fecha_fin)}, ${pesos(uno.body.monto)}); ${placa('PA04-6')} (MOTO) 6 meses → 201 ${seis.body.comprobante} (${fechaCorta(seis.body.fecha_inicio)}–${fechaCorta(seis.body.fecha_fin)}, ${pesos(seis.body.monto)}).`);
  },

  'PA-05': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const op = await entrar('operador_prueba');
    const p = placa('PA05');
    await buscarPlaca(page, p);
    const pantalla: string[] = [];
    await page.locator('#metodo').selectOption('TRANSFERENCIA');
    for (const [ref, nombre] of [['', 'transferencia sin referencia'], ['AB1', 'referencia de 3'], ['R'.repeat(31), 'referencia de 31']]) {
      await page.locator('#referencia').fill(ref);
      let enviadas = 0;
      enviadas += await solicitudesDurante(page, 'GET', '/pagos/cotizacion', async () => {
        enviadas += await solicitudesDurante(page, 'POST', '/pagos', () => page.getByRole('button', { name: 'Revisar pago' }).click());
      });
      const error = await texto(page, '#referencia-error');
      verificar(enviadas === 0 && !!error, `${nombre} en pantalla: ${enviadas} solicitudes, error «${error}»`);
      pantalla.push(`${nombre} → «${error}»`);
      if (ref === 'AB1') await captura(page, 'rechazo');
    }
    await page.locator('#metodo').selectOption('EFECTIVO');
    const campoEnEfectivo = await page.locator('#referencia').count();
    verificar(campoEnEfectivo === 0, 'en efectivo la pantalla muestra el campo de referencia');
    const intentos: [unknown, unknown, string][] = [
      ['TRANSFERENCIA', null, 'transferencia sin referencia'], ['TRANSFERENCIA', 'AB1', 'referencia de 3'], ['TRANSFERENCIA', 'R'.repeat(31), 'referencia de 31'],
      ['EFECTIVO', 'ABCD', 'efectivo con referencia'], ['CHEQUE', 'ABCD', 'método fuera de la lista (CHEQUE)'],
    ];
    const api: string[] = [];
    for (const [metodo, referencia, nombre] of intentos) {
      const r = await op.post('/pagos', { placa: p, meses: 1, metodo, referencia, monto_confirmado: 120000 }, `por la API: ${nombre}`);
      verificar(r.status === 422, `${nombre} por la API respondió ${r.status} (se esperaba 422)`);
      api.push(`${nombre} → 422`);
    }
    const ninguno = await pagosDe('pagos de PA05 después de los rechazos', 'PA05');
    verificar(ninguno === 0, `se crearon ${ninguno} pagos con datos inválidos`);
    await revisarPago(page, 1, 'TARJETA', 'TJ01');
    const cuatro = await confirmarPago(page);
    await captura(page);
    const treinta = await pagar(op, p, 1, 'TARJETA', 'T'.repeat(26) + '-030', 'tarjeta con referencia de 30 caracteres por la API');
    verificar(cuatro.status === 201 && cuatro.body.referencia === 'TJ01', `referencia de 4: ${cuatro.status} ${JSON.stringify(cuatro.body)}`);
    verificar(treinta.referencia.length === 30, `referencia de 30: ${JSON.stringify(treinta)}`);
    await periodos('pagos de PA05', 'PA05');
    c.anotar(`Pantalla: ${pantalla.join('; ')} (se rechazan sin enviar nada). En efectivo el campo de referencia no aparece, así que «efectivo con referencia» no se puede escribir en la pantalla.`);
    c.anotar(`Por la API los cinco intentos responden 422: ${api.join(', ')}; ningún pago creado. Tarjeta con referencia de 4 (TJ01, desde la pantalla) → 201 ${cuatro.body.comprobante}; de 30 (por la API) → 201 ${treinta.comprobante}.`);
  },

  'PA-06': async (c) => {
    const op = await entrar('operador_prueba');
    const p = placa('PA06');
    const tope = topeDeAdelanto(E.hoy);
    const seis = await pagar(op, p, 6, 'EFECTIVO', null, 'preparación: 6 meses');
    const uno = await pagar(op, p, 1, 'EFECTIVO', null, 'preparación: 1 mes más (vence a 7 meses de hoy)');
    const finActual = uno.fecha_fin;
    verificar(finActual === finDePeriodo(sumarDias(finDePeriodo(E.hoy, 6), 1), 1), `los periodos preparados terminan el ${finActual}`);
    const inicio = sumarDias(finActual, 1);
    const cot = await op.get(`/pagos/cotizacion?placa=${p}&meses=6`, 'resumen de 6 meses más');
    const r = await op.post('/pagos', { placa: p, meses: 6, metodo: 'EFECTIVO', monto_confirmado: 720000 }, 'intentar pagar 6 meses más');
    const finSeis = finDePeriodo(inicio, 6);
    const mensaje = `El pago dejaría la mensualidad vigente hasta el ${fechaCorta(finSeis)}: lo máximo es 12 meses desde hoy (${fechaCorta(tope)}). Registra menos meses.`;
    verificar(finSeis > tope, `6 meses más terminarían el ${finSeis}, dentro del tope ${tope}: la precondición no sirve`);
    verificar(r.status === 409 && r.body.detail === mensaje && cot.status === 409, `6 meses más: resumen ${cot.status}, registro ${r.status} «${r.body?.detail}»`);
    const caben = [5, 4, 3, 2, 1].find((m) => finDePeriodo(inicio, m) <= tope)!;
    const ok = await pagar(op, p, caben, 'EFECTIVO', null, `pagar ${caben} meses (fin dentro del tope)`);
    verificar(ok.fecha_fin <= tope && ok.fecha_fin === finDePeriodo(inicio, caben), `${caben} meses: fin ${ok.fecha_fin}, tope ${tope}`);
    await periodos('periodos de PA06', 'PA06');
    c.anotar(`Preparación por la API: ${p} con 6 meses y 1 mes pagados, vigente hasta el ${fechaCorta(finActual)} (unos 7 meses desde hoy). Tope: ${fechaCorta(tope)}.`);
    c.anotar(`6 meses más (terminarían el ${fechaCorta(finSeis)}): el resumen y el registro responden 409 «${r.body.detail}». ${caben} meses (hasta el ${fechaCorta(ok.fecha_fin)}, dentro del tope) → 201 ${ok.comprobante}.`);
  },

  'PA-01': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const p = placa('V-VENC');
    await buscarPlaca(page, p);
    await revisarPago(page, 1, 'EFECTIVO');
    const periodo = await dato(page, 'Periodo', 'section.resumen');
    const monto = await dato(page, 'Monto a pagar', 'section.resumen');
    const r = await confirmarPago(page);
    const aviso = await texto(page, 'section[aria-label="Pago registrado"] p.notice.success');
    const responsable = await dato(page, 'Registrado por', 'app-comprobante');
    const codigo = await texto(page, 'app-comprobante .codigo');
    await captura(page);
    const fin = finDePeriodo(E.hoy, 1);
    verificar(r.status === 201 && r.body.fecha_inicio === E.hoy && r.body.fecha_fin === fin, `API: ${r.status} ${r.body?.fecha_inicio}–${r.body?.fecha_fin} (se esperaba ${E.hoy}–${fin})`);
    verificar(r.body.monto === 120000 && r.body.valor_mensual === 120000 && monto === '$ 120.000', `monto ${r.body.monto}, pantalla «${monto}»`);
    verificar(responsable === OPERADOR && r.body.registrado_por === OPERADOR, `responsable «${responsable}»`);
    const n = await contar('pagos con ese número de comprobante', 'SELECT count(*) FROM pago WHERE comprobante = $1', [r.body.comprobante]);
    verificar(/^RC-\d{6}$/.test(codigo) && codigo === r.body.comprobante && n === 1, `comprobante «${codigo}», ${n} pago(s) con ese número`);
    E.pagos['PA-01'] = r.body;
    await estadoPago('pago registrado en la base', r.body.id);
    c.anotar(`Placa real: ${placaReal('V-VENC')}. Resumen: «${periodo}», «${monto}». POST /pagos → 201.`);
    c.anotar(`El periodo va del ${fechaCorta(E.hoy)} (hoy) al ${fechaCorta(fin)} (día anterior a la misma fecha del mes siguiente); monto $ 120.000 = tarifa × 1. Aviso «${aviso}». Comprobante ${codigo} (único en la base), «Registrado por ${responsable}».`);
  },

  'PA-02': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const p = placa('V-VIG');
    await buscarPlaca(page, p);
    const finActual = sumarDias(E.hoy, 10);
    await revisarPago(page, 2, 'TRANSFERENCIA', 'TRX-PP03-0001');
    const periodo = await dato(page, 'Periodo', 'section.resumen');
    const r = await confirmarPago(page);
    await captura(page);
    const inicio = sumarDias(finActual, 1);
    const fin = finDePeriodo(inicio, 2);
    verificar(r.status === 201 && r.body.fecha_inicio === inicio && r.body.fecha_fin === fin, `API: ${r.status} ${r.body?.fecha_inicio}–${r.body?.fecha_fin} (se esperaba ${inicio}–${fin})`);
    verificar(r.body.monto === 280000 && r.body.valor_mensual === 140000 && r.body.meses === 2, `monto ${r.body.monto}`);
    const filas = await periodos('periodos de V-VIG: el nuevo empieza el día siguiente del anterior', 'V-VIG');
    verificar(filas.length === 2 && sumarDias(filas[0].fin, 1) === filas[1].inicio, `periodos: ${JSON.stringify(filas)}`);
    E.pagos['PA-02'] = r.body;
    c.anotar(`Placa real: ${placaReal('V-VIG')}; su periodo vigente vence el ${fechaCorta(finActual)}. Pago de 2 meses por transferencia (referencia TRX-PP03-0001) → 201 ${r.body.comprobante}; resumen «${periodo}».`);
    c.anotar(`El nuevo periodo empieza el ${fechaCorta(inicio)} (día siguiente al vencimiento) y termina el ${fechaCorta(fin)}; en la base los dos periodos quedan seguidos, sin días perdidos ni superposición. Monto $ 280.000 = $ 140.000 × 2.`);
  },

  'TA-05': async (c) => {
    const admin = await entrar('admin_prueba');
    const op = await entrar('operador_prueba');
    const anterior = E.pagos['PA-01'];
    const antes = await admin.get(`/pagos/${anterior.id}`, 'pago anterior de AUTOMOVIL (PA-01)');
    try {
      const nueva = await fijarTarifa(admin, 'AUTOMOVIL', 130000, 'actualizar la tarifa de AUTOMOVIL a $ 130.000');
      const despues = await admin.get(`/pagos/${anterior.id}`, 'el pago anterior después del cambio');
      const nuevo = await pagar(op, placa('TA05'), 1, 'EFECTIVO', null, `pago nuevo de un AUTOMOVIL (${placa('TA05')})`);
      await consulta('montos guardados', 'SELECT comprobante, tipo_vehiculo, valor_mensual, meses, monto, tarifa_id FROM pago WHERE id IN ($1, $2) ORDER BY id', [anterior.id, nuevo.id]);
      verificar(antes.body.monto === 120000 && despues.body.monto === 120000 && despues.body.valor_mensual === 120000, `el pago anterior pasó de ${antes.body.monto} a ${despues.body.monto}`);
      verificar(nuevo.monto === 130000 && nuevo.valor_mensual === 130000, `el pago nuevo es de ${nuevo.monto}`);
      c.anotar(`Pago anterior ${anterior.comprobante} (AUTOMOVIL, PA-01): $ 120.000. Se actualizó AUTOMOVIL a $ 130.000 (tarifa ${nueva.id}).`);
      c.anotar(`Después del cambio, ${anterior.comprobante} conserva $ 120.000 (valor mensual $ 120.000). El pago nuevo de ${placa('TA05')}, 1 mes, se calculó con la tarifa nueva: ${nuevo.comprobante} por $ 130.000.`);
    } finally {
      await fijarTarifa(admin, 'AUTOMOVIL', 120000, 'restaurar AUTOMOVIL a $ 120.000 (independencia de los casos)');
    }
    c.anotar('Al terminar, AUTOMOVIL vuelve a $ 120.000 para los casos siguientes.');
  },

  'PA-08': async (c) => {
    const [a, b] = await Promise.all([entrar('operador_prueba'), entrar('admin_dos')]);
    const p = placa('PA08');
    const cuerpo = { placa: p, meses: 1, metodo: 'EFECTIVO', monto_confirmado: 120000 };
    const [ra, rb] = await Promise.all([
      a.post('/pagos', cuerpo, 'pago simultáneo (sesión de operador_prueba)'),
      b.post('/pagos', cuerpo, 'pago simultáneo (sesión de admin_dos)'),
    ]);
    verificar(ra.status === 201 && rb.status === 201, `respuestas: ${ra.status} y ${rb.status}`);
    const filas = await periodos('periodos de PA08', 'PA08');
    const solapan = await contar('periodos que se superponen', `SELECT count(*) FROM mensualidad x JOIN mensualidad y ON x.vehiculo_id = y.vehiculo_id AND x.id < y.id
      AND daterange(x.fecha_inicio, x.fecha_fin, '[]') && daterange(y.fecha_inicio, y.fecha_fin, '[]') WHERE x.vehiculo_id = $1`, [E.vehiculoId.PA08]);
    verificar(filas.length === 2 && filas[0].inicio === E.hoy && filas[0].fin === finDePeriodo(E.hoy, 1) && filas[1].inicio === sumarDias(filas[0].fin, 1), `periodos: ${JSON.stringify(filas)}`);
    verificar(solapan === 0 && ra.body.comprobante !== rb.body.comprobante, `superposiciones ${solapan}; comprobantes ${ra.body.comprobante} y ${rb.body.comprobante}`);
    const [primero, segundo] = [ra.body, rb.body].sort((x, y) => x.fecha_inicio.localeCompare(y.fecha_inicio));
    E.pagos['PA08-1'] = primero;
    E.pagos['PA08-2'] = segundo;
    c.anotar(`Dos sesiones (operador_prueba y admin_dos) enviaron a la vez un pago de 1 mes de ${p}: ambos 201 (${ra.body.comprobante} y ${rb.body.comprobante}).`);
    c.anotar(`Periodos consecutivos: ${fechaCorta(filas[0].inicio)}–${fechaCorta(filas[0].fin)} (${filas[0].comprobante}) y ${fechaCorta(filas[1].inicio)}–${fechaCorta(filas[1].fin)} (${filas[1].comprobante}); el segundo empieza el día siguiente al fin del primero, sin superposición.`);
  },

  'PA-09': async (c) => {
    const op = await entrar('operador_prueba');
    const admin = await entrar('admin_prueba');
    const p = placa('PA09');
    const cot1 = await op.get(`/pagos/cotizacion?placa=${p}&meses=1`, 'resumen: monto calculado');
    const paso1 = await op.post('/pagos', { placa: p, meses: 1, metodo: 'EFECTIVO', monto_confirmado: 1000 }, 'paso 1: monto confirmado distinto del calculado ($ 1.000)');
    const n1 = await pagosDe('pagos después del paso 1', 'PA09');
    verificar(cot1.body.monto === 140000 && paso1.status === 409 && paso1.body.detail.includes('$ 140.000') && n1 === 0, `paso 1: ${paso1.status} «${paso1.body?.detail}», pagos ${n1}`);
    let paso2: any, paso3: any, n2 = -1;
    try {
      const cot2 = await op.get(`/pagos/cotizacion?placa=${p}&meses=1`, 'paso 2: resumen ($ 140.000)');
      await fijarTarifa(admin, 'CAMIONETA', 150000, 'paso 2: el administrador cambia CAMIONETA a $ 150.000');
      paso2 = await op.post('/pagos', { placa: p, meses: 1, metodo: 'EFECTIVO', monto_confirmado: cot2.body.monto }, 'paso 2: confirmar con el monto anterior ($ 140.000)');
      n2 = await pagosDe('pagos después del paso 2', 'PA09');
      paso3 = await op.post('/pagos', { placa: p, meses: 1, metodo: 'EFECTIVO', monto_confirmado: 150000 }, 'paso 3: confirmar con el monto correcto ($ 150.000)');
    } finally {
      await fijarTarifa(admin, 'CAMIONETA', 140000, 'restaurar CAMIONETA a $ 140.000 (independencia de los casos)');
    }
    verificar(paso2.status === 409 && paso2.body.detail.includes('$ 150.000') && n2 === 0, `paso 2: ${paso2.status} «${paso2.body?.detail}», pagos ${n2}`);
    verificar(paso3.status === 201, `paso 3: ${paso3.status} ${JSON.stringify(paso3.body)}`);
    const guardado = await consulta('paso 4: monto guardado', 'SELECT comprobante, valor_mensual, meses, monto, monto = valor_mensual * meses AS calculado FROM pago WHERE id = $1', [paso3.body.id]);
    verificar(guardado[0].monto === 150000 && guardado[0].calculado === true, `monto guardado: ${JSON.stringify(guardado[0])}`);
    c.anotar(`Paso 1 (${p}, monto confirmado $ 1.000 con el calculado en $ 140.000): 409 «${paso1.body.detail}»; ningún pago.`);
    c.anotar(`Paso 2 (resumen de $ 140.000, el administrador cambia CAMIONETA a $ 150.000 y se confirma con $ 140.000): 409 «${paso2.body.detail}»; ningún pago.`);
    c.anotar(`Paso 3 (monto correcto $ 150.000): 201 ${paso3.body.comprobante}. Paso 4: en la base monto $ 150.000 = valor mensual $ 150.000 × 1 mes (el calculado por el servidor). CAMIONETA vuelve a $ 140.000.`);
  },

  'PA-10': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const p = placa('V-SIN');
    const primera = await registrarEntradaUI(page, p);
    await captura(page, 'rechazo');
    verificar(primera.status === 409 && primera.body?.detail === SIN_MENSUALIDAD && primera.aviso.includes(SIN_MENSUALIDAD), `primera entrada: ${primera.status} «${primera.aviso}»`);
    await buscarPlaca(page, p);
    await revisarPago(page, 1, 'EFECTIVO');
    const pago = await confirmarPago(page);
    verificar(pago.status === 201, `pago: ${pago.status}`);
    const segunda = await registrarEntradaUI(page, p);
    await captura(page);
    verificar(segunda.status === 201, `segunda entrada: ${segunda.status} «${segunda.aviso}»`);
    await consulta('estancia abierta de V-SIN', `SELECT e.id, v.placa, c.codigo AS celda, e.entrada, e.salida FROM estancia e JOIN vehiculo v ON v.id = e.vehiculo_id
      JOIN celda c ON c.id = e.celda_id WHERE v.placa = $1`, [p]);
    c.anotar(`Placa real: ${placaReal('V-SIN')}. Primera entrada (pantalla Control de acceso): 409, la pantalla dice «${primera.aviso}».`);
    c.anotar(`Pago de 1 mes desde la pantalla Pagos → 201 ${pago.body.comprobante}. Entrada de nuevo, de inmediato: 201, «${segunda.aviso}».`);
  },

  'AN-01': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba');
    const pago = E.pagos.AN01;
    const p = placa('AN01');
    const op = await entrar('operador_prueba');
    const dentro = await op.get(`/estancias/vehiculo/${p}`, 'el vehículo está fuera del parqueadero');
    verificar(dentro.status === 200 && !dentro.body.esta_dentro, `${p} está dentro`);
    await irA(page, `/consultas/pagos/${pago.id}`);
    await page.getByRole('button', { name: 'Anular pago' }).click();
    const motivo = 'El cliente pidió la devolución: pago registrado por error.';
    await page.locator('#motivo').fill(motivo);
    await page.getByRole('button', { name: 'Continuar' }).click();
    const dialogo = page.getByRole('alertdialog');
    await dialogo.waitFor();
    const confirmacion = ((await dialogo.locator('#confirmacion-mensaje').textContent()) ?? '').replace(/\s+/g, ' ').trim();
    await captura(page, 'confirmacion');
    const r = await conRespuesta(page, 'POST', `/pagos/${pago.id}/anular`, () => dialogo.getByRole('button', { name: 'Sí, anular el pago' }).click(), 'pantalla Detalle del pago: confirmar la anulación');
    await page.locator('.sello').waitFor();
    const linea = await texto(page, 'section.anulacion p:first-child');
    const lineaMotivo = await texto(page, 'section.anulacion p:nth-child(2)');
    await captura(page);
    const fila = await estadoPago('el pago en la base: ANULADO, no eliminado', pago.id);
    verificar(r.status === 200 && fila.length === 1 && fila[0].estado === 'ANULADO' && fila[0].pago_estado === 'ANULADO', `anulación: ${r.status}; base ${JSON.stringify(fila)}`);
    verificar(fila[0].anulado_por === 'admin_prueba' && !!fila[0].anulado_en && fila[0].motivo_anulacion === motivo, `datos de la anulación: ${JSON.stringify(fila[0])}`);
    verificar(linea.startsWith(`Anulado por ${ADMIN} el `) && FECHA_HORA.test(linea) && lineaMotivo === `Motivo: ${motivo}`, `comprobante: «${linea}» «${lineaMotivo}»`);
    const entrada = await op.post('/estancias/entrada', { placa: p }, 'registrar la entrada del vehículo');
    verificar(entrada.status === 409 && entrada.body.detail === SIN_MENSUALIDAD, `entrada: ${entrada.status} «${entrada.body?.detail}»`);
    c.anotar(`Vehículo ${p} (fuera del parqueadero), pago ${pago.comprobante}. Confirmación: «${confirmacion}». POST /pagos/${pago.id}/anular → 200.`);
    c.anotar(`El comprobante muestra «PAGO ANULADO», «${linea}» y «${lineaMotivo}». En la base el pago sigue existiendo, ANULADO, con anulado_por admin_prueba, la fecha y el motivo; su periodo queda ANULADO.`);
    c.anotar(`La entrada de ${p} responde 409 «${entrada.body.detail}».`);
  },

  'ME-04': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const p = placa('AN01');
    const r = await buscarPlaca(page, p);
    const tag = await etiqueta(page);
    const mensualidad = await dato(page, 'Mensualidad');
    const anulados = await dato(page, 'Periodos anulados');
    const actual = await page.locator('dl.datos dt', { hasText: 'Periodo actual' }).count();
    await captura(page);
    const pago = E.pagos.AN01;
    const esperado = `Del ${fechaCorta(pago.fecha_inicio)} al ${fechaCorta(pago.fecha_fin)} · ${pago.comprobante} · Anulado (no cuenta)`;
    verificar(r.body.estado === 'SIN_MENSUALIDAD' && r.body.periodo_actual === null && r.body.periodos_anulados.length === 1, `API: ${JSON.stringify({ estado: r.body.estado, actual: r.body.periodo_actual, anulados: r.body.periodos_anulados })}`);
    verificar(tag === 'Sin mensualidad' && anulados === esperado && actual === 0, `pantalla: «${tag}», anulados «${anulados}», periodo actual ${actual}`);
    c.anotar(`Vehículo ${p} (pago anulado en AN-01). Etiqueta «${tag}», «${mensualidad}». Periodos anulados: «${anulados}». No aparece periodo actual: el anulado no cuenta (API SIN_MENSUALIDAD).`);
  },

  'AN-04': async (c) => {
    const admin = await entrar('admin_dos');
    const pago = E.pagos.AN01;
    const antes = await estadoPago('el pago antes del segundo intento', pago.id);
    const r = await admin.post(`/pagos/${pago.id}/anular`, { motivo: 'Segundo intento de anulación del mismo pago.' }, 'anular de nuevo un pago ya anulado');
    const despues = await estadoPago('el pago después del segundo intento', pago.id);
    verificar(r.status === 409, `respondió ${r.status}`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues), 'cambiaron los datos de la anulación');
    c.anotar(`POST /pagos/${pago.id}/anular (admin_dos): 409 «${r.body.detail}». El pago conserva la primera anulación: admin_prueba, ${new Date(despues[0].anulado_en).toISOString()} y el mismo motivo.`);
  },

  'AN-02': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba');
    const admin = await entrar('admin_prueba');
    const pago = E.pagos['AN02-10'];
    await irA(page, `/consultas/pagos/${pago.id}`);
    await page.getByRole('button', { name: 'Anular pago' }).click();
    const invalidos: [string, string][] = [['Nueve car', 'motivo de 9'], ['M'.repeat(201), 'motivo de 201'], ['            ', 'solo espacios']];
    const pantalla: string[] = [];
    for (const [motivo, nombre] of invalidos) {
      await page.locator('#motivo').fill(motivo);
      const enviadas = await solicitudesDurante(page, 'POST', `/pagos/${pago.id}/anular`, () => page.getByRole('button', { name: 'Continuar' }).click());
      const error = await texto(page, '#motivo-error');
      const dialogo = await page.getByRole('alertdialog').count();
      verificar(enviadas === 0 && dialogo === 0 && !!error, `${nombre} en pantalla: ${enviadas} solicitudes, confirmación ${dialogo}, error «${error}»`);
      pantalla.push(`${nombre} → «${error}»`);
      if (motivo === 'Nueve car') await captura(page, 'rechazo');
    }
    const api: string[] = [];
    for (const [motivo, nombre] of invalidos) {
      const r = await admin.post(`/pagos/${pago.id}/anular`, { motivo }, `por la API: ${nombre}`);
      verificar(r.status === 422, `${nombre} por la API respondió ${r.status}`);
      api.push(`${nombre} → 422`);
    }
    const sigue = await estadoPago('el pago sigue válido', pago.id);
    verificar(sigue[0].estado === 'VALIDO', `el pago quedó ${sigue[0].estado}`);
    await page.locator('#motivo').fill('Duplicado.');
    await page.getByRole('button', { name: 'Continuar' }).click();
    const r10 = await conRespuesta(page, 'POST', `/pagos/${pago.id}/anular`, () => page.getByRole('alertdialog').getByRole('button', { name: 'Sí, anular el pago' }).click(), 'pantalla: anular con un motivo de 10 caracteres');
    await page.locator('.sello').waitFor();
    await captura(page);
    const motivo200 = ('Motivo de doscientos caracteres para verificar el límite superior de la anulación. ').repeat(3).slice(0, 199) + '.';
    const r200 = await admin.post(`/pagos/${E.pagos['AN02-200'].id}/anular`, { motivo: motivo200 }, 'otro pago: anular con un motivo de 200 caracteres');
    const filas = await consulta('motivos guardados', 'SELECT comprobante, estado, motivo_anulacion, length(motivo_anulacion) AS largo FROM pago WHERE id IN ($1, $2) ORDER BY id', [pago.id, E.pagos['AN02-200'].id]);
    verificar(r10.status === 200 && r200.status === 200 && filas.map((f) => Number(f.largo)).join() === '10,200', `motivo de 10: ${r10.status}; de 200: ${r200.status}; ${JSON.stringify(filas)}`);
    c.anotar(`Pantalla (${pago.comprobante}): ${pantalla.join('; ')}; ninguno llega a la confirmación. Por la API: ${api.join(', ')}. El pago sigue VALIDO.`);
    c.anotar(`Motivo de 10 caracteres («Duplicado.») desde la pantalla → 200, ${pago.comprobante} ANULADO. En otro pago (${E.pagos['AN02-200'].comprobante}) el motivo de 200 caracteres → 200.`);
  },

  'AN-03': async (c) => {
    const admin = await entrar('admin_prueba');
    const [primero, segundo] = [E.pagos['PA08-1'], E.pagos['PA08-2']];
    const r = await admin.post(`/pagos/${primero.id}/anular`, { motivo: 'Intento de anular el primer periodo de dos.' }, 'anular el pago del primer periodo');
    const filas = await consulta('los dos pagos siguen válidos', 'SELECT comprobante, estado FROM pago WHERE id IN ($1, $2) ORDER BY id', [primero.id, segundo.id]);
    verificar(r.status === 409 && r.body.detail.startsWith('Solo se puede anular el pago del último periodo del vehículo.'), `respondió ${r.status} «${r.body?.detail}»`);
    verificar(filas.every((f) => f.estado === 'VALIDO'), `estados: ${JSON.stringify(filas)}`);
    c.anotar(`${placa('PA08')} tiene dos periodos pagados seguidos (PA-08). Anular ${primero.comprobante}: 409 «${r.body.detail}». ${primero.comprobante} y ${segundo.comprobante} siguen VALIDO.`);
  },

  'AN-05': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const pago = E.pagos['PA08-2'];
    await irA(page, `/consultas/pagos/${pago.id}`);
    await page.locator('app-comprobante').waitFor();
    const boton = await page.getByRole('button', { name: 'Anular pago' }).count();
    await captura(page);
    const r = await (await entrar('operador_prueba')).post(`/pagos/${pago.id}/anular`, { motivo: 'El operador intenta anular este pago.' }, 'el operador envía la anulación');
    const fila = await estadoPago('el pago sigue válido', pago.id);
    verificar(boton === 0, 'el operador ve la acción «Anular pago»');
    verificar(r.status === 403 && fila[0].estado === 'VALIDO', `API ${r.status}; estado ${fila[0].estado}`);
    c.anotar(`El operador abre el detalle de ${pago.comprobante} (anulable: último periodo de ${placa('PA08')}) y no ve «Anular pago». POST /pagos/${pago.id}/anular: 403 «${r.body?.detail}». El pago sigue VALIDO.`);
  },

  'AN-06': async (c) => {
    const valido = E.pagos['PA-01'];
    const anulado = E.pagos.AN01;
    const foto = `SELECT p.id, p.comprobante, p.estado, p.monto, p.valor_mensual, p.meses, p.anulado_en, p.anulado_por_cuenta_id, p.motivo_anulacion,
      m.fecha_inicio::text, m.fecha_fin::text, m.pago_estado FROM pago p JOIN mensualidad m ON m.pago_id = p.id WHERE p.id IN ($1, $2) ORDER BY p.id`;
    const antes = await consulta('pagos antes de los intentos (uno válido y uno anulado)', foto, [valido.id, anulado.id]);
    const intentos = [
      await intentoBd('1. DELETE de un pago', 'DELETE FROM pago WHERE id = $1', [valido.id]),
      await intentoBd('2a. cambiar el monto de un pago (con un valor mensual coherente)', 'UPDATE pago SET valor_mensual = valor_mensual + 1, monto = (valor_mensual + 1) * meses WHERE id = $1', [valido.id]),
      await intentoBd('2b. cambiar las fechas del periodo de un pago', 'UPDATE mensualidad SET fecha_fin = fecha_fin + 1 WHERE pago_id = $1', [valido.id]),
      await intentoBd('3. devolver un pago anulado a VALIDO', "UPDATE pago SET estado = 'VALIDO', anulado_en = NULL, anulado_por_cuenta_id = NULL, motivo_anulacion = NULL WHERE id = $1", [anulado.id]),
    ];
    const despues = await consulta('pagos después de los intentos', foto, [valido.id, anulado.id]);
    verificar(intentos.every((i) => i.rechazada), `la base aceptó alguna operación: ${JSON.stringify(intentos)}`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues), 'los pagos cambiaron');
    const nombres = ['DELETE', 'cambio de monto', 'cambio de fechas del periodo', 'ANULADO → VALIDO'];
    c.anotar(`Pagos ${valido.comprobante} (válido) y ${anulado.comprobante} (anulado). La base rechaza: ${intentos.map((i, k) => `${nombres[k]} (SQLSTATE ${i.codigo}: «${i.mensaje}»)`).join('; ')}.`);
    c.anotar('Los dos pagos y sus periodos quedan idénticos.');
  },

  'PA-11': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/consultas/pagos');
    const admin = await entrar('admin_prueba');
    await page.locator('table tbody tr').first().waitFor();
    const columnas = (await page.locator('table thead th').allInnerTexts()).map((t) => t.trim());
    const esperadas = ['Comprobante', 'Fecha (Bogotá)', 'Placa', 'Cliente', 'Periodo', 'Meses', 'Monto', 'Método', 'Estado', 'Responsable'];
    verificar(JSON.stringify(columnas) === JSON.stringify(esperadas), `columnas: ${columnas.join(', ')}`);
    const porPlaca = await filtrarPagos(page, { placa: placa('PA08') }, `filtro por placa ${placa('PA08')}`);
    verificar(porPlaca.filas.length === 2 && porPlaca.filas.every((f) => f[2] === placa('PA08')), `por placa: ${JSON.stringify(porPlaca.filas)}`);
    const porMetodo = await filtrarPagos(page, { desde: E.hoy, hasta: E.hoy, metodo: 'TRANSFERENCIA' }, 'filtro por rango de hoy y método Transferencia');
    verificar(porMetodo.filas.length > 0 && porMetodo.filas.every((f) => f[7] === 'Transferencia' && f[1].startsWith(fechaCorta(E.hoy))), `por método: ${JSON.stringify(porMetodo.filas)}`);
    await captura(page, 'metodo');
    const porEstado = await filtrarPagos(page, { estado: 'ANULADO' }, 'filtro por estado Anulado');
    verificar(porEstado.filas.length >= 2 && porEstado.filas.every((f) => f[8] === 'Anulado'), `por estado: ${JSON.stringify(porEstado.filas)}`);
    await captura(page, 'anulados');
    const nada = await filtrarPagos(page, { placa: placa('PA08'), estado: 'ANULADO' }, 'filtros sin coincidencias');
    const vacio = await texto(page, 'section[aria-label="Listado de pagos"] p.empty');
    await captura(page);
    verificar(nada.status === 200 && nada.body.total === 0 && nada.body.items.length === 0 && vacio === 'No hay pagos que coincidan con los filtros.', `sin coincidencias: ${nada.status} ${JSON.stringify(nada.body)} «${vacio}»`);
    const viejo = await admin.get('/pagos?desde=2020-01-01&hasta=2020-01-31', 'rango de fechas sin pagos por la API');
    const totales = await consulta('comprobación en la base', `SELECT count(*) FILTER (WHERE estado = 'ANULADO') AS anulados,
      count(*) FILTER (WHERE metodo = 'TRANSFERENCIA' AND (fecha AT TIME ZONE 'America/Bogota')::date = $1::date) AS transferencias_hoy FROM pago`, [E.hoy]);
    verificar(Number(totales[0].anulados) === porEstado.body.total && Number(totales[0].transferencias_hoy) === porMetodo.body.total, `la base no coincide: ${JSON.stringify(totales)}`);
    verificar(viejo.status === 200 && viejo.body.total === 0, `rango 2020: ${viejo.status} ${viejo.body.total}`);
    const ejemplo = porPlaca.filas[0].join(' | ');
    c.anotar(`Columnas: ${columnas.join(', ')}. Ejemplo de fila: «${ejemplo}».`);
    c.anotar(`Placa ${placa('PA08')}: ${porPlaca.filas.length} pagos, solo de esa placa. Rango de hoy + Transferencia: ${porMetodo.filas.length}, todos de transferencia y de hoy. Estado Anulado: ${porEstado.filas.length}, todos anulados (igual que la base).`);
    c.anotar(`Sin coincidencias (${placa('PA08')} + Anulado): API 200 con lista vacía y la pantalla dice «${vacio}». Rango 01/01/2020–31/01/2020 por la API: 200, total 0.`);
  },

  'PA-12': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba');
    const valido = E.pagos['PA-01'];
    await irA(page, `/consultas/pagos/${valido.id}`);
    await page.locator('app-comprobante').waitFor();
    const etiquetas = ['Fecha del pago', 'Placa', 'Cliente', 'Periodo', 'Meses', 'Valor mensual', 'Método', 'Registrado por', 'Estado', 'Total pagado'];
    const datosValido: Record<string, string> = {};
    for (const e of etiquetas) datosValido[e] = await dato(page, e, 'app-comprobante');
    const codigo = await texto(page, 'app-comprobante .codigo');
    await captura(page, 'valido');
    verificar(codigo === valido.comprobante && datosValido.Estado === 'Válido' && datosValido['Total pagado'] === '$ 120.000' && datosValido['Registrado por'] === OPERADOR
      && datosValido.Periodo === `Del ${fechaCorta(valido.fecha_inicio)} al ${fechaCorta(valido.fecha_fin)}` && FECHA_HORA.test(datosValido['Fecha del pago']), `comprobante válido: ${codigo} ${JSON.stringify(datosValido)}`);
    const anulado = E.pagos.AN01;
    await irA(page, `/consultas/pagos/${anulado.id}`);
    await page.locator('app-comprobante').waitFor();
    const sello = await texto(page, '.sello');
    const linea = await texto(page, 'section.anulacion p:first-child');
    const motivo = await texto(page, 'section.anulacion p:nth-child(2)');
    const estado = await dato(page, 'Estado', 'app-comprobante');
    await captura(page, 'anulado');
    verificar(sello === 'PAGO ANULADO' && estado === 'Anulado' && linea.startsWith(`Anulado por ${ADMIN} el`) && FECHA_HORA.test(linea) && motivo.startsWith('Motivo: '), `anulado: «${sello}» «${linea}» «${motivo}»`);
    c.anotar(`Detalle de ${codigo}: ${etiquetas.map((e) => `${e} «${datosValido[e]}»`).join(', ')}.`);
    c.anotar(`Detalle de ${anulado.comprobante}: el mismo comprobante con «${sello}», Estado «${estado}», «${linea}» y «${motivo}».`);
  },

  'PA-13': async (c, browser) => {
    const tipos = await consulta('tipo de las columnas de dinero', `SELECT column_name, data_type, numeric_precision, numeric_scale FROM information_schema.columns
      WHERE table_name IN ('pago', 'tarifa') AND column_name IN ('monto', 'valor_mensual', 'valor') ORDER BY table_name, column_name`);
    verificar(tipos.length === 3 && tipos.every((t) => t.data_type === 'integer' && Number(t.numeric_scale) === 0), `tipos: ${JSON.stringify(tipos)}`);
    const page = await conSesionUI(browser, 'admin_prueba');
    const comparacion: string[] = [];
    for (const clave of ['PA-01', 'PA-02']) {
      const pago = E.pagos[clave];
      const fila = await consulta(`monto guardado de ${pago.comprobante}`, 'SELECT comprobante, monto FROM pago WHERE id = $1', [pago.id]);
      await irA(page, `/consultas/pagos/${pago.id}`);
      await page.locator('app-comprobante').waitFor();
      const mostrado = await dato(page, 'Total pagado', 'app-comprobante');
      verificar(mostrado === pesos(fila[0].monto) && /^\$ \d{1,3}(\.\d{3})*$/.test(mostrado), `${pago.comprobante}: base ${fila[0].monto}, pantalla «${mostrado}»`);
      comparacion.push(`${pago.comprobante}: base ${fila[0].monto} → pantalla «${mostrado}»`);
      if (clave === 'PA-02') await captura(page);
    }
    c.anotar(`Columnas de dinero: ${tipos.map((t) => `${t.column_name} ${t.data_type} (escala ${t.numeric_scale})`).join(', ')}: entero exacto, sin decimales.`);
    c.anotar(`Montos guardados y mostrados: ${comparacion.join('; ')}.`);
  },

  'RE-01': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/consultas/recaudo');
    const r = await recaudoUI(page, E.hoy, E.hoy);
    await page.locator('#totales-titulo').waitFor();
    const total = await texto(page, '.total-principal .cifra');
    const anulados = await texto(page, '.total-anulado .cifra');
    await captura(page);
    const grupos = await consulta('pagos del rango agrupados en la base (por la fecha del pago, en Bogotá)', `SELECT estado, metodo, tipo_vehiculo, count(*) AS cantidad, sum(monto) AS total
      FROM pago WHERE (fecha AT TIME ZONE 'America/Bogota')::date BETWEEN $1::date AND $1::date GROUP BY estado, metodo, tipo_vehiculo ORDER BY estado, metodo, tipo_vehiculo`, [E.hoy]);
    const suma = (f: (g: any) => boolean) => grupos.filter(f).reduce((s, g) => ({ cantidad: s.cantidad + Number(g.cantidad), total: s.total + Number(g.total) }), { cantidad: 0, total: 0 });
    const validos = suma((g) => g.estado === 'VALIDO');
    const anul = suma((g) => g.estado === 'ANULADO');
    const metodos = new Set(grupos.filter((g) => g.estado === 'VALIDO').map((g) => g.metodo));
    const tipos = new Set(grupos.filter((g) => g.estado === 'VALIDO').map((g) => g.tipo_vehiculo));
    verificar(metodos.size >= 2 && tipos.size >= 2 && anul.cantidad >= 1, `precondición: métodos ${[...metodos]}, tipos ${[...tipos]}, anulados ${anul.cantidad}`);
    verificar(r.body.validos.total === validos.total && r.body.validos.cantidad === validos.cantidad, `válidos: API ${JSON.stringify(r.body.validos)}, base ${JSON.stringify(validos)}`);
    verificar(r.body.anulados.total === anul.total && r.body.anulados.cantidad === anul.cantidad, `anulados: API ${JSON.stringify(r.body.anulados)}, base ${JSON.stringify(anul)}`);
    for (const m of r.body.por_metodo) {
      const b = suma((g) => g.estado === 'VALIDO' && g.metodo === m.metodo);
      verificar(m.total === b.total && m.cantidad === b.cantidad, `método ${m.metodo}: API ${JSON.stringify(m)}, base ${JSON.stringify(b)}`);
    }
    for (const t of r.body.por_tipo_vehiculo) {
      const b = suma((g) => g.estado === 'VALIDO' && g.tipo_vehiculo === t.tipo_vehiculo);
      verificar(t.total === b.total && t.cantidad === b.cantidad, `tipo ${t.tipo_vehiculo}: API ${JSON.stringify(t)}, base ${JSON.stringify(b)}`);
    }
    verificar(total === pesos(validos.total) && anulados === pesos(anul.total), `pantalla: «${total}», «${anulados}»`);
    const desglose = (lista: any[], k: string) => lista.map((x) => `${x[k]} ${x.cantidad} (${pesos(x.total)})`).join(', ');
    c.anotar(`Recaudo del ${fechaCorta(E.hoy)}: total válido «${total}» (${validos.cantidad} pagos), igual a la suma de los pagos válidos en la base. Por método: ${desglose(r.body.por_metodo, 'metodo')}. Por tipo: ${desglose(r.body.por_tipo_vehiculo, 'tipo_vehiculo')}.`);
    c.anotar(`Anulados aparte: «${anulados}» (${anul.cantidad} pagos), contados por la fecha del pago; no suman al total.`);
  },

  'RE-02': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/consultas/recaudo');
    const r = await recaudoUI(page, '2020-01-01', '2020-01-31');
    await page.locator('#totales-titulo').waitFor();
    const total = await texto(page, '.total-principal .cifra');
    const anulados = await texto(page, '.total-anulado .cifra');
    const vacio = await texto(page, 'p.empty');
    await captura(page);
    verificar(r.status === 200 && r.body.validos.total === 0 && r.body.anulados.total === 0 && total === '$ 0' && anulados === '$ 0', `HTTP ${r.status}; pantalla «${total}» «${anulados}»`);
    verificar((await page.locator('p.notice.error').count()) === 0, 'la pantalla muestra un error');
    c.anotar(`Rango 01/01/2020–31/01/2020: API 200 con totales en 0; la pantalla muestra «${total}» (válidos) y «${anulados}» (anulados), con «${vacio}», sin error.`);
  },

  'RE-03': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/consultas/recaudo');
    const ayer = sumarDias(E.hoy, -1);
    await page.locator('#desde').fill(E.hoy);
    await page.locator('#hasta').fill(ayer);
    const enviadas = await solicitudesDurante(page, 'GET', '/reportes/recaudo', () => page.getByRole('button', { name: 'Consultar' }).click());
    const aviso = await texto(page, 'p.notice.error');
    await captura(page);
    const r = await (await entrar('admin_prueba')).get(`/reportes/recaudo?desde=${E.hoy}&hasta=${ayer}`, 'rango invertido por la API');
    verificar(enviadas === 0 && aviso === 'La fecha inicial no puede ser posterior a la fecha final.', `pantalla: ${enviadas} solicitudes, «${aviso}»`);
    verificar(r.status === 422 && r.body.detail === 'La fecha inicial no puede ser posterior a la fecha final.', `API: ${r.status} ${JSON.stringify(r.body)}`);
    c.anotar(`Desde ${fechaCorta(E.hoy)} hasta ${fechaCorta(ayer)}: la pantalla dice «${aviso}» sin consultar al servidor. Por la API: 422 «${r.body.detail}».`);
  },

  'RE-04': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba');
    const opciones = await opcionesMenu(page);
    await page.goto('/consultas/recaudo');
    await page.waitForLoadState('networkidle');
    const ruta = new URL(page.url()).pathname;
    await captura(page);
    const r = await (await entrar('operador_prueba')).get(`/reportes/recaudo?desde=${E.hoy}&hasta=${E.hoy}`, 'el operador consulta el recaudo por la API');
    verificar(!opciones.includes('Recaudo'), `el menú del operador incluye Recaudo: ${opciones.join(', ')}`);
    verificar(ruta === '/', `la ruta /consultas/recaudo terminó en ${ruta}`);
    verificar(r.status === 403, `API: ${r.status}`);
    c.anotar(`Menú del operador: ${opciones.join(', ')} (sin Recaudo). Abrir /consultas/recaudo lo devuelve a ${ruta} (Inicio). GET /reportes/recaudo: 403 «${r.body?.detail}».`);
  },

  'PE-01': async (c) => {
    const cuentas = 'SELECT (SELECT count(*) FROM tarifa) AS tarifas, (SELECT count(*) FROM cliente) AS clientes, (SELECT count(*) FROM pago) AS pagos';
    const antes = await consulta('registros antes', cuentas);
    const anon = await anonimo();
    const t = await anon.post('/tarifas', { tipo_vehiculo: 'MOTO', valor: 70000 }, 'actualizar tarifa sin sesión');
    const cl = await anon.post('/clientes', { tipo_documento: 'CC', documento: '7003000066', nombre: 'Cliente Sin Sesión', telefono: '3006600660' }, 'registrar cliente sin sesión');
    const p = await anon.post('/pagos', { placa: placa('PA07'), meses: 1, metodo: 'EFECTIVO', monto_confirmado: 120000 }, 'registrar pago sin sesión');
    const despues = await consulta('registros después', cuentas);
    verificar(t.status === 401 && cl.status === 401 && p.status === 401, `respuestas: ${t.status}, ${cl.status}, ${p.status}`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues), `cambiaron los registros: ${JSON.stringify(antes)} → ${JSON.stringify(despues)}`);
    c.anotar(`Sin sesión: POST /tarifas 401, POST /clientes 401 y POST /pagos 401 («${t.body?.detail}»). Tarifas, clientes y pagos: ${JSON.stringify(despues[0])}, igual que antes.`);
  },
};
