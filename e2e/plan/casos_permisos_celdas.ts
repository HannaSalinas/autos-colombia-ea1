/** Casos PE-01 a PE-05 y CE-01 a CE-16 del plan de pruebas (CE-17 se ejecuta con pytest). */
import type { Browser, Page } from '@playwright/test';
import { anonimo, captura, consulta, menu, precondicion, verificar, type Caso } from './contexto';
import { buscarYEsperar, conSesionUI, MENU_OPERADOR, textoVisible } from './casos_usuarios';
import { crearCelda, cuenta, E, entrar, tomarCarro } from './escenario';

const NO_EXISTE = 999999;

async function abrirCeldas(page: Page): Promise<void> {
  await menu(page).getByRole('link', { name: 'Celdas' }).click();
  await page.getByRole('heading', { level: 1, name: 'Celdas', exact: true }).waitFor();
  await page.getByRole('rowheader').first().waitFor();
}

async function buscarCelda(page: Page, texto: string): Promise<void> {
  await page.getByLabel('Buscar por código').fill(texto);
  await buscarYEsperar(page, '/celdas?');
}

const filasCeldas = (page: Page) => page.getByRole('row').filter({ has: page.getByRole('rowheader') });

async function celdaBd(nota: string, codigo: string) {
  return (await consulta(nota, 'SELECT id, codigo, tipo, ubicacion, habilitada, disponible_desde FROM celda WHERE upper(codigo) = upper($1)', [codigo]))[0];
}

export const CASOS_PERMISOS_CELDAS: Record<string, (c: Caso, browser: Browser) => Promise<void>> = {
  'PE-01': async (c) => {
    const antes = (await consulta('cuentas y celdas antes', 'SELECT (SELECT count(*) FROM cuenta_usuario)::int AS cuentas, (SELECT count(*) FROM celda)::int AS celdas'))[0];
    const api = await anonimo();
    const r1 = await api.post('/cuentas', { nombre: 'Sin Sesión', nombre_usuario: 'sin.sesion', contrasena: 'Clave12345', rol: 'OPERADOR' }, 'crear cuenta sin autenticación');
    const r2 = await api.post('/celdas', { codigo: 'C79', tipo: 'CARRO' }, 'crear celda sin autenticación');
    const despues = (await consulta('cuentas y celdas después', 'SELECT (SELECT count(*) FROM cuenta_usuario)::int AS cuentas, (SELECT count(*) FROM celda)::int AS celdas'))[0];
    verificar(r1.status === 401 && r2.status === 401, `API: ${r1.status} y ${r2.status} (se esperaba 401)`);
    verificar(antes.cuentas === despues.cuentas && antes.celdas === despues.celdas, 'se creó un registro');
    c.anotar(`API: 401 en ambas. Cuentas (${antes.cuentas}) y celdas (${antes.celdas}) sin cambios.`);
  },

  'PE-02': async (c, browser) => {
    const o = cuenta('operador_prueba');
    const { contexto, page } = await conSesionUI(browser, o.usuario, o.contrasena);
    await page.goto('/gestion/cuentas');
    // La guarda redirige en el navegador: se espera a que la URL deje de ser /gestion/cuentas.
    await page.waitForURL((u) => !u.pathname.startsWith('/gestion/cuentas'), { timeout: 10_000 }).catch(() => undefined);
    await page.waitForLoadState('networkidle');
    const url = new URL(page.url());
    await captura(page);
    await contexto.close();
    const objetivo = cuenta('operador.nuevo');
    const antes = (await consulta('cuentas antes', 'SELECT count(*)::int AS cuentas, bool_and(activa) FILTER (WHERE id = $1) AS objetivo_activa FROM cuenta_usuario', [objetivo.id]))[0];
    const api = await entrar(o);
    const r1 = await api.post('/cuentas', { nombre: 'Creada Por Operador', nombre_usuario: 'creada.por.operador', contrasena: 'Clave12345', rol: 'OPERADOR' }, 'el operador intenta crear una cuenta');
    const r2 = await api.post(`/cuentas/${objetivo.id}/desactivar`, undefined, 'el operador intenta desactivar una cuenta existente (operador.nuevo)');
    const despues = (await consulta('cuentas después', 'SELECT count(*)::int AS cuentas, bool_and(activa) FILTER (WHERE id = $1) AS objetivo_activa FROM cuenta_usuario', [objetivo.id]))[0];
    verificar(url.pathname === '/', `la pantalla quedó en ${url.pathname}`);
    verificar(r1.status === 403 && r2.status === 403, `API: ${r1.status} y ${r2.status} (se esperaba 403)`);
    verificar(antes.cuentas === despues.cuentas && despues.objetivo_activa === true, 'se creó o modificó una cuenta');
    c.anotar(`La pantalla no abre Cuentas de usuario y vuelve a «Inicio» (/). API: 403 en la creación y en la desactivación. Cuentas sin cambios y operador.nuevo sigue activa.`);
  },

  'PE-03': async (c, browser) => {
    const o = cuenta('operador_prueba');
    const id = E.celdas.C80;
    const { contexto, page } = await conSesionUI(browser, o.usuario, o.contrasena);
    await abrirCeldas(page);
    const botones = await page.getByRole('button', { name: /^(Nueva celda|Editar|Inhabilitar|Rehabilitar)/ }).count();
    await captura(page);
    await contexto.close();
    const antes = await celdaBd('C80 antes', 'C80');
    const api = await entrar(o);
    const respuestas = [
      await api.post('/celdas', { codigo: 'C79', tipo: 'CARRO' }, 'crear'),
      await api.patch(`/celdas/${id}`, { ubicacion: 'Cambio del operador' }, 'editar C80'),
      await api.post(`/celdas/${id}/inhabilitar`, undefined, 'inhabilitar C80'),
      await api.post(`/celdas/${id}/rehabilitar`, undefined, 'rehabilitar C80'),
    ].map((r) => r.status);
    const despues = await celdaBd('C80 después', 'C80');
    verificar(botones === 0, `el operador ve ${botones} botones de administración`);
    verificar(respuestas.every((s) => s === 403), `API: ${respuestas.join(', ')} (se esperaba 403 en las cuatro)`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues), 'C80 cambió');
    c.anotar(`El operador consulta el catálogo sin botones de acción. Crear, editar, inhabilitar y rehabilitar: ${respuestas.join(', ')}. C80 conserva sus datos.`);
  },

  'PE-04': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const api = await entrar(a);
    const placa = await tomarCarro(api);
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Control de acceso' }).click();
    await page.getByLabel('Placa de entrada').fill(placa);
    await page.getByRole('button', { name: 'Registrar entrada' }).click();
    await page.getByText(`Entrada registrada: ${placa}`).waitFor();
    await captura(page, 'entrada');
    await page.getByLabel('Placa a consultar').fill(placa);
    await page.getByRole('button', { name: 'Consultar vehículo' }).click();
    await page.getByRole('button', { name: 'Confirmar salida' }).click();
    await page.getByText(`Salida registrada: ${placa}`).waitFor();
    await captura(page, 'salida');
    await contexto.close();
    const h = await api.get(`/reportes/historial?placa=${placa}`, 'responsable de los movimientos');
    const e = h.body.items[0];
    verificar(e?.operador_entrada === a.nombre && e?.operador_salida === a.nombre, `responsables: ${e?.operador_entrada} / ${e?.operador_salida}`);
    c.anotar(`El administrador registra la entrada y la salida de ${placa}; ambos movimientos quedan a nombre de ${a.nombre}.`);
  },

  'PE-05': async (c, browser) => {
    const o = cuenta('operador_prueba');
    const estados = await consulta('estados disponibles para el caso', `SELECT c.codigo, c.habilitada, EXISTS (SELECT 1 FROM estancia e WHERE e.celda_id = c.id AND e.salida IS NULL) AS ocupada FROM celda c WHERE c.codigo IN ('C86', 'C81', 'C82') ORDER BY c.codigo`);
    const libre = estados.find((f) => f.habilitada && !f.ocupada)?.codigo;
    const inhabilitada = estados.find((f) => !f.habilitada)?.codigo;
    const ocupada = estados.find((f) => f.ocupada)?.codigo;
    precondicion(!!libre && !!inhabilitada && !!ocupada, `faltan celdas: libre ${libre}, ocupada ${ocupada}, inhabilitada ${inhabilitada}`);
    const contar = () => consulta('estancias y celdas libres', `SELECT (SELECT count(*) FROM estancia)::int AS estancias, (SELECT count(*) FROM celda c WHERE c.habilitada AND NOT EXISTS (SELECT 1 FROM estancia e WHERE e.celda_id = c.id AND e.salida IS NULL))::int AS libres`);
    const antes = (await contar())[0];
    const { contexto, page } = await conSesionUI(browser, o.usuario, o.contrasena);
    await abrirCeldas(page);
    const vistos: string[] = [];
    for (const codigo of [libre, ocupada, inhabilitada] as string[]) {
      await buscarCelda(page, codigo);
      vistos.push((await filasCeldas(page).first().innerText()).replace(/\s+/g, ' ').trim());
    }
    const botones = await page.getByRole('button', { name: /^(Nueva celda|Editar|Inhabilitar|Rehabilitar)/ }).count();
    await buscarCelda(page, 'C8');
    await captura(page);
    const despuesDeVer = (await contar())[0];
    const api = await entrar(o);
    const placa = await tomarCarro(api);
    const r = await api.post('/estancias/entrada', { placa }, 'registrar una entrada después de consultar');
    await contexto.close();
    const asignada = r.body?.celda;
    if (r.status === 201) await api.post('/estancias/salida', { placa }, 'al terminar: registrar la salida para liberar el carro');
    verificar(vistos[0].includes('Libre') && vistos[1].includes('Ocupada') && vistos[1].includes(E.placaC82) && vistos[2].includes('Inhabilitada'), `filas: ${vistos.join(' / ')}`);
    verificar(botones === 0, `botones de administración: ${botones}`);
    verificar(antes.estancias === despuesDeVer.estancias && antes.libres === despuesDeVer.libres, 'consultar cambió las estancias o las celdas libres');
    verificar(r.status === 201 && asignada?.habilitada === true && asignada.codigo !== ocupada && asignada.codigo !== inhabilitada, `entrada: ${r.status}, celda ${asignada?.codigo}`);
    c.anotar(`El operador ve ${libre} libre, ${ocupada} ocupada con la placa ${E.placaC82} y ${inhabilitada} inhabilitada, sin botones de administración. Consultar no cambia estancias ni celdas libres. La entrada de ${placa} recibe ${asignada.codigo}, libre y habilitada.`);
  },

  'CE-01': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const api = await entrar(a);
    const lista = await api.get('/celdas?buscar=C8&limit=100', 'catálogo de las celdas de prueba');
    const por = Object.fromEntries(lista.body.items.map((x: any) => [x.codigo, x]));
    const esperado: Record<string, string> = { C80: 'LIBRE', C81: 'LIBRE', C82: 'OCUPADA' };
    const datos = Object.entries(esperado).map(([k, v]) => `${k} ${por[k]?.tipo} «${por[k]?.ubicacion}» ${por[k]?.estado}`);
    verificar(Object.entries(esperado).every(([k, v]) => por[k]?.tipo === 'CARRO' && por[k]?.estado === v && por[k]?.ubicacion), `datos: ${datos.join('; ')}`);
    const b = await api.get('/celdas?buscar=C80', 'buscar C80');
    const f = await api.get('/celdas?tipo=CARRO&estado=OCUPADA&limit=100', 'filtrar por tipo CARRO y estado OCUPADA');
    verificar(b.body.items.length === 1 && b.body.items[0].codigo === 'C80', `búsqueda C80: ${b.body.items.map((x: any) => x.codigo).join(', ')}`);
    verificar(f.body.items.length > 0 && f.body.items.every((x: any) => x.tipo === 'CARRO' && x.estado === 'OCUPADA') && f.body.items.some((x: any) => x.codigo === 'C82'), 'el filtro devuelve celdas que no coinciden');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    const columnas = (await page.getByRole('columnheader').allInnerTexts()).map((t) => t.trim());
    await captura(page, 'catalogo');
    await buscarCelda(page, 'C80');
    const filas = await filasCeldas(page).allInnerTexts();
    await captura(page, 'busqueda');
    await page.getByLabel('Buscar por código').fill('');
    await page.locator('#filtro-tipo').selectOption('CARRO');
    await page.locator('#filtro-estado').selectOption('OCUPADA');
    await buscarYEsperar(page, '/celdas?');
    const filtradas = await filasCeldas(page).allInnerTexts();
    await captura(page, 'filtros');
    await contexto.close();
    verificar(['Código', 'Tipo', 'Ubicación', 'Estado'].every((x) => columnas.includes(x)), `columnas: ${columnas.join(', ')}`);
    verificar(filas.length === 1 && filas[0].includes('C80'), `búsqueda en pantalla: ${filas.length} filas`);
    verificar(filtradas.length > 0 && filtradas.every((x) => x.includes('CARRO') && x.includes('Ocupada')), 'el filtro en pantalla muestra celdas que no coinciden');
    c.anotar(`Columnas ${columnas.map((x) => `«${x}»`).join(', ')}. ${datos.join('; ')}. La búsqueda de C80 devuelve solo C80 y el filtro CARRO + Ocupada solo celdas que coinciden (incluida C82), en pantalla y en la API.`);
  },

  'CE-02': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const api = await entrar(a);
    const r1 = await api.get('/celdas?buscar=X9', 'código inexistente');
    const r2 = await api.get('/celdas?buscar=M0&tipo=CARRO', 'filtros sin coincidencias');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    await buscarCelda(page, 'X9');
    const vacio = await textoVisible(page, 'No hay celdas que coincidan.');
    const alerta = await page.getByRole('alert').count();
    await captura(page);
    await contexto.close();
    verificar(r1.status === 200 && r1.body.items.length === 0 && r2.status === 200 && r2.body.items.length === 0, `API: ${r1.status}/${r1.body.items?.length}, ${r2.status}/${r2.body.items?.length}`);
    verificar(vacio && alerta === 0, 'la pantalla no muestra «No hay celdas que coincidan.» o muestra un error');
    c.anotar('API: 200 con lista vacía (código inexistente y filtros sin coincidencias). La pantalla muestra «No hay celdas que coincidan.», sin error.');
  },

  'CE-03': async (c) => {
    const api = await entrar(cuenta('admin_prueba'));
    const r = await api.get(`/celdas/${NO_EXISTE}`, 'celda inexistente');
    verificar(r.status === 404 && r.body.detail === 'Celda no encontrada.' && !r.body.codigo, `API: ${r.status} ${JSON.stringify(r.body)}`);
    c.anotar('API: 404 «Celda no encontrada.»; no se devuelve otra celda.');
  },

  'CE-04': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    await page.getByRole('button', { name: 'Nueva celda' }).click();
    await page.getByLabel('Código', { exact: true }).fill('C83');
    await page.locator('#tipo').selectOption('CARRO');
    await page.getByLabel('Ubicación (opcional)').fill('Bloque C, nivel 8');
    const respuesta = page.waitForResponse((r) => r.url().endsWith('/celdas') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Guardar celda' }).click();
    const r = await respuesta;
    const cuerpo = await r.json();
    c.api.push({ sesion: a.usuario, metodo: 'POST', ruta: '/celdas', codigo: r.status(), solicitud: { codigo: 'C83', tipo: 'CARRO', ubicacion: 'Bloque C, nivel 8' }, respuesta: cuerpo, nota: 'creación desde la pantalla (respuesta capturada del navegador)' });
    const exito = await textoVisible(page, 'Celda C83 registrada correctamente.');
    await captura(page);
    await page.reload();
    await abrirCeldas(page);
    await buscarCelda(page, 'C83');
    const fila = (await filasCeldas(page).allInnerTexts()).join(' / ');
    await captura(page, 'recargada');
    await contexto.close();
    verificar(r.status() === 201, `API: ${r.status()} (se esperaba 201)`);
    E.celdas.C83 = cuerpo.id;
    const api = await entrar(a);
    const det = await api.get(`/celdas/${cuerpo.id}`, 'consultar C83 desde otra solicitud');
    const bd = await consulta('celdas C83 y estancias en ella', "SELECT (SELECT count(*) FROM celda WHERE upper(codigo) = 'C83')::int AS celdas_c83, (SELECT count(*) FROM estancia e JOIN celda c ON c.id = e.celda_id WHERE c.codigo = 'C83')::int AS estancias");
    const crear = det.body.auditoria?.find((x: any) => x.accion === 'CREAR');
    verificar(exito, 'no aparece «Celda C83 registrada correctamente.»');
    verificar(fila.includes('C83') && fila.includes('Bloque C, nivel 8') && fila.includes('Libre'), `al recargar: ${fila}`);
    verificar(det.body.estado === 'LIBRE' && det.body.habilitada === true, `estado: ${det.body.estado}, habilitada: ${det.body.habilitada}`);
    verificar(bd[0].celdas_c83 === 1 && bd[0].estancias === 0, `celdas C83: ${bd[0].celdas_c83}, estancias: ${bd[0].estancias}`);
    verificar(!!crear && String(crear.actor).includes(a.usuario) && !!crear.fecha, 'la auditoría no registra CREAR con el administrador');
    c.anotar(`API: 201. «Celda C83 registrada correctamente.». Al recargar sigue C83, «Bloque C, nivel 8», Libre. Existe una sola C83, libre y habilitada, sin estancias. Auditoría: CREAR por ${crear.actor} el ${crear.fecha}.`);
  },

  'CE-05': async (c) => {
    const api = await entrar(cuenta('admin_prueba'));
    const antes = await celdaBd('C80 antes', 'C80');
    const r1 = await api.post('/celdas', { codigo: 'C80', tipo: 'CARRO', ubicacion: 'Duplicada' }, 'crear C80 otra vez');
    const r2 = await api.post('/celdas', { codigo: ' c80 ', tipo: 'CARRO', ubicacion: 'Duplicada' }, 'crear « c80 » (espacios y minúscula)');
    const despues = await celdaBd('C80 después', 'C80');
    const n = await consulta('celdas con el código C80', "SELECT count(*)::int AS celdas FROM celda WHERE upper(trim(codigo)) = 'C80'");
    verificar(r1.status === 409 && r2.status === 409, `API: ${r1.status} y ${r2.status} (se esperaba 409)`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues) && n[0].celdas === 1, 'C80 cambió o se duplicó');
    c.anotar(`API: 409 en ambas variantes («${r1.body.detail}»). C80 conserva sus datos y sigue siendo única.`);
  },

  'CE-06': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    await page.getByRole('button', { name: 'Nueva celda' }).click();
    const envios: string[] = [];
    page.on('request', (r) => r.url().endsWith('/celdas') && r.method() === 'POST' && envios.push('POST'));
    const pantalla: string[] = [];
    const guardar = async (codigo: string, tipo: string, ubicacion: string, campo: string, nota: string) => {
      await page.getByLabel('Código', { exact: true }).fill(codigo);
      await page.locator('#tipo').selectOption(tipo);
      await page.getByLabel('Ubicación (opcional)').fill(ubicacion);
      await page.getByRole('button', { name: 'Guardar celda' }).click();
      const texto = (await page.locator(`#${campo}-error`).innerText()).trim();
      pantalla.push(`${nota}: ${texto ? `«${texto}»` : 'sin error'}`);
      return texto;
    };
    const rechazos = [
      await guardar('', 'CARRO', '', 'codigo', 'sin código'),
      await guardar('C79', '', '', 'tipo', 'sin tipo'),
      await guardar('   ', 'CARRO', '', 'codigo', 'código solo con espacios'),
      await guardar('C00', 'CARRO', '', 'codigo', 'C00'),
      await guardar('C100', 'CARRO', '', 'codigo', 'C100'),
      await guardar('M05', 'CARRO', '', 'codigo', 'M05 con tipo CARRO'),
      await guardar('C79', 'CARRO', 'U'.repeat(61), 'ubicacion', 'ubicación de 61'),
    ];
    await captura(page);
    await contexto.close();
    const api = await entrar(a);
    const servidor: [string, Record<string, unknown>][] = [
      ['sin código', { tipo: 'CARRO' }], ['sin tipo', { codigo: 'C79' }], ['código solo con espacios', { codigo: '   ', tipo: 'CARRO' }],
      ['tipo solo con espacios', { codigo: 'C79', tipo: '   ' }], ['C00', { codigo: 'C00', tipo: 'CARRO' }], ['C100', { codigo: 'C100', tipo: 'CARRO' }],
      ['M05 con tipo CARRO', { codigo: 'M05', tipo: 'CARRO' }], ['ubicación de 61', { codigo: 'C79', tipo: 'CARRO', ubicacion: 'U'.repeat(61) }],
    ];
    const noRechazados: string[] = [];
    for (const [nota, cuerpo] of servidor) {
      const r = await api.post('/celdas', cuerpo, nota);
      if (r.status !== 422) noRechazados.push(`${nota}: ${r.status}`);
    }
    const c99 = await api.post('/celdas', { codigo: 'C99', tipo: 'CARRO', ubicacion: '' }, 'límite válido: C99 con ubicación vacía');
    const c85 = await api.post('/celdas', { codigo: 'C85', tipo: 'CARRO', ubicacion: 'U'.repeat(60) }, 'límite válido: ubicación de 60 caracteres');
    const c01 = await api.post('/celdas', { codigo: 'C01', tipo: 'CARRO' }, 'C01: formato válido, pero ya existe');
    if (c99.status === 201) E.celdas.C99 = c99.body.id;
    if (c85.status === 201) E.celdas.C85 = c85.body.id;
    // M05 existe en las semillas como celda MOTO: lo rechazado es M05 con tipo CARRO.
    const incompletas = await consulta('celdas con los valores rechazados', "SELECT count(*)::int AS celdas FROM celda WHERE upper(trim(codigo)) IN ('C00', 'C100', 'C79', '') OR (upper(codigo) = 'M05' AND tipo = 'CARRO') OR length(ubicacion) > 60");
    verificar(rechazos.every((t) => t.length > 0) && envios.length === 0, `pantalla: ${pantalla.join('; ')}`);
    verificar(noRechazados.length === 0, `el servidor no respondió 422 en: ${noRechazados.join(', ')}`);
    verificar(c99.status === 201 && c85.status === 201, `C99: ${c99.status}, ubicación de 60: ${c85.status} (se esperaba 201)`);
    verificar(c01.status === 409, `C01: ${c01.status} (se esperaba 409 por duplicado, no 422)`);
    verificar(incompletas[0].celdas === 0, 'se guardó una celda con un valor rechazado');
    c.anotar(`Pantalla: ${pantalla.join('; ')}; sin enviar nada. Servidor: 422 en los ${servidor.length} rechazos. C99 con ubicación vacía y C85 con ubicación de 60 caracteres: 201. C01: 409 «${c01.body.detail}» (supera el formato). Ninguna celda incompleta.`);
  },

  'CE-07': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const id = E.celdas.C80;
    const estancias = () => consulta('estancias de la celda', 'SELECT count(*)::int AS estancias FROM estancia WHERE celda_id = $1', [id]);
    const antes = (await estancias())[0].estancias;
    precondicion(antes === 0, 'C80 tiene movimientos');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    await buscarCelda(page, 'C80');
    await page.getByRole('button', { name: 'Editar C80' }).click();
    await page.getByLabel('Código', { exact: true }).fill('C86');
    await page.getByLabel('Ubicación (opcional)').fill('Plan de pruebas: editada en CE-07');
    await page.getByRole('button', { name: 'Guardar celda' }).click();
    const exito = await page.getByText('Celda C86 actualizada correctamente.').waitFor().then(() => true, () => false);
    await captura(page);
    await page.reload();
    await abrirCeldas(page);
    await buscarCelda(page, 'C86');
    const fila = (await filasCeldas(page).allInnerTexts()).join(' / ');
    await captura(page, 'recargada');
    await contexto.close();
    const api = await entrar(a);
    const det = await api.get(`/celdas/${id}`, 'consultar la celda por su identificador');
    const editar = det.body.auditoria?.filter((x: any) => x.accion === 'EDITAR').at(-1);
    const despues = (await estancias())[0].estancias;
    verificar(exito, 'no aparece «Celda C86 actualizada correctamente.»');
    verificar(det.body.id === id && det.body.codigo === 'C86' && det.body.ubicacion === 'Plan de pruebas: editada en CE-07', `celda ${id}: ${det.body.codigo} «${det.body.ubicacion}»`);
    verificar(fila.includes('C86'), `al recargar: ${fila}`);
    verificar(despues === 0, 'se abrieron o cerraron estancias');
    verificar(!!editar?.detalle && String(editar.actor).includes(a.usuario), `auditoría EDITAR: ${JSON.stringify(editar)}`);
    E.celdas.C86 = id;
    c.anotar(`«Celda C86 actualizada correctamente.». Al recargar se ve C86; el identificador ${id} se conserva con el código y la ubicación nuevos. Sin estancias. Auditoría: EDITAR por ${editar.actor}, detalle «${editar.detalle}».`);
  },

  'CE-08': async (c) => {
    const api = await entrar(cuenta('admin_prueba'));
    precondicion(!!E.celdas.C86 && !!E.celdas.C85, 'faltan dos celdas sin historial (C86 y C85)');
    const antes = [await celdaBd('C86 antes', 'C86'), await celdaBd('C85 antes', 'C85')];
    const r = await api.patch(`/celdas/${E.celdas.C86}`, { codigo: 'C85' }, 'cambiar el código de C86 por el de C85');
    const despues = [await celdaBd('C86 después', 'C86'), await celdaBd('C85 después', 'C85')];
    verificar(r.status === 409, `API: ${r.status} (se esperaba 409)`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues), 'alguna celda cambió');
    c.anotar(`API: 409 «${r.body.detail}». C86 y C85 conservan sus datos.`);
  },

  'CE-09': async (c) => {
    const api = await entrar(cuenta('admin_prueba'));
    const antes = await consulta('celdas antes', 'SELECT count(*)::int AS celdas, max(id)::int AS max_id FROM celda');
    const r = await api.patch(`/celdas/${NO_EXISTE}`, { ubicacion: 'Cambio válido' }, 'actualizar una celda inexistente');
    const despues = await consulta('celdas después', "SELECT count(*)::int AS celdas, max(id)::int AS max_id, count(*) FILTER (WHERE ubicacion = 'Cambio válido')::int AS con_el_cambio FROM celda");
    verificar(r.status === 404, `API: ${r.status} (se esperaba 404)`);
    verificar(antes[0].celdas === despues[0].celdas && antes[0].max_id === despues[0].max_id && despues[0].con_el_cambio === 0, 'se creó o modificó una celda');
    c.anotar(`API: 404 «${r.body.detail}». No se crea ni se modifica ninguna celda.`);
  },

  'CE-10': async (c, browser) => {
    const a = cuenta('admin_prueba');
    precondicion(!!E.celdas.C83, 'C83 no existe (CE-04)');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    await buscarCelda(page, 'C83');
    await page.getByRole('button', { name: 'Inhabilitar C83' }).click();
    const dialogo = page.getByRole('alertdialog');
    const confirmacion = (await dialogo.locator('p').innerText()).trim();
    await captura(page, 'confirmacion');
    await dialogo.getByRole('button', { name: 'Sí, inhabilitar' }).click();
    const exito = await page.getByText('Celda C83 inhabilitada: ya no se asigna a nuevas entradas.').waitFor().then(() => true, () => false);
    await page.reload();
    await abrirCeldas(page);
    await buscarCelda(page, 'C83');
    const fila = (await filasCeldas(page).allInnerTexts()).join(' / ');
    await captura(page);
    await contexto.close();
    const api = await entrar(a);
    const det = await api.get(`/celdas/${E.celdas.C83}`, 'consultar C83 por su identificador');
    const inh = det.body.auditoria?.filter((x: any) => x.accion === 'INHABILITAR').at(-1);
    verificar(confirmacion.startsWith('¿Inhabilitar la celda C83 (Bloque C, nivel 8)?'), `confirmación: «${confirmacion}»`);
    verificar(exito && fila.includes('Inhabilitada'), `al recargar: ${fila}`);
    verificar(det.status === 200 && det.body.estado === 'INHABILITADA', `consulta: ${det.status} ${det.body.estado}`);
    verificar(!!inh && String(inh.actor).includes(a.usuario), 'la auditoría no registra INHABILITAR');
    c.anotar(`Confirmación: «${confirmacion}». C83 queda Inhabilitada en el catálogo y la consulta responde 200 con estado INHABILITADA (no se elimina). Auditoría: INHABILITAR por ${inh.actor}.`);
  },

  'CE-11': async (c) => {
    const api = await entrar(cuenta('admin_prueba'));
    const historial = () => consulta('estancias de C81', "SELECT e.id, v.placa, e.entrada, e.salida FROM estancia e JOIN celda c ON c.id = e.celda_id JOIN vehiculo v ON v.id = e.vehiculo_id WHERE c.codigo = 'C81' ORDER BY e.id");
    const antes = await historial();
    precondicion(antes.length > 0 && antes.every((e) => e.salida), 'C81 no tiene una estancia cerrada');
    const r = await api.post(`/celdas/${E.celdas.C81}/inhabilitar`, undefined, 'inhabilitar C81');
    const det = await api.get(`/celdas/${E.celdas.C81}`, 'consultar C81');
    const despues = await historial();
    const h = await api.get(`/reportes/historial?placa=${antes[0].placa}`, 'historial consultable de la estancia en C81');
    verificar(r.status === 200 && det.body.estado === 'INHABILITADA' && det.body.tiene_historial === true, `inhabilitar: ${r.status}, estado ${det.body.estado}`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues), 'el historial de C81 cambió');
    verificar(h.body.items.some((x: any) => x.celda === 'C81'), 'el historial no muestra la estancia en C81');
    c.anotar(`La inhabilitación se permite (200, estado INHABILITADA, con historial). ${antes.length === 1 ? 'La estancia cerrada de C81 queda intacta y el historial la sigue mostrando.' : `Las ${antes.length} estancias de C81 quedan intactas y el historial las sigue mostrando.`}`);
  },

  'CE-12': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    await buscarCelda(page, 'C82');
    const fila = filasCeldas(page).first();
    const boton = await page.getByRole('button', { name: 'Inhabilitar C82' }).count();
    const motivo = await fila.getByText('Ocupada: primero debe salir el vehículo').isVisible();
    await captura(page);
    await contexto.close();
    const antes = await consulta('C82 y su estancia abierta antes', "SELECT c.habilitada, e.id AS estancia, e.salida FROM celda c JOIN estancia e ON e.celda_id = c.id AND e.salida IS NULL WHERE c.codigo = 'C82'");
    const api = await entrar(a);
    const r = await api.post(`/celdas/${E.celdas.C82}/inhabilitar`, undefined, 'intentar inhabilitar C82 (ocupada)');
    const despues = await consulta('C82 y su estancia abierta después', "SELECT c.habilitada, e.id AS estancia, e.salida FROM celda c JOIN estancia e ON e.celda_id = c.id AND e.salida IS NULL WHERE c.codigo = 'C82'");
    verificar(boton === 0 && motivo, `pantalla: botón Inhabilitar ${boton}, motivo visible ${motivo}`);
    verificar(r.status === 409 && r.body.detail === 'La celda C82 está ocupada: primero debe salir el vehículo.', `API: ${r.status} ${JSON.stringify(r.body)}`);
    verificar(JSON.stringify(antes) === JSON.stringify(despues) && despues.length === 1, 'la celda o la estancia cambió');
    c.anotar('La pantalla impide la acción: en la fila de C82 no aparece «Inhabilitar» y se muestra «Ocupada: primero debe salir el vehículo». API: 409 «La celda C82 está ocupada: primero debe salir el vehículo.». La celda y la estancia abierta conservan sus datos.');
  },

  'CE-13': async (c) => {
    const s1 = await entrar(cuenta('admin_prueba'), 'primera sesión de administrador');
    const s2 = await entrar(cuenta('admin_dos'), 'segunda sesión de administrador');
    const [r1, r2] = await Promise.all([
      s1.post('/celdas', { codigo: 'C84', tipo: 'CARRO' }, 'creación simultánea 1'),
      s2.post('/celdas', { codigo: 'C84', tipo: 'CARRO' }, 'creación simultánea 2'),
    ]);
    const n = await consulta('celdas C84', "SELECT count(*)::int AS celdas FROM celda WHERE upper(codigo) = 'C84'");
    const codigos = [r1.status, r2.status].sort();
    verificar(codigos[0] === 201 && codigos[1] === 409, `respuestas: ${r1.status} y ${r2.status} (se esperaba 201 y 409)`);
    verificar(n[0].celdas === 1, `celdas C84: ${n[0].celdas}`);
    c.anotar(`API, dos sesiones al mismo tiempo: ${r1.status} y ${r2.status}; existe exactamente una celda C84.`);
  },

  'CE-14': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const motivos: Record<string, string> = {
      C81: 'La celda C81 ya tuvo movimientos: su código y su tipo quedan fijos para que el historial siga siendo legible. Solo se puede editar su ubicación.',
      C82: 'La celda C82 está ocupada: su código y su tipo no se pueden cambiar.',
    };
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    const pantalla: string[] = [];
    for (const codigo of ['C81', 'C82']) {
      await buscarCelda(page, codigo);
      await page.getByRole('button', { name: `Editar ${codigo}` }).click();
      const aviso = (await page.getByRole('note').innerText()).trim();
      const bloqueados = (await page.getByLabel('Código', { exact: true }).isDisabled()) && (await page.locator('#tipo').isDisabled());
      pantalla.push(`${codigo}: ${bloqueados ? 'código y tipo bloqueados' : 'código o tipo editables'}, «${aviso}»`);
      await captura(page, codigo);
      verificar(aviso === motivos[codigo] && bloqueados, `pantalla ${codigo}: ${pantalla.at(-1)}`);
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
    }
    await contexto.close();
    const api = await entrar(a);
    const r81 = await api.patch(`/celdas/${E.celdas.C81}`, { codigo: 'M87', tipo: 'MOTO' }, 'cambiar código y tipo de C81 (con historial)');
    const r82 = await api.patch(`/celdas/${E.celdas.C82}`, { codigo: 'M88', tipo: 'MOTO' }, 'cambiar código y tipo de C82 (ocupada)');
    const ubic = await api.patch(`/celdas/${E.celdas.C81}`, { ubicacion: 'Plan de pruebas: ubicación editada en CE-14' }, 'cambiar solo la ubicación de C81');
    const bd = await consulta('C81 y C82 después', "SELECT codigo, tipo, ubicacion FROM celda WHERE codigo IN ('C81', 'C82') ORDER BY codigo");
    verificar(r81.status === 409 && r81.body.detail === 'La celda C81 ya tuvo movimientos: su código y su tipo no se pueden cambiar, para que el historial siga siendo legible. Solo se puede editar su ubicación.', `API C81: ${r81.status} ${JSON.stringify(r81.body)}`);
    verificar(r82.status === 409 && r82.body.detail === 'La celda C82 está ocupada: su código y su tipo no se pueden cambiar.', `API C82: ${r82.status} ${JSON.stringify(r82.body)}`);
    verificar(ubic.status === 200 && bd.find((f) => f.codigo === 'C81')?.ubicacion === 'Plan de pruebas: ubicación editada en CE-14', `ubicación de C81: ${ubic.status}`);
    verificar(bd.every((f) => f.tipo === 'CARRO'), 'cambió el tipo de alguna celda');
    c.anotar(`Pantalla: ${pantalla.join('; ')}. API: 409 en C81 («${r81.body.detail}») y en C82 («${r82.body.detail}»). La ubicación de C81 sí se modifica (200).`);
  },

  'CE-15': async (c) => {
    const admin = await entrar(cuenta('admin_prueba'), 'sesión de administrador (inhabilita y rehabilita)');
    const operador = await entrar(cuenta('operador_prueba'), 'sesión de operador (registra la entrada)');
    const siguiente = await consulta(
      'celda CARRO que sería la siguiente en asignarse (regla: nunca usada primero; entre ellas, por código)',
      `SELECT c.id, c.codigo, c.disponible_desde FROM celda c
        WHERE c.tipo = 'CARRO' AND c.habilitada AND NOT EXISTS (SELECT 1 FROM estancia e WHERE e.celda_id = c.id AND e.salida IS NULL)
        ORDER BY c.disponible_desde ASC NULLS FIRST, c.codigo LIMIT 1`,
    );
    precondicion(siguiente.length === 1, 'no hay celdas CARRO libres');
    const objetivo = siguiente[0];
    const inh = await admin.post(`/celdas/${objetivo.id}/inhabilitar`, undefined, `inhabilitar ${objetivo.codigo}`);
    precondicion(inh.status === 200, `no se pudo inhabilitar ${objetivo.codigo}: ${inh.status}`);
    const placa = await tomarCarro(operador);
    const r = await operador.post('/estancias/entrada', { placa }, 'registrar la entrada de un carro');
    const asignada = r.body?.celda;
    const reh = await admin.post(`/celdas/${objetivo.id}/rehabilitar`, undefined, `al final del caso: rehabilitar ${objetivo.codigo}`);
    if (r.status === 201) await operador.post('/estancias/salida', { placa }, 'al terminar: registrar la salida para liberar el carro');
    verificar(r.status === 201 && asignada?.codigo !== objetivo.codigo && asignada?.habilitada === true, `entrada: ${r.status}, celda ${asignada?.codigo}`);
    verificar(reh.status === 200, `rehabilitar ${objetivo.codigo}: ${reh.status}`);
    c.anotar(`La siguiente celda era ${objetivo.codigo}; se inhabilitó. La entrada de ${placa} recibió ${asignada.codigo}, libre y habilitada, nunca la inhabilitada. Al final ${objetivo.codigo} se rehabilitó (200).`);
  },

  'CE-16': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const antes = await celdaBd('C83 antes de rehabilitar', 'C83');
    precondicion(antes?.habilitada === false, 'C83 no está inhabilitada (CE-10)');
    const api = await entrar(a);
    const inicio = new Date();
    const r = await api.post(`/celdas/${E.celdas.C83}/rehabilitar`, undefined, 'rehabilitar C83');
    const det = await api.get(`/celdas/${E.celdas.C83}`, 'estado, fecha de disponibilidad y auditoría de C83');
    const reh = det.body.auditoria?.filter((x: any) => x.accion === 'REHABILITAR').at(-1);
    const desde = new Date(det.body.disponible_desde);
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await abrirCeldas(page);
    await buscarCelda(page, 'C83');
    const fila = (await filasCeldas(page).allInnerTexts()).join(' / ');
    await captura(page);
    await contexto.close();
    verificar(r.status === 200 && det.body.estado === 'LIBRE' && det.body.habilitada === true, `rehabilitar: ${r.status}, estado ${det.body.estado}`);
    verificar(desde.getTime() >= inicio.getTime() - 2000, `disponible desde ${det.body.disponible_desde}, antes de la rehabilitación (${inicio.toISOString()})`);
    verificar(fila.includes('Libre'), `catálogo: ${fila}`);
    verificar(!!reh && String(reh.actor).includes(a.usuario), 'la auditoría no registra REHABILITAR');
    c.anotar(`C83 vuelve a estar libre y habilitada; disponible desde ${det.body.disponible_desde} (la rehabilitación ocurrió a las ${inicio.toISOString()}). Auditoría: REHABILITAR por ${reh.actor}.`);
  },
};
