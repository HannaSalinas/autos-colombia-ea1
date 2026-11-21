/** Casos TA-01 a TA-06 y CL-01 a CL-06 del plan PP-03. Los resultados esperados son los del Excel (hoja Casos). */
import type { Browser, Page } from '@playwright/test';
import { captura, consulta, intentoBd, verificar, type Caso } from '../plan/contexto';
import { contar, DOC_CL01, DOC_CL04, entrar, pesos, TARIFAS_INICIALES, tarifaVigente } from './escenario';
import { conRespuesta, conSesionUI, solicitudesDurante, texto } from './pantalla';

type Funcion = (c: Caso, browser: Browser) => Promise<void>;
const TIPOS = ['MOTO', 'AUTOMOVIL', 'CAMIONETA'] as const;
const ADMIN = 'Administradora de Prueba (admin_prueba)';
const FECHA_HORA = /\d{2}\/\d{2}\/\d{4}, \d{1,2}:\d{2} [ap]\. m\./;

async function historialDe(page: Page): Promise<string[][]> {
  return page.locator('table tbody tr').evaluateAll((filas) =>
    filas.map((f) => Array.from(f.querySelectorAll('th, td')).map((c) => (c.textContent ?? '').replace(/\s+/g, ' ').trim())));
}

/** Tarifas: escribe un valor y pulsa «Guardar tarifa». Devuelve cuántos POST /tarifas salieron. */
async function intentarTarifa(page: Page, valor: string): Promise<number> {
  await page.locator('#valor').fill(valor);
  return solicitudesDurante(page, 'POST', '/tarifas', () => page.getByRole('button', { name: 'Guardar tarifa' }).click());
}

async function guardarTarifaUI(page: Page, tipo: string, valor: number): Promise<{ status: number; body: any; aviso: string }> {
  await page.getByRole('button', { name: 'Nueva tarifa' }).click();
  await page.locator('#tipo-vehiculo').selectOption(tipo);
  await page.locator('#valor').fill(String(valor));
  await page.getByRole('button', { name: 'Guardar tarifa' }).click();
  const dialogo = page.getByRole('alertdialog');
  await dialogo.waitFor();
  const r = await conRespuesta(page, 'POST', '/tarifas', () => dialogo.getByRole('button', { name: 'Sí, guardar la tarifa' }).click(),
    `pantalla Tarifas: guardar ${tipo} en ${pesos(valor)} y confirmar`);
  await page.locator('p.notice.success').waitFor();
  return { ...r, aviso: await texto(page, 'p.notice.success') };
}

// ------------------------------------------------------------------ clientes
const VALIDO = { tipo_documento: 'CC', documento: '7003000090', nombre: 'Cliente Límite', telefono: '3000000000', correo: '' };
type DatosCliente = typeof VALIDO;

async function llenarCliente(page: Page, d: DatosCliente): Promise<void> {
  await page.locator('#tipo-documento').selectOption(d.tipo_documento);
  await page.locator('#documento').fill(d.documento);
  await page.locator('#nombre').fill(d.nombre);
  await page.locator('#telefono').fill(d.telefono);
  await page.locator('#correo').fill(d.correo);
}

async function abrirRegistro(page: Page): Promise<void> {
  if (!(await page.locator('#documento').isVisible().catch(() => false))) await page.getByRole('button', { name: 'Registrar cliente' }).click();
  await page.locator('#documento').waitFor();
}

async function buscarCliente(page: Page, texto_: string): Promise<{ status: number; body: any }> {
  await page.locator('#buscar-cliente').fill(texto_);
  return conRespuesta(page, 'GET', '/clientes', () => page.getByRole('button', { name: 'Buscar', exact: true }).click(), `pantalla Clientes: buscar «${texto_}»`);
}

/** Filas del listado de clientes: celdas separadas por « | » y placas separadas por espacio (sin la columna Acciones). */
async function filasClientes(page: Page): Promise<string[]> {
  return page.locator('table tbody tr').evaluateAll((filas) => filas.map((f) =>
    Array.from(f.querySelectorAll('th, td')).slice(0, -1).map((c) => {
      const placas = Array.from(c.querySelectorAll('.placa-tag')).map((t) => (t.textContent ?? '').trim());
      return placas.length ? placas.join(' ') : (c.textContent ?? '').replace(/\s+/g, ' ').trim();
    }).join(' | ')));
}

export const CASOS_TARIFAS_CLIENTES: Record<string, Funcion> = {
  'TA-01': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/gestion/tarifas');
    await page.getByRole('heading', { name: /Historial de tarifas/ }).waitFor();
    await page.locator('table tbody tr').first().waitFor();
    const montos: string[] = [];
    for (const tipo of TIPOS) {
      const tarjeta = page.getByRole('article', { name: `Tarifa de ${tipo}` });
      const monto = ((await tarjeta.locator('.monto').textContent()) ?? '').trim();
      const vigencia = ((await tarjeta.locator('.hint').textContent()) ?? '').replace(/\s+/g, ' ').trim();
      verificar(monto === pesos(TARIFAS_INICIALES[tipo]), `la tarjeta de ${tipo} muestra «${monto}» (se esperaba ${pesos(TARIFAS_INICIALES[tipo])})`);
      verificar(FECHA_HORA.test(vigencia), `la tarjeta de ${tipo} no muestra la fecha de vigencia: «${vigencia}»`);
      montos.push(`${tipo} ${monto}`);
    }
    const filas = await historialDe(page);
    const encabezados = (await page.locator('table thead th').allInnerTexts()).map((t) => t.trim());
    verificar(JSON.stringify(encabezados) === JSON.stringify(['Tipo', 'Valor mensual', 'Vigente desde (Bogotá)', 'Definida por']),
      `columnas del historial: ${encabezados.join(', ')}`);
    const cambio = filas.find((f) => f[0] === 'AUTOMOVIL' && f[1] === '$ 125.000');
    verificar(!!cambio && cambio[3] === ADMIN && FECHA_HORA.test(cambio[2]), `el historial no muestra el cambio previo de AUTOMOVIL a $ 125.000 con su autor: ${JSON.stringify(filas)}`);
    verificar(filas.filter((f) => f[3] === 'Sistema (semillas)').length === 3, 'el historial no conserva las 3 tarifas de las semillas');
    verificar(filas.every((f) => /^\$ \d{1,3}(\.\d{3})*$/.test(f[1]) && FECHA_HORA.test(f[2]) && f[3]), 'hay filas del historial sin valor, fecha o autor');
    const api = await (await entrar('admin_prueba')).get('/tarifas/historial?limit=100', 'historial por la API');
    verificar(api.status === 200 && api.body.total === filas.length, `la API tiene ${api.body.total} tarifas en el historial y la pantalla ${filas.length}`);
    await captura(page);
    c.anotar(`Tarifas vigentes en pantalla: ${montos.join(', ')}, cada una con «al mes · vigente desde» y fecha y hora de Bogotá.`);
    c.anotar(`Historial con ${filas.length} filas (columnas Tipo, Valor mensual, Vigente desde (Bogotá) y Definida por), igual que GET /tarifas/historial: las 3 tarifas de las semillas («Sistema (semillas)») y el cambio previo de AUTOMOVIL a $ 125.000 y de vuelta a $ 120.000, definidos por ${ADMIN}.`);
  },

  'TA-02': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba', '/gestion/tarifas');
    await page.getByRole('article', { name: 'Tarifa de MOTO' }).waitFor();
    const tarjetas = await page.getByRole('article').count();
    const boton = await page.getByRole('button', { name: 'Nueva tarifa' }).count();
    const historial = await page.getByRole('heading', { name: /Historial de tarifas/ }).count();
    await captura(page);
    verificar(tarjetas === 3, `el operador ve ${tarjetas} tarjetas de tarifa (se esperaban 3)`);
    verificar(boton === 0 && historial === 0, `el operador ve la acción de actualizar (${boton}) o el historial (${historial})`);
    const antes = await contar('tarifas antes del intento del operador', 'SELECT count(*) FROM tarifa');
    const op = await entrar('operador_prueba');
    const r = await op.post('/tarifas', { tipo_vehiculo: 'AUTOMOVIL', valor: 130000 }, 'el operador intenta actualizar la tarifa de AUTOMOVIL');
    const h = await op.get('/tarifas/historial', 'el operador pide el historial de gestión');
    const despues = await contar('tarifas después del intento', 'SELECT count(*) FROM tarifa');
    const vigente = await tarifaVigente(op, 'AUTOMOVIL');
    verificar(r.status === 403, `POST /tarifas como operador respondió ${r.status} (se esperaba 403)`);
    verificar(antes === despues && vigente === 120000, `la tarifa cambió: ${antes} → ${despues} filas, AUTOMOVIL ${vigente}`);
    c.anotar(`Pantalla Tarifas del operador: las 3 tarifas vigentes, sin el botón «Nueva tarifa» ni el «Historial de tarifas».`);
    c.anotar(`POST /tarifas (AUTOMOVIL $ 130.000): 403 «${r.body?.detail}». GET /tarifas/historial: ${h.status}. La tabla tarifa sigue con ${despues} filas y AUTOMOVIL en $ 120.000.`);
  },

  'TA-03': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/gestion/tarifas');
    const admin = await entrar('admin_prueba');
    const inicial = await tarifaVigente(admin, 'MOTO');
    const antes = (await admin.get('/tarifas/historial?tipo=MOTO&limit=100', 'historial de MOTO antes')).body;
    const avisos: string[] = [];
    for (const valor of [1000, 2000000, inicial]) {
      const r = await guardarTarifaUI(page, 'MOTO', valor);
      verificar(r.status === 201 && r.body.valor === valor && r.body.definida_por === ADMIN,
        `guardar MOTO en ${valor}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
      verificar(r.aviso.startsWith(`Nueva tarifa de MOTO: ${pesos(valor)} al mes, vigente desde`), `aviso: «${r.aviso}»`);
      avisos.push(r.aviso);
      if (valor === 2000000) await captura(page, '2000000');
    }
    await page.waitForTimeout(500);
    await captura(page);
    const despues = (await admin.get('/tarifas/historial?tipo=MOTO&limit=100', 'historial de MOTO después')).body;
    const nuevas = despues.items.slice(0, 3);
    verificar(despues.total === antes.total + 3, `el historial de MOTO pasó de ${antes.total} a ${despues.total} (se esperaban 3 más)`);
    verificar(JSON.stringify(nuevas.map((t: any) => t.valor)) === JSON.stringify([inicial, 2000000, 1000]), `las 3 tarifas nuevas: ${JSON.stringify(nuevas)}`);
    verificar(nuevas.every((t: any) => t.definida_por === ADMIN), 'alguna tarifa nueva no tiene al administrador como autor');
    verificar(antes.items.every((t: any) => despues.items.some((d: any) => d.id === t.id && d.valor === t.valor)), 'alguna tarifa anterior desapareció o cambió');
    const vigente = await tarifaVigente(admin, 'MOTO');
    verificar(vigente === inicial, `MOTO quedó en ${vigente}`);
    c.anotar(`Desde la pantalla Tarifas (con su confirmación) se guardaron MOTO $ 1.000, $ 2.000.000 y ${pesos(inicial)}: los tres respondieron 201. Avisos: ${avisos.map((a) => `«${a}»`).join('; ')}.`);
    c.anotar(`El historial de MOTO pasó de ${antes.total} a ${despues.total} tarifas: cada cambio es una tarifa nueva con su fecha de vigencia y «${ADMIN}» como autor; la tarifa de las semillas sigue en el historial. MOTO vigente: ${pesos(vigente)}.`);
  },

  'TA-04': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/gestion/tarifas');
    const admin = await entrar('admin_prueba');
    const antes = await contar('tarifas antes', 'SELECT count(*) FROM tarifa');
    await page.getByRole('button', { name: 'Nueva tarifa' }).click();
    await page.locator('#tipo-vehiculo').selectOption('MOTO');
    const pantalla: string[] = [];
    for (const valor of ['999', '2000001', '1500.5', '']) {
      const enviadas = await intentarTarifa(page, valor);
      const error = await texto(page, '#valor-error');
      const dialogo = await page.getByRole('alertdialog').count();
      verificar(enviadas === 0 && dialogo === 0 && !!error, `«${valor}» en pantalla: ${enviadas} solicitudes, confirmación ${dialogo}, error «${error}»`);
      pantalla.push(`«${valor || '(vacío)'}» → «${error}»`);
      if (valor === '1500.5') await captura(page);
    }
    const servidor: string[] = [];
    for (const valor of [999, 2000001, 1500.5, null, '']) {
      const r = await admin.post('/tarifas', { tipo_vehiculo: 'MOTO', valor }, `tarifa inválida por la API: ${JSON.stringify(valor)}`);
      verificar(r.status === 422, `POST /tarifas con ${JSON.stringify(valor)} respondió ${r.status} (se esperaba 422)`);
      servidor.push(`${JSON.stringify(valor)} → 422`);
    }
    const despues = await contar('tarifas después', 'SELECT count(*) FROM tarifa');
    const vigente = await tarifaVigente(admin, 'MOTO');
    verificar(antes === despues && vigente === 60000, `se creó algún registro (${antes} → ${despues}) o MOTO cambió (${vigente})`);
    c.anotar(`En pantalla ningún valor llegó a la confirmación ni al servidor: ${pantalla.join('; ')}.`);
    c.anotar(`Por la API: ${servidor.join(', ')}. La tabla tarifa sigue con ${despues} filas y MOTO vigente en $ 60.000.`);
  },

  'TA-06': async (c) => {
    const foto = 'SELECT id, tipo_vehiculo, valor, vigente_desde, definida_por_cuenta_id FROM tarifa ORDER BY id';
    const antes = await consulta('tarifas antes de los intentos', foto);
    const objetivo = antes.find((t) => t.tipo_vehiculo === 'MOTO' && Number(t.valor) === 1000) ?? antes[antes.length - 1];
    const u = await intentoBd('1. UPDATE del valor de una tarifa', 'UPDATE tarifa SET valor = valor + 1000 WHERE id = $1', [objetivo.id]);
    const d = await intentoBd('2. DELETE de una tarifa', 'DELETE FROM tarifa WHERE id = $1', [objetivo.id]);
    const despues = await consulta('3. tarifas después de los intentos', foto);
    verificar(u.rechazada && d.rechazada, `la base aceptó: UPDATE ${u.rechazada ? 'rechazado' : 'aceptado'}, DELETE ${d.rechazada ? 'rechazado' : 'aceptado'}`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues), 'la tabla tarifa cambió');
    c.anotar(`UPDATE tarifa (id ${objetivo.id}): rechazado con SQLSTATE ${u.codigo} «${u.mensaje}». DELETE: rechazado con SQLSTATE ${d.codigo} «${d.mensaje}».`);
    c.anotar(`La tabla tarifa queda idéntica: ${despues.length} filas con los mismos valores, fechas y autores.`);
  },

  'CL-01': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/gestion/clientes');
    await abrirRegistro(page);
    await llenarCliente(page, { tipo_documento: 'CC', documento: DOC_CL01, nombre: 'Ana María Restrepo', telefono: '3001234567', correo: 'ana.restrepo@correo.com' });
    const r = await conRespuesta(page, 'POST', '/clientes', () => page.getByRole('button', { name: 'Guardar cliente' }).click(), 'pantalla Clientes: guardar el cliente');
    verificar(r.status === 201, `POST /clientes respondió ${r.status}: ${JSON.stringify(r.body)}`);
    const exito = await texto(page, 'p.notice.success');
    const busqueda = await buscarCliente(page, DOC_CL01);
    const filas = await filasClientes(page);
    verificar(busqueda.body.total === 1 && filas.length === 1 && filas[0].includes(`CC ${DOC_CL01}`), `la búsqueda devolvió ${JSON.stringify(filas)}`);
    await page.getByRole('button', { name: 'Ver detalle de Ana María Restrepo' }).click();
    await page.getByRole('heading', { name: 'Detalle de Ana María Restrepo' }).waitFor();
    const registro = ((await page.locator('dl.datos > div').filter({ hasText: 'Registrado' }).locator('dd').textContent()) ?? '').replace(/\s+/g, ' ').trim();
    await captura(page);
    verificar(FECHA_HORA.test(registro) && registro.endsWith(ADMIN), `el detalle muestra «${registro}»`);
    const n = await contar('clientes con el documento CC 1020304050', "SELECT count(*) FROM cliente WHERE tipo_documento = 'CC' AND documento = $1", [DOC_CL01]);
    const fila = await consulta('registro del cliente', `SELECT c.id, c.tipo_documento, c.documento, c.nombre, c.telefono, c.correo, c.registrado_en, u.nombre_usuario AS registrado_por
      FROM cliente c LEFT JOIN cuenta_usuario u ON u.id = c.registrado_por_cuenta_id WHERE c.documento = $1`, [DOC_CL01]);
    verificar(n === 1 && fila[0]?.registrado_por === 'admin_prueba', `clientes con ese documento: ${n}; registrado por ${fila[0]?.registrado_por}`);
    c.anotar(`Formulario Registrar cliente (CC ${DOC_CL01}, Ana María Restrepo, 3001234567, ana.restrepo@correo.com) → API 201; aviso «${exito}».`);
    c.anotar(`La búsqueda por el documento devuelve solo ese cliente. Detalle: «Registrado ${registro}». En la base hay ${n} cliente con ese documento, registrado por admin_prueba.`);
  },

  'CL-02': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/gestion/clientes');
    const admin = await entrar('admin_prueba');
    await abrirRegistro(page);
    const invalidos: [keyof DatosCliente, string, string][] = [
      ['documento', '1234', 'documento de 4'], ['documento', '1234567890123456', 'documento de 16'],
      ['nombre', 'Al', 'nombre de 2'], ['nombre', 'N' + 'a'.repeat(80), 'nombre de 81'], ['nombre', '     ', 'nombre solo con espacios'],
      ['telefono', '300123456', 'teléfono de 9'], ['telefono', '30012345678', 'teléfono de 11'], ['telefono', '300123456a', 'teléfono con letras'],
      ['correo', 'ana@', 'correo «ana@»'], ['correo', 'anacorreo.com', 'correo sin @'],
    ];
    const pantalla: string[] = [];
    for (const [campo, valor, nombre] of invalidos) {
      await llenarCliente(page, { ...VALIDO, [campo]: valor });
      const enviadas = await solicitudesDurante(page, 'POST', '/clientes', () => page.getByRole('button', { name: 'Guardar cliente' }).click());
      const error = await texto(page, `#${campo}-error`);
      verificar(enviadas === 0 && !!error, `${nombre} en pantalla: ${enviadas} solicitudes, error «${error}»`);
      pantalla.push(`${nombre} → «${error}»`);
      if (campo === 'telefono' && valor.endsWith('a')) await captura(page, 'rechazo');
    }
    // Límites válidos: se aceptan (se registran dos clientes con los extremos).
    const nombre80 = 'Nombre de Ochenta Caracteres para Probar el Límite del Campo Nombre del Cliente.';
    verificar(nombre80.length === 80, `el nombre de prueba tiene ${nombre80.length} caracteres`);
    const limites: DatosCliente[] = [
      { tipo_documento: 'CC', documento: '70030', nombre: 'Ana', telefono: '3000000005', correo: '' },
      { tipo_documento: 'CC', documento: '700300000000015', nombre: nombre80, telefono: '3000000015', correo: 'cliente.limite@correo.com' },
    ];
    const aceptados: string[] = [];
    for (const d of limites) {
      await abrirRegistro(page);
      await llenarCliente(page, d);
      const r = await conRespuesta(page, 'POST', '/clientes', () => page.getByRole('button', { name: 'Guardar cliente' }).click(),
        `pantalla Clientes: límites válidos (documento de ${d.documento.length}, nombre de ${d.nombre.length})`);
      verificar(r.status === 201, `límites válidos (documento ${d.documento}): HTTP ${r.status} ${JSON.stringify(r.body)}`);
      aceptados.push(`documento de ${d.documento.length}, nombre de ${d.nombre.length}, teléfono de 10 y correo ${d.correo ? 'válido' : 'vacío'} → 201`);
    }
    await captura(page);
    const servidor: string[] = [];
    for (const [campo, valor, nombre] of invalidos) {
      const cuerpo = { ...VALIDO, [campo]: valor, correo: campo === 'correo' ? valor : null };
      const r = await admin.post('/clientes', cuerpo, `rechazo por la API: ${nombre}`);
      verificar(r.status === 422, `${nombre} por la API respondió ${r.status} (se esperaba 422)`);
      servidor.push(nombre);
    }
    const incompletos = await contar('clientes creados con los datos inválidos (documento base 7003000090 o documentos de 4 y 16)',
      "SELECT count(*) FROM cliente WHERE documento IN ('7003000090', '1234', '1234567890123456')");
    const validos = await consulta('clientes con los límites válidos', "SELECT documento, length(documento) AS largo_documento, nombre, length(nombre) AS largo_nombre, telefono, correo FROM cliente WHERE documento IN ('70030', '700300000000015') ORDER BY documento");
    verificar(incompletos === 0 && validos.length === 2, `clientes inválidos creados: ${incompletos}; límites válidos guardados: ${validos.length}`);
    c.anotar(`En pantalla se rechazan sin enviar nada: ${pantalla.join('; ')}.`);
    c.anotar(`Se aceptan los límites válidos (desde la pantalla): ${aceptados.join('; ')}.`);
    c.anotar(`Por la API los ${servidor.length} valores inválidos responden 422. En la base no hay ningún cliente con los datos inválidos y sí los 2 de los límites válidos.`);
  },

  'CL-03': async (c) => {
    const admin = await entrar('admin_prueba');
    const r = await admin.post('/clientes', { tipo_documento: 'CC', documento: DOC_CL01, nombre: 'Otra Persona', telefono: '3009998877' }, 'registrar otro cliente con CC 1020304050');
    const n = await contar('clientes con CC 1020304050', "SELECT count(*) FROM cliente WHERE tipo_documento = 'CC' AND documento = $1", [DOC_CL01]);
    verificar(r.status === 409 && /ya existe/i.test(r.body?.detail ?? ''), `respondió ${r.status}: ${JSON.stringify(r.body)}`);
    verificar(n === 1, `hay ${n} clientes con ese documento`);
    c.anotar(`POST /clientes con CC ${DOC_CL01}: 409 «${r.body.detail}». En la base sigue habiendo ${n} cliente con ese documento.`);
  },

  'CL-04': async (c) => {
    const [a, b] = await Promise.all([entrar('admin_prueba'), entrar('admin_dos')]);
    const cuerpo = (nombre: string) => ({ tipo_documento: 'CC', documento: DOC_CL04, nombre, telefono: '3001112233' });
    const [ra, rb] = await Promise.all([
      a.post('/clientes', cuerpo('Registro Simultáneo Uno'), 'registro simultáneo (sesión de admin_prueba)'),
      b.post('/clientes', cuerpo('Registro Simultáneo Dos'), 'registro simultáneo (sesión de admin_dos)'),
    ]);
    const codigos = [ra.status, rb.status].sort();
    const n = await contar('clientes con CC 1098765432', "SELECT count(*) FROM cliente WHERE tipo_documento = 'CC' AND documento = $1", [DOC_CL04]);
    verificar(JSON.stringify(codigos) === '[201,409]', `respuestas: ${ra.status} y ${rb.status}`);
    verificar(n === 1, `hay ${n} clientes con ese documento`);
    const perdedor = ra.status === 409 ? ra : rb;
    c.anotar(`Dos sesiones de administrador enviaron el registro de CC ${DOC_CL04} al mismo tiempo: admin_prueba ${ra.status} y admin_dos ${rb.status}; el 409 dice «${perdedor.body.detail}». En la base hay exactamente ${n} cliente con ese documento.`);
  },

  'CL-05': async (c, browser) => {
    const page = await conSesionUI(browser, 'admin_prueba', '/gestion/clientes');
    const nombre = await buscarCliente(page, 'Laura');
    const filasNombre = await filasClientes(page);
    verificar(nombre.status === 200 && nombre.body.items.length > 0 && nombre.body.items.every((x: any) => /laura/i.test(x.nombre) || x.documento.includes('LAURA')),
      `búsqueda por nombre: ${JSON.stringify(nombre.body.items?.map((x: any) => x.nombre))}`);
    verificar(filasNombre.length === nombre.body.items.length && filasNombre.every((f) => /Laura/.test(f)), `filas: ${JSON.stringify(filasNombre)}`);
    verificar(nombre.body.items.every((x: any) => Array.isArray(x.vehiculos)) && filasNombre.some((f) => /[A-Z]{3}\d{2}[0-9A-Z]/.test(f)), 'los clientes no muestran sus vehículos');
    await captura(page, 'nombre');
    const doc = await buscarCliente(page, '1001234567');
    const filasDoc = await filasClientes(page);
    verificar(doc.body.total === 1 && filasDoc.length === 1 && filasDoc[0].includes('1001234567'), `búsqueda por documento: ${JSON.stringify(filasDoc)}`);
    const nada = await buscarCliente(page, 'Sin Coincidencias Xyz');
    const vacio = await texto(page, 'section[aria-label="Listado de clientes"] p.empty');
    await captura(page, 'sin_coincidencias');
    verificar(nada.status === 200 && nada.body.total === 0 && nada.body.items.length === 0, `sin coincidencias: HTTP ${nada.status} ${JSON.stringify(nada.body)}`);
    verificar(vacio === 'No hay clientes que coincidan con la búsqueda.' && (await page.locator('p.notice.error').count()) === 0, `la pantalla muestra «${vacio}»`);
    c.anotar(`Por parte del nombre («Laura»): ${filasNombre.length} cliente(s), todos coinciden y muestran sus vehículos (${filasNombre.join(' | ')}).`);
    c.anotar(`Por documento (1001234567): solo ${filasDoc[0]}.`);
    c.anotar(`Sin coincidencias: GET /clientes responde 200 con lista vacía (total 0) y la pantalla dice «${vacio}», sin error.`);
  },

  'CL-06': async (c, browser) => {
    const page = await conSesionUI(browser, 'operador_prueba', '/gestion/clientes');
    const r = await buscarCliente(page, 'Laura');
    const filas = await filasClientes(page);
    const boton = await page.getByRole('button', { name: 'Registrar cliente' }).count();
    await page.getByRole('button', { name: /^Ver detalle de / }).first().click();
    await page.getByRole('heading', { name: /^Detalle de / }).waitFor();
    const vehiculos = (await page.locator('dl.datos > div').filter({ hasText: 'Vehículos' }).locator('dd .placa-tag').allInnerTexts()).map((t) => t.trim()).join(', ');
    await captura(page);
    verificar(r.status === 200 && filas.length > 0 && /[A-Z]{3}\d{2}/.test(vehiculos), `búsqueda del operador: ${JSON.stringify(filas)}; vehículos «${vehiculos}»`);
    verificar(boton === 0, 'el operador ve la acción «Registrar cliente»');
    const op = await entrar('operador_prueba');
    const p = await op.post('/clientes', { tipo_documento: 'CC', documento: '7003000077', nombre: 'Cliente del Operador', telefono: '3007700770' }, 'el operador intenta registrar un cliente');
    const n = await contar('clientes con CC 7003000077', "SELECT count(*) FROM cliente WHERE documento = '7003000077'");
    verificar(p.status === 403 && n === 0, `POST /clientes como operador: ${p.status}; clientes creados: ${n}`);
    c.anotar(`El operador busca «Laura» (${filas.length} resultado(s)) y abre el detalle: vehículos «${vehiculos}». No aparece la acción «Registrar cliente».`);
    c.anotar(`POST /clientes como operador: 403 «${p.body?.detail}». No se creó el cliente (0 filas con CC 7003000077).`);
  },
};
