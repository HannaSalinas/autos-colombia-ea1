/** Casos US-01 a US-20 del plan de pruebas (hoja Casos). Los textos esperados son los del Excel. */
import { expect, type Browser, type Page } from '@playwright/test';
import {
  anonimo, captura, conToken, consulta, contrasenaAleatoria, escribirSecreto, ingresarUI, menu, nuevaPagina, opcionesMenu,
  precondicion, sesion, tokenDePantalla, verificar, type Api, type Caso,
} from './contexto';
import { crearCuenta, cuenta, E, entrar, idCuenta, NOMBRES, tomarCarro } from './escenario';

const MENU_ADMIN = ['Inicio', 'Control de acceso', 'Ocupación', 'Historial', 'Vehículos', 'Celdas', 'Cuentas de usuario'];
const MENU_OPERADOR = ['Inicio', 'Control de acceso', 'Ocupación', 'Historial', 'Vehículos', 'Celdas'];
const AVISO_SESION = 'Tu sesión venció o fue cerrada. Ingresa de nuevo.';
const CREDENCIALES = 'Usuario o contraseña inválidos.';
const DESACTIVADA = 'Tu cuenta está desactivada. Contacta al administrador.';
const igual = (a: string[], b: string[]) => JSON.stringify(a) === JSON.stringify(b);

async function textoVisible(page: Page, texto: string): Promise<boolean> {
  return page.getByText(texto, { exact: false }).first().isVisible().catch(() => false);
}

/** Pulsa «Buscar» y espera la respuesta de la API (networkidle se cumple antes de que salga la solicitud). */
async function buscarYEsperar(page: Page, ruta: string): Promise<void> {
  const respuesta = page.waitForResponse((r) => r.url().includes(ruta) && r.request().method() === 'GET');
  await page.getByRole('button', { name: 'Buscar', exact: true }).click();
  await respuesta;
  await page.waitForTimeout(300);
}

async function esperarIngreso(page: Page): Promise<void> {
  await page.waitForURL(/\/ingresar/, { timeout: 15_000 });
  await page.getByRole('heading', { level: 1, name: 'Ingresar' }).waitFor();
}

/** Abre una pantalla con sesión iniciada en un contexto nuevo del navegador. */
async function conSesionUI(browser: Browser, usuario: string, contrasena: string) {
  const { contexto, page } = await nuevaPagina(browser);
  await page.goto('/ingresar');
  await ingresarUI(page, usuario, contrasena);
  await menu(page).waitFor();
  return { contexto, page };
}

async function adminsActivos(): Promise<number> {
  const f = await consulta('administradores activos', "SELECT count(*)::int AS administradores_activos FROM cuenta_usuario WHERE rol = 'ADMINISTRADOR' AND activa");
  return f[0].administradores_activos;
}

export const CASOS_USUARIOS: Record<string, (c: Caso, browser: Browser) => Promise<void>> = {
  'US-01': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const api = await anonimo();
    const r = await api.post('/auth/login', { usuario: a.usuario, contrasena: a.contrasena }, 'login del administrador por API');
    verificar(r.status === 200, `API de login respondió ${r.status} (se esperaba 200)`);
    const { contexto, page } = await nuevaPagina(browser);
    await page.goto('/ingresar');
    await ingresarUI(page, a.usuario, a.contrasena);
    const opciones = await opcionesMenu(page);
    await captura(page);
    verificar(igual(opciones, MENU_ADMIN), `menú: ${opciones.join(', ')}`);
    verificar(await textoVisible(page, `Administrador · ${a.usuario}`), 'la cabecera no muestra «Administrador · admin_prueba»');
    verificar(await page.locator('.cuenta-nombre').innerText() === a.nombre, 'la cabecera no muestra el nombre de la persona');
    verificar(await page.getByRole('button', { name: 'Cerrar sesión' }).isVisible(), 'no aparece «Cerrar sesión»');
    c.anotar(`API de login: 200. Menú: ${opciones.map((o) => `«${o}»`).join(', ')}. Cabecera: «${a.nombre}», «Administrador · ${a.usuario}» y «Cerrar sesión».`);
    await contexto.close();
  },

  'US-02': async (c, browser) => {
    const o = cuenta('operador_prueba');
    const { contexto, page } = await conSesionUI(browser, o.usuario, o.contrasena);
    const opciones = await opcionesMenu(page);
    await captura(page);
    verificar(igual(opciones, MENU_OPERADOR), `menú: ${opciones.join(', ')}`);
    await menu(page).getByRole('link', { name: 'Celdas' }).click();
    await page.getByRole('heading', { level: 1, name: 'Celdas', exact: true }).waitFor();
    await page.getByRole('rowheader').first().waitFor();
    await captura(page, 'celdas');
    const acciones: Record<string, number> = {};
    for (const nombre of ['Nueva celda', 'Editar', 'Inhabilitar', 'Rehabilitar'])
      acciones[nombre] = await page.getByRole('button', { name: new RegExp(`^${nombre}`) }).count();
    verificar(Object.values(acciones).every((n) => n === 0), `acciones visibles: ${JSON.stringify(acciones)}`);
    c.anotar(`Acceso concedido. Menú: ${opciones.map((o) => `«${o}»`).join(', ')} (sin «Cuentas de usuario»). En Celdas no aparecen «Nueva celda», «Editar», «Inhabilitar» ni «Rehabilitar».`);
    await contexto.close();
  },

  'US-03': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const { contexto, page } = await nuevaPagina(browser);
    await page.goto('/ingresar');
    const textos: string[] = [];
    for (const [variante, usuario, clave] of [
      ['contraseña incorrecta', a.usuario, 'ClaveIncorrecta1'],
      ['usuario inexistente', 'usuario.inexistente', 'ClaveIncorrecta1'],
    ] as const) {
      await ingresarUI(page, usuario, clave);
      const alerta = page.getByRole('alert');
      await alerta.waitFor();
      textos.push((await alerta.innerText()).trim());
      await captura(page, variante === 'contraseña incorrecta' ? 'clave_incorrecta' : 'usuario_inexistente');
      verificar(page.url().includes('/ingresar'), `después de «${variante}» la URL es ${page.url()}`);
    }
    verificar(textos.every((t) => t === CREDENCIALES), `mensajes en pantalla: ${textos.map((t) => `«${t}»`).join(' / ')}`);
    const api = await anonimo();
    const r1 = await api.post('/auth/login', { usuario: a.usuario, contrasena: 'ClaveIncorrecta1' }, 'usuario existente, contraseña incorrecta');
    const r2 = await api.post('/auth/login', { usuario: 'usuario.inexistente', contrasena: 'ClaveIncorrecta1' }, 'usuario inexistente');
    verificar(r1.status === 401 && r2.status === 401, `API: ${r1.status} y ${r2.status} (se esperaba 401 en ambas)`);
    verificar(JSON.stringify(r1.body) === JSON.stringify(r2.body), 'los cuerpos de las dos respuestas 401 son distintos');
    const token = await page.evaluate(() => sessionStorage.getItem('autos-colombia.token'));
    verificar(!token, 'quedó un token guardado en el navegador');
    await page.goto('/control-acceso');
    await esperarIngreso(page);
    await captura(page, 'modulo_protegido');
    const tecnico = await page.getByText(/error|exception|traceback|undefined/i).count();
    verificar(tecnico === 0, 'aparece un texto técnico en la pantalla');
    c.anotar(`Pantalla: ambas variantes muestran «${CREDENCIALES}». API: 401 en ambas, con el mismo cuerpo ${JSON.stringify(r1.body)}. No queda token; al abrir /control-acceso vuelve a «Ingresar». Sin errores técnicos.`);
    await contexto.close();
  },

  'US-04': async (c, browser) => {
    const { contexto, page } = await nuevaPagina(browser);
    const envios: string[] = [];
    page.on('request', (r) => r.url().endsWith('/auth/login') && envios.push(r.method()));
    await page.goto('/ingresar');
    await page.getByLabel('Contraseña').fill('ClaveCualquiera1');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    verificar(await textoVisible(page, 'Escribe tu usuario.'), 'no se indica «Escribe tu usuario.»');
    await captura(page, 'usuario_vacio');
    await page.getByLabel('Contraseña').fill('');
    await page.getByLabel('Usuario').fill('admin_prueba');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    verificar(await textoVisible(page, 'Escribe tu contraseña.'), 'no se indica «Escribe tu contraseña.»');
    await captura(page, 'contrasena_vacia');
    verificar(envios.length === 0, 'la pantalla envió la solicitud con un campo vacío');
    const api = await anonimo();
    const r1 = await api.post('/auth/login', { usuario: '', contrasena: 'ClaveCualquiera1' }, 'usuario vacío');
    const r2 = await api.post('/auth/login', { usuario: 'admin_prueba', contrasena: '' }, 'contraseña vacía');
    verificar(r1.status === 422 && r2.status === 422, `API: ${r1.status} y ${r2.status} (se esperaba 422)`);
    verificar(!r1.body?.token && !r2.body?.token, 'la API entregó un token');
    c.anotar('Pantalla: «Escribe tu usuario.» y «Escribe tu contraseña.», sin enviar la solicitud. API: 422 en ambas, sin token (no hay sesión).');
    await contexto.close();
  },

  'US-05': async (c, browser) => {
    const vencido = process.env.TOKEN_VENCIDO ?? '';
    precondicion(vencido.length > 0, 'no se recibió el token vencido (lo genera el orquestador)');
    // Variante A: token vencido
    const apiVencido = await conToken(vencido, 'sesión con token vencido');
    const a1 = await apiVencido.get('/cuentas', 'operación protegida con token vencido');
    const a2 = await apiVencido.get('/celdas', 'consulta protegida con token vencido');
    verificar(a1.status === 401 && a2.status === 401, `token vencido: ${a1.status} y ${a2.status} (se esperaba 401)`);
    verificar(!a1.body?.items && !a2.body?.items, 'con el token vencido se entregó información protegida');
    const { contexto: ctxA, page: pA } = await nuevaPagina(browser);
    await pA.addInitScript((t) => sessionStorage.setItem('autos-colombia.token', t), vencido);
    await pA.goto('/gestion/celdas');
    await esperarIngreso(pA);
    await pA.waitForTimeout(1000);
    await captura(pA, 'token_vencido');
    const avisoA = await textoVisible(pA, AVISO_SESION);
    await ctxA.close();
    // Variante B: cuenta desactivada después de ingresar (marta.usuga; se reactiva al final)
    const admin = await entrar(cuenta('admin_prueba'));
    const marta = await sesion(E.marta.usuario, E.marta.contrasena, 'marta.usuga (contraseña de .env)');
    const { contexto: ctxB, page: pB } = await conSesionUI(browser, E.marta.usuario, E.marta.contrasena);
    const placa = await tomarCarro(admin);
    const d = await admin.post(`/cuentas/${E.marta.id}/desactivar`, undefined, 'desactivar a marta.usuga después de que ingresó');
    precondicion(d.status === 200, `no se pudo desactivar a marta.usuga: ${d.status}`);
    const b1 = await marta.get('/celdas', 'consulta protegida con la sesión de la cuenta desactivada');
    const b2 = await marta.post('/estancias/entrada', { placa }, 'intento de cambio con la sesión de la cuenta desactivada');
    const dentro = await admin.get(`/estancias/vehiculo/${placa}`, 'comprobar que no se registró la entrada');
    await menu(pB).getByRole('link', { name: 'Celdas' }).click();
    await esperarIngreso(pB);
    await pB.waitForTimeout(500);
    await captura(pB, 'cuenta_desactivada');
    const avisoB = await textoVisible(pB, AVISO_SESION);
    await ctxB.close();
    const re = await admin.post(`/cuentas/${E.marta.id}/reactivar`, undefined, 'restaurar: reactivar a marta.usuga');
    verificar(re.status === 200, 'no se pudo reactivar a marta.usuga');
    verificar(b1.status === 401 && b2.status === 401, `cuenta desactivada: ${b1.status} y ${b2.status} (se esperaba 401)`);
    verificar(!b1.body?.items && dentro.body?.esta_dentro === false, 'se entregó información o se registró la entrada');
    c.anotar(`API: 401 en ambas variantes (token vencido: ${a1.status}/${a2.status}; cuenta desactivada: ${b1.status}/${b2.status}); sin datos protegidos y sin cambios (${placa} sigue fuera).`);
    c.anotar(`Pantalla, cuenta desactivada: vuelve a «Ingresar» ${avisoB ? `con el aviso «${AVISO_SESION}»` : 'SIN el aviso'}. Pantalla, token vencido: vuelve a «Ingresar» ${avisoA ? `con el aviso «${AVISO_SESION}»` : 'SIN el aviso'}.`);
    verificar(avisoB, `con la cuenta desactivada, la pantalla vuelve al ingreso sin el aviso «${AVISO_SESION}»`);
    verificar(avisoA, `con el token vencido, la pantalla vuelve al ingreso sin el aviso «${AVISO_SESION}» (llega a /ingresar?volver=…)`);
  },

  'US-06': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByRole('heading', { level: 1, name: 'Cuentas de usuario' }).waitFor();
    const anterior = await conToken(await tokenDePantalla(page), 'token anterior de admin_prueba');
    const antes = await anterior.get('/auth/yo', 'el token funciona antes de cerrar sesión');
    precondicion(antes.status === 200, 'el token no funcionaba antes de cerrar sesión');
    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await esperarIngreso(page);
    const aviso = await textoVisible(page, 'Cerraste sesión.');
    await captura(page);
    await page.goto('/gestion/cuentas');
    await esperarIngreso(page);
    await page.goBack();
    await page.waitForLoadState('networkidle');
    const urlAtras = page.url();
    await captura(page, 'atras');
    const despues = await anterior.get('/auth/yo', 'reutilizar el token anterior');
    const cambio = await anterior.post('/celdas', { codigo: 'C79', tipo: 'CARRO' }, 'reutilizar el token anterior en una operación de cambio');
    verificar(aviso, 'la pantalla de ingreso no muestra «Cerraste sesión.»');
    verificar(urlAtras.includes('/ingresar'), `con el botón atrás quedó en ${urlAtras}`);
    verificar(despues.status === 401 && cambio.status === 401, `token anterior: ${despues.status} y ${cambio.status} (se esperaba 401)`);
    c.anotar(`Se muestra «Ingresar» con el aviso «Cerraste sesión.». Al abrir /gestion/cuentas y con el botón atrás vuelve a «Ingresar». El token anterior responde 401 (GET /auth/yo y POST /celdas): el cierre se aplica en el servidor.`);
    await contexto.close();
  },

  'US-07': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const nuevo = { usuario: 'operador.nuevo', nombre: 'Operador Nuevo de Prueba', rol: 'OPERADOR' as const, contrasena: contrasenaAleatoria() };
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByRole('button', { name: 'Nueva cuenta' }).click();
    await page.getByLabel('Nombre completo').fill(nuevo.nombre);
    await page.getByLabel('Nombre de usuario').fill(nuevo.usuario);
    await escribirSecreto(page.getByLabel('Contraseña inicial'), nuevo.contrasena);
    await page.locator('#rol').selectOption('OPERADOR');
    const respuesta = page.waitForResponse((r) => r.url().endsWith('/cuentas') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Crear cuenta' }).click();
    const r = await respuesta;
    const cuerpo = await r.json();
    c.api.push({ sesion: a.usuario, metodo: 'POST', ruta: '/cuentas', codigo: r.status(), solicitud: { nombre: nuevo.nombre, nombre_usuario: nuevo.usuario, contrasena: '«omitido»', rol: 'OPERADOR' }, respuesta: cuerpo, nota: 'creación desde la pantalla (respuesta capturada del navegador)' });
    verificar(r.status() === 201, `API de creación: ${r.status()} (se esperaba 201)`);
    E.cuentas[nuevo.usuario] = { ...nuevo, id: cuerpo.id };
    const exito = `Cuenta de ${nuevo.nombre} (${nuevo.usuario}) creada y activa.`;
    verificar(await textoVisible(page, exito), `no aparece «${exito}»`);
    await captura(page);
    await page.getByRole('button', { name: `Ver detalle de ${nuevo.nombre}` }).click();
    await page.getByRole('heading', { name: `Detalle de ${nuevo.nombre}` }).waitFor();
    const fila = page.getByRole('row').filter({ hasText: 'Creó la cuenta' });
    verificar(await fila.count() === 1 && (await fila.innerText()).includes(a.nombre), 'el detalle no muestra «Creó la cuenta» con el administrador');
    await captura(page, 'detalle');
    await contexto.close();
    const admin = await entrar(a);
    const det = await admin.get(`/cuentas/${cuerpo.id}`, 'detalle de la cuenta creada (auditoría)');
    const crear = det.body.auditoria?.find((e: any) => e.accion === 'CREAR');
    verificar(!!crear && String(crear.actor).includes(a.usuario) && !!crear.fecha, 'la auditoría no registra CREAR con el administrador y la fecha');
    verificar(det.body.activa === true && det.body.rol === 'OPERADOR', 'la cuenta no quedó activa con rol OPERADOR');
    const persona = await consulta('cuenta y persona vinculada', 'SELECT c.nombre_usuario, c.rol, c.activa, o.id AS persona_id, o.nombre AS persona FROM cuenta_usuario c JOIN operador o ON o.id = c.operador_id WHERE c.nombre_usuario = $1', [nuevo.usuario]);
    verificar(persona.length === 1 && persona[0].persona === nuevo.nombre, 'no existe la persona vinculada');
    const s = await anonimo();
    const login = await s.post('/auth/login', { usuario: nuevo.usuario, contrasena: nuevo.contrasena }, 'ingresar con la cuenta nueva');
    verificar(login.status === 200, `la cuenta nueva no ingresa: ${login.status}`);
    const permisos: string[] = login.body.cuenta.permisos;
    verificar(!permisos.includes('cuentas:gestionar') && !permisos.includes('celdas:gestionar'), `permisos: ${permisos.join(', ')}`);
    const { contexto: ctx2, page: p2 } = await conSesionUI(browser, nuevo.usuario, nuevo.contrasena);
    const opciones = await opcionesMenu(p2);
    await captura(p2, 'ingreso');
    await ctx2.close();
    verificar(igual(opciones, MENU_OPERADOR), `menú de la cuenta nueva: ${opciones.join(', ')}`);
    c.anotar(`API de creación: 201. «${exito}». Cuenta activa con su persona vinculada (${persona[0].persona}). Ingresa (200) con permisos de operador: ${permisos.join(', ')}. El detalle muestra «Creó la cuenta» por ${crear.actor} el ${crear.fecha}.`);
  },

  'US-08': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const nuevo = { usuario: 'admin.nuevo', nombre: 'Administrador Nuevo de Prueba', rol: 'ADMINISTRADOR' as const, contrasena: contrasenaAleatoria() };
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByRole('button', { name: 'Nueva cuenta' }).click();
    await page.getByLabel('Nombre completo').fill(nuevo.nombre);
    await page.getByLabel('Nombre de usuario').fill(nuevo.usuario);
    await escribirSecreto(page.getByLabel('Contraseña inicial'), nuevo.contrasena);
    await page.locator('#rol').selectOption('ADMINISTRADOR');
    const respuesta = page.waitForResponse((r) => r.url().endsWith('/cuentas') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Crear cuenta' }).click();
    const r = await respuesta;
    const cuerpo = await r.json();
    c.api.push({ sesion: a.usuario, metodo: 'POST', ruta: '/cuentas', codigo: r.status(), solicitud: { nombre: nuevo.nombre, nombre_usuario: nuevo.usuario, contrasena: '«omitido»', rol: 'ADMINISTRADOR' }, respuesta: cuerpo, nota: 'creación desde la pantalla (respuesta capturada del navegador)' });
    verificar(r.status() === 201, `API de creación: ${r.status()} (se esperaba 201)`);
    E.cuentas[nuevo.usuario] = { ...nuevo, id: cuerpo.id };
    await captura(page, 'creada');
    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await esperarIngreso(page);
    await ingresarUI(page, nuevo.usuario, nuevo.contrasena);
    const opciones = await opcionesMenu(page);
    await captura(page);
    verificar(igual(opciones, MENU_ADMIN), `menú de admin.nuevo: ${opciones.join(', ')}`);
    // Espera la ruta y el título de cada pantalla (Inicio también tiene un título h1).
    for (const [destino, ruta] of [['Control de acceso', '/control-acceso'], ['Cuentas de usuario', '/gestion/cuentas'], ['Celdas', '/gestion/celdas']]) {
      await menu(page).getByRole('link', { name: destino }).click();
      const abrio = await page.waitForURL(`**${ruta}`).then(() => page.getByRole('heading', { level: 1, name: destino, exact: true }).waitFor()).then(() => true, () => false);
      verificar(abrio, `no pudo abrir ${destino} (quedó en ${new URL(page.url()).pathname})`);
    }
    await contexto.close();
    c.anotar(`API de creación: 201. Después de cerrar sesión, admin.nuevo ingresa y ve todo el menú: ${opciones.map((o) => `«${o}»`).join(', ')}; abre Control de acceso, Cuentas de usuario y Celdas.`);
  },

  'US-09': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const contar = () => consulta('cuentas y personas', 'SELECT (SELECT count(*) FROM cuenta_usuario)::int AS cuentas, (SELECT count(*) FROM operador)::int AS personas');
    const antes = (await contar())[0];
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    const mensajes: string[] = [];
    for (const [variante, usuario] of [['exacto', 'operador_prueba'], ['normalizado', ' Operador_Prueba ']] as const) {
      await page.getByRole('button', { name: 'Nueva cuenta' }).click().catch(() => undefined);
      await page.getByLabel('Nombre completo').fill('Persona Duplicada');
      await page.getByLabel('Nombre de usuario').fill(usuario);
      await escribirSecreto(page.getByLabel('Contraseña inicial'), contrasenaAleatoria());
      await page.locator('#rol').selectOption('OPERADOR');
      const respuesta = page.waitForResponse((r) => r.url().endsWith('/cuentas') && r.request().method() === 'POST');
      await page.getByRole('button', { name: 'Crear cuenta' }).click();
      const r = await respuesta;
      c.api.push({ sesion: a.usuario, metodo: 'POST', ruta: '/cuentas', codigo: r.status(), solicitud: { nombre_usuario: usuario, contrasena: '«omitido»', rol: 'OPERADOR' }, respuesta: await r.json(), nota: `pantalla, variante ${variante}` });
      const error = (await page.locator('#usuario-error').innerText()).trim();
      mensajes.push(error);
      await captura(page, variante);
      verificar(r.status() === 409, `pantalla (${variante}): ${r.status()} (se esperaba 409)`);
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
    }
    await contexto.close();
    const api = await entrar(a);
    const r1 = await api.post('/cuentas', { nombre: 'Persona Duplicada', nombre_usuario: 'operador_prueba', contrasena: contrasenaAleatoria(), rol: 'OPERADOR' }, 'API, usuario exacto');
    const r2 = await api.post('/cuentas', { nombre: 'Persona Duplicada', nombre_usuario: ' Operador_Prueba ', contrasena: contrasenaAleatoria(), rol: 'OPERADOR' }, 'API, con espacios y mayúsculas');
    const despues = (await contar())[0];
    verificar(mensajes.every((m) => m === 'Ese nombre de usuario ya está en uso.'), `mensajes: ${mensajes.map((m) => `«${m}»`).join(' / ')}`);
    verificar(r1.status === 409 && r2.status === 409, `API: ${r1.status} y ${r2.status} (se esperaba 409)`);
    verificar(r1.body.detail === 'Ese nombre de usuario ya está en uso.' && r2.body.detail === r1.body.detail, 'la API no responde «Ese nombre de usuario ya está en uso.»');
    verificar(antes.cuentas === despues.cuentas && antes.personas === despues.personas, `cuentas ${antes.cuentas}→${despues.cuentas}, personas ${antes.personas}→${despues.personas}`);
    c.anotar(`Pantalla y API rechazan ambas variantes con «Ese nombre de usuario ya está en uso.» (409). Cuentas ${antes.cuentas}→${despues.cuentas} y personas ${antes.personas}→${despues.personas}: sin datos parciales.`);
  },

  'US-10': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const contar = () => consulta('cuentas y personas', 'SELECT (SELECT count(*) FROM cuenta_usuario)::int AS cuentas, (SELECT count(*) FROM operador)::int AS personas');
    const antes = (await contar())[0];
    // Pantalla
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByRole('button', { name: 'Nueva cuenta' }).click();
    const envios: string[] = [];
    page.on('request', (r) => r.url().endsWith('/cuentas') && r.method() === 'POST' && envios.push('POST'));
    await page.getByRole('button', { name: 'Crear cuenta' }).click();
    const vacios = await Promise.all(['#nombre-error', '#usuario-error', '#contrasena-error', '#rol-error'].map((s) => page.locator(s).innerText()));
    await captura(page, 'vacios');
    verificar(vacios.every((t) => t.trim().length > 0), `campos vacíos sin mensaje: ${JSON.stringify(vacios)}`);
    const pantalla: string[] = [];
    const probar = async (campo: string, valor: string, error: string, secreto = false) => {
      const input = page.locator(campo);
      if (secreto) {
        await escribirSecreto(input, valor);
      } else await input.fill(valor);
      await input.blur();
      const texto = (await page.locator(error).innerText()).trim();
      pantalla.push(`${campo}=${valor.length} car.: ${texto ? `«${texto}»` : 'sin error'}`);
      return texto;
    };
    const invalidos: [string, string, string, boolean?][] = [
      ['#nombre', '   ', '#nombre-error'], ['#nombre', 'Al', '#nombre-error'], ['#nombre', 'N'.repeat(81), '#nombre-error'],
      ['#nombre_usuario', 'abc', '#usuario-error'], ['#nombre_usuario', 'u'.repeat(31), '#usuario-error'],
      ['#contrasena', 'clave12', '#contrasena-error', true], ['#contrasena', 'c1'.repeat(32) + 'c', '#contrasena-error', true],
      ['#contrasena', 'clavesinnumero', '#contrasena-error', true],
    ];
    const sinError: string[] = [];
    for (const [campo, valor, error, secreto] of invalidos) if (!(await probar(campo, valor, error, secreto))) sinError.push(`${campo}=${valor.length}`);
    await captura(page, 'invalidos');
    const validos: [string, string, string, boolean?][] = [
      ['#nombre', 'Ana', '#nombre-error'], ['#nombre', 'N'.repeat(80), '#nombre-error'],
      ['#nombre_usuario', 'abcd', '#usuario-error'], ['#nombre_usuario', 'u'.repeat(30), '#usuario-error'],
      ['#contrasena', 'clave123', '#contrasena-error', true], ['#contrasena', 'c1'.repeat(32), '#contrasena-error', true],
    ];
    const conError: string[] = [];
    for (const [campo, valor, error, secreto] of validos) if (await probar(campo, valor, error, secreto)) conError.push(`${campo}=${valor.length}`);
    await captura(page, 'validos');
    await contexto.close();
    verificar(sinError.length === 0, `la pantalla acepta valores inválidos: ${sinError.join(', ')}`);
    verificar(conError.length === 0, `la pantalla rechaza límites válidos: ${conError.join(', ')}`);
    verificar(envios.length === 0, 'la pantalla envió una solicitud con datos inválidos');
    // Servidor
    const api = await entrar(a);
    const base = { nombre: 'Persona Límite', nombre_usuario: 'limite.uno', contrasena: 'clave123', rol: 'OPERADOR' };
    const casos: [string, Record<string, unknown>][] = [
      ['sin nombre', { ...base, nombre: undefined }], ['sin usuario', { ...base, nombre_usuario: undefined }],
      ['sin contraseña', { ...base, contrasena: undefined }], ['sin rol', { ...base, rol: undefined }],
      ['nombre solo con espacios', { ...base, nombre: '   ' }], ['usuario abc (3)', { ...base, nombre_usuario: 'abc' }],
      ['usuario de 31', { ...base, nombre_usuario: 'u'.repeat(31) }], ['nombre Al (2)', { ...base, nombre: 'Al' }],
      ['nombre de 81', { ...base, nombre: 'N'.repeat(81) }], ['contraseña clave12 (7)', { ...base, contrasena: 'clave12' }],
      ['contraseña de 65', { ...base, contrasena: 'c1'.repeat(32) + 'c' }], ['contraseña sin número', { ...base, contrasena: 'clavesinnumero' }],
    ];
    const rechazos: string[] = [];
    for (const [nota, cuerpo] of casos) {
      const r = await api.post('/cuentas', Object.fromEntries(Object.entries(cuerpo).filter(([, v]) => v !== undefined)), nota);
      if (r.status !== 422) rechazos.push(`${nota}: ${r.status}`);
    }
    const v1 = await api.post('/cuentas', { nombre: 'Ana', nombre_usuario: 'abcd', contrasena: 'clave123', rol: 'OPERADOR' }, 'límites válidos inferiores: Ana (3), abcd (4), clave123 (8)');
    const v2 = await api.post('/cuentas', { nombre: 'N'.repeat(80), nombre_usuario: 'u'.repeat(30), contrasena: 'c1'.repeat(32), rol: 'OPERADOR' }, 'límites válidos superiores: nombre de 80, usuario de 30, contraseña de 64');
    const despues = (await contar())[0];
    verificar(rechazos.length === 0, `el servidor no respondió 422 en: ${rechazos.join(', ')}`);
    verificar(v1.status === 201 && v2.status === 201, `límites válidos: ${v1.status} y ${v2.status} (se esperaba 201)`);
    verificar(despues.cuentas - antes.cuentas === 2 && despues.personas - antes.personas === 2, `cuentas +${despues.cuentas - antes.cuentas}, personas +${despues.personas - antes.personas} (se esperaba +2 y +2: solo los válidos)`);
    c.anotar(`Pantalla: los 4 campos vacíos muestran su mensaje; ${pantalla.join('; ')}; sin enviar nada. Servidor: 422 en los ${casos.length} rechazos; los límites válidos se crean (201 y 201). Cuentas y personas +2 cada una: ninguna incompleta.`);
  },

  'US-11': async (c) => {
    const api = await entrar(cuenta('admin_prueba'));
    const r = await api.post('/cuentas', { nombre: 'Rol Inválido', nombre_usuario: 'rol.invalido', contrasena: contrasenaAleatoria(), rol: 'SUPERUSUARIO' }, 'rol distinto de ADMINISTRADOR y OPERADOR');
    const filas = await consulta('cuentas con ese usuario o con un rol distinto de los dos válidos', "SELECT count(*) FILTER (WHERE nombre_usuario = 'rol.invalido')::int AS con_ese_usuario, count(*) FILTER (WHERE rol NOT IN ('ADMINISTRADOR', 'OPERADOR'))::int AS con_rol_arbitrario FROM cuenta_usuario");
    verificar(r.status === 422, `API: ${r.status} (se esperaba 422)`);
    verificar(filas[0].con_ese_usuario === 0 && filas[0].con_rol_arbitrario === 0, 'se guardó una cuenta con el rol inválido');
    c.anotar('API: 422. Ninguna cuenta con ese usuario ni con un rol distinto de ADMINISTRADOR y OPERADOR.');
  },

  'US-12': async (c) => {
    const api = await entrar(cuenta('admin_prueba'));
    const ficticia = await crearCuenta(api, 'cuenta.ficticia', 'Cuenta Ficticia de Prueba', 'OPERADOR', 'crear la cuenta ficticia (contraseña generada en memoria)');
    const lista = await api.get('/cuentas?buscar=cuenta.ficticia', 'consultar cuentas');
    const detalle = await api.get(`/cuentas/${ficticia.id}`, 'detalle de la cuenta');
    const textos = [JSON.stringify(lista.body), JSON.stringify(detalle.body), JSON.stringify(c.api.find((x) => x.ruta === '/cuentas' && x.metodo === 'POST')?.respuesta ?? {})];
    const expone = textos.some((t) => t.includes(ficticia.contrasena) || /\$2[aby]\$/.test(t) || /hash|contrasena/i.test(t));
    const filas = await consulta('cómo se guarda la contraseña (solo algoritmo y costo: el hash no se reproduce)', "SELECT nombre_usuario, substring(hash_contrasena FROM 1 FOR 7) AS algoritmo_y_costo, length(hash_contrasena) AS largo FROM cuenta_usuario WHERE nombre_usuario = 'cuenta.ficticia'");
    const costo = Number(String(filas[0]?.algoritmo_y_costo ?? '').split('$')[2]);
    const login = await (await anonimo()).post('/auth/login', { usuario: ficticia.usuario, contrasena: ficticia.contrasena }, 'iniciar sesión con la cuenta ficticia');
    verificar(!expone, 'una respuesta expone la contraseña o el hash');
    verificar(/^\$2[aby]\$/.test(filas[0]?.algoritmo_y_costo ?? '') && costo >= 12 && filas[0].largo === 60, `la base guarda: ${filas[0]?.algoritmo_y_costo}, largo ${filas[0]?.largo}`);
    verificar(login.status === 200, `login: ${login.status}`);
    c.anotar(`Las respuestas de creación, listado y detalle no traen la contraseña ni el hash. La base guarda un hash bcrypt (${filas[0].algoritmo_y_costo}…, costo ${costo}, 60 caracteres), no texto plano. El login responde 200.`);
  },

  'US-13': async (c) => {
    const a = await entrar(cuenta('admin_prueba'), 'primera sesión de administrador');
    const b = await entrar(cuenta('admin_dos'), 'segunda sesión de administrador');
    const cuerpo = (usuario: string) => ({ nombre: 'Pedro Simultáneo', nombre_usuario: usuario, contrasena: contrasenaAleatoria(), rol: 'OPERADOR' });
    const [r1, r2] = await Promise.all([a.post('/cuentas', cuerpo('pedro.x'), 'creación simultánea 1'), b.post('/cuentas', cuerpo('PEDRO.X'), 'creación simultánea 2')]);
    const filas = await consulta('cuentas con el usuario pedro.x', "SELECT count(*)::int AS cuentas FROM cuenta_usuario WHERE lower(nombre_usuario) = 'pedro.x'");
    const codigos = [r1.status, r2.status].sort();
    verificar(codigos[0] === 201 && codigos[1] === 409, `respuestas: ${r1.status} y ${r2.status} (se esperaba 201 y 409)`);
    verificar(filas[0].cuentas === 1, `cuentas pedro.x: ${filas[0].cuentas}`);
    c.anotar(`API, dos sesiones al mismo tiempo: ${r1.status} y ${r2.status}; existe exactamente 1 cuenta pedro.x.`);
  },

  'US-14': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const api = await entrar(a);
    // Precondición: cuentas activas y desactivadas de ambos roles. Se desactiva la cuenta ficticia de US-12.
    const ficticia = cuenta('cuenta.ficticia');
    const d = await api.post(`/cuentas/${ficticia.id}/desactivar`, undefined, 'preparación: dejar una cuenta desactivada (cuenta.ficticia)');
    precondicion(d.status === 200, 'no se pudo desactivar la cuenta ficticia');
    const comprobar = async (consultaUrl: string, nota: string, cumple: (x: any) => boolean) => {
      const r = await api.get(consultaUrl, nota);
      verificar(r.status === 200 && r.body.items.length > 0 && r.body.items.every(cumple), `${nota}: ${r.status}, ${r.body.items?.length} resultados, alguno no coincide`);
      return r.body.items.length;
    };
    const n1 = await comprobar('/cuentas?buscar=Operador%20de%20Prueba', 'buscar por nombre', (x) => x.nombre.toLowerCase().includes('operador de prueba'));
    const n2 = await comprobar('/cuentas?buscar=operador_prueba', 'buscar por usuario', (x) => x.nombre_usuario.includes('operador_prueba'));
    const n3 = await comprobar('/cuentas?rol=OPERADOR&limit=100', 'filtrar por rol OPERADOR', (x) => x.rol === 'OPERADOR');
    const n4 = await comprobar('/cuentas?estado=INACTIVA&limit=100', 'filtrar por estado desactivada', (x) => x.activa === false);
    const n5 = await comprobar('/cuentas?rol=ADMINISTRADOR&estado=ACTIVA&limit=100', 'filtrar por rol y estado', (x) => x.rol === 'ADMINISTRADOR' && x.activa);
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByRole('row').nth(1).waitFor();
    const columnas = (await page.getByRole('columnheader').allInnerTexts()).map((t) => t.trim());
    await captura(page);
    verificar(['Nombre completo', 'Usuario', 'Rol', 'Estado', 'Creada'].every((col) => columnas.includes(col)), `columnas: ${columnas.join(', ')}`);
    await page.getByLabel('Buscar por nombre o usuario').fill('Operador de Prueba');
    await buscarYEsperar(page, '/cuentas?');
    const filas = await page.getByRole('row').filter({ hasNot: page.getByRole('columnheader') }).allInnerTexts();
    await captura(page, 'busqueda');
    verificar(filas.length > 0 && filas.every((f) => f.includes('Operador de Prueba')), `búsqueda en pantalla: ${filas.length} filas`);
    await page.getByLabel('Buscar por nombre o usuario').fill('');
    await page.locator('#filtro-rol').selectOption('OPERADOR');
    await page.locator('#filtro-estado').selectOption('INACTIVA');
    await buscarYEsperar(page, '/cuentas?');
    const filtradas = await page.getByRole('row').filter({ hasNot: page.getByRole('columnheader') }).allInnerTexts();
    await captura(page, 'filtros');
    await contexto.close();
    verificar(filtradas.length > 0 && filtradas.every((f) => f.includes('Operador') && f.includes('Desactivada')), `filtro en pantalla: ${filtradas.length} filas`);
    c.anotar(`Listado con columnas ${columnas.filter((x) => x !== 'Acciones').map((x) => `«${x}»`).join(', ')}. Búsqueda por nombre (${n1}) y por usuario (${n2}), filtro por rol (${n3}), por estado (${n4}) y combinado (${n5}): solo cuentas que coinciden, en pantalla y en la API.`);
  },

  'US-15': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const api = await entrar(a);
    const r = await api.get('/cuentas?buscar=zzz-sin-coincidencias', 'búsqueda sin coincidencias');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByLabel('Buscar por nombre o usuario').fill('zzz-sin-coincidencias');
    await page.getByRole('button', { name: 'Buscar', exact: true }).click();
    const vacio = await page.getByText('No hay cuentas que coincidan.').waitFor().then(() => true, () => false);
    const alerta = await page.getByRole('alert').count();
    await captura(page);
    await contexto.close();
    verificar(r.status === 200 && r.body.items.length === 0 && r.body.total === 0, `API: ${r.status}, ${r.body.items?.length} resultados`);
    verificar(vacio && alerta === 0, 'la pantalla no muestra «No hay cuentas que coincidan.» o muestra un error');
    c.anotar('API: 200 con lista vacía (total 0). La pantalla muestra «No hay cuentas que coincidan.», sin error.');
  },

  'US-20': async (c, browser) => {
    const o = cuenta('operador_prueba');
    const api = await entrar(o);
    const placa = await tomarCarro(api);
    const { contexto, page } = await conSesionUI(browser, o.usuario, o.contrasena);
    await menu(page).getByRole('link', { name: 'Control de acceso' }).click();
    await page.getByRole('heading', { level: 1, name: 'Control de acceso' }).waitFor();
    const selectores = await page.locator('select').count();
    const responsable = await page.locator('.responsable').innerText();
    await page.getByLabel('Placa de entrada').fill(placa);
    await page.getByRole('button', { name: 'Registrar entrada' }).click();
    await page.getByText(`Entrada registrada: ${placa}`).waitFor();
    await captura(page, 'entrada');
    await page.getByLabel('Placa a consultar').fill(placa);
    await page.getByRole('button', { name: 'Consultar vehículo' }).click();
    await page.getByRole('button', { name: 'Confirmar salida' }).click();
    await page.getByText(`Salida registrada: ${placa}`).waitFor();
    await captura(page, 'salida');
    await menu(page).getByRole('link', { name: 'Historial' }).click();
    await page.getByLabel('Placa').fill(placa);
    await page.getByRole('button', { name: 'Buscar', exact: true }).click();
    await page.getByRole('row').filter({ hasText: placa }).first().waitFor();
    const filaHistorial = await page.getByRole('row').filter({ hasText: placa }).first().innerText();
    await captura(page, 'historial');
    await contexto.close();
    E.placaOperador = placa;
    const h = await api.get(`/reportes/historial?placa=${placa}`, 'historial de la estancia registrada por operador_prueba');
    const estancia = h.body.items[0];
    const otra = await tomarCarro(api);
    const conOperador = await api.post('/estancias/entrada', { placa: otra, operador_id: 1 }, 'entrada con operador_id en el cuerpo');
    const dentro = await api.get(`/estancias/vehiculo/${otra}`, 'comprobar que esa entrada no se registró');
    const ea1 = await consulta(
      'responsables de los movimientos (entradas y salidas) anteriores a esta ejecución: la historia de la EA1',
      `SELECT 'entrada' AS movimiento, o.nombre AS responsable, count(*)::int AS movimientos
         FROM estancia e JOIN operador o ON o.id = e.operador_entrada_id WHERE e.entrada < $1 GROUP BY 1, 2
       UNION ALL
       SELECT 'salida', o.nombre, count(*)::int
         FROM estancia e JOIN operador o ON o.id = e.operador_salida_id WHERE e.salida < $1 GROUP BY 1, 2
       ORDER BY 1, 2`,
      [E.inicio],
    );
    const nombresEa1 = new Set(ea1.map((f) => f.responsable));
    verificar(selectores === 0, `la pantalla tiene ${selectores} selectores (se esperaba ninguno)`);
    verificar(responsable.includes(NOMBRES.operador_prueba), `responsable mostrado: ${responsable}`);
    verificar(estancia?.operador_entrada === NOMBRES.operador_prueba && estancia?.operador_salida === NOMBRES.operador_prueba, `historial: entrada ${estancia?.operador_entrada}, salida ${estancia?.operador_salida}`);
    verificar(filaHistorial.includes(NOMBRES.operador_prueba), 'el historial en pantalla no muestra a la persona de la sesión');
    verificar(conOperador.status === 422 && dentro.body.esta_dentro === false, `entrada con operador_id: ${conOperador.status} (se esperaba 422)`);
    verificar(ea1.length > 0 && [...nombresEa1].every((n) => /Marta Úsuga|Diego Arango/.test(n)), `responsables de la EA1: ${[...nombresEa1].join(', ') || 'ninguno'}`);
    c.anotar(`La pantalla no tiene selector de operador y muestra «Responsable de las operaciones: ${NOMBRES.operador_prueba}». Entrada y salida de ${placa} a nombre de ${NOMBRES.operador_prueba} (pantalla e historial). La entrada con operador_id responde 422. Los ${ea1.reduce((s, f) => s + f.movimientos, 0)} movimientos de la EA1 conservan como responsables a: ${[...nombresEa1].join(', ')}.`);
  },

  'US-16': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const o = cuenta('operador_prueba');
    precondicion(!!E.placaOperador, 'operador_prueba no tiene movimientos (US-20 no se completó)');
    precondicion((await adminsActivos()) >= 2, 'no hay dos administradores activos');
    const tokenOperador = await entrar(o, 'sesión de operador_prueba (su token se conserva para US-17)');
    E.tokenOperadorAnterior = tokenOperador.token ?? '';
    const { contexto: ctxO, page: pO } = await conSesionUI(browser, o.usuario, o.contrasena);
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByLabel('Buscar por nombre o usuario').fill(o.usuario);
    await page.getByRole('button', { name: 'Buscar', exact: true }).click();
    await page.getByRole('button', { name: `Desactivar la cuenta de ${o.nombre}` }).click();
    const dialogo = page.getByRole('alertdialog');
    const confirmacion = (await dialogo.locator('p').innerText()).trim();
    await captura(page, 'confirmacion');
    await dialogo.getByRole('button', { name: 'Sí, desactivar' }).click();
    await page.getByText(`Cuenta de ${o.nombre} desactivada: ya no puede ingresar.`).waitFor();
    await captura(page);
    await menu(pO).getByRole('link', { name: 'Celdas' }).click();
    await esperarIngreso(pO);
    await captura(pO, 'sesion_abierta');
    await ctxO.close();
    const siguiente = await tokenOperador.get('/celdas', 'siguiente solicitud de la sesión abierta del operador');
    const login = await (await anonimo()).post('/auth/login', { usuario: o.usuario, contrasena: o.contrasena }, 'ingresar con la contraseña correcta');
    const { contexto: ctxL, page: pL } = await nuevaPagina(browser);
    await pL.goto('/ingresar');
    await ingresarUI(pL, o.usuario, o.contrasena);
    const alertaLogin = (await pL.getByRole('alert').innerText()).trim();
    await captura(pL, 'ingreso_rechazado');
    await ctxL.close();
    const admin = await entrar(a);
    const h = await admin.get(`/reportes/historial?placa=${E.placaOperador}`, 'movimientos de operador_prueba después de desactivarla');
    const det = await admin.get(`/cuentas/${o.id}`, 'auditoría de la cuenta');
    const ultima = det.body.auditoria?.at(-1) ?? det.body.auditoria?.[0];
    await page.getByRole('button', { name: `Ver detalle de ${o.nombre}` }).click();
    await page.getByRole('heading', { name: `Detalle de ${o.nombre}` }).waitFor();
    const filaAud = await page.getByRole('row').filter({ hasText: 'Desactivó la cuenta' }).first().waitFor().then(() => 1, () => 0);
    await captura(page, 'auditoria');
    await contexto.close();
    const esperado = `¿Desactivar la cuenta de ${o.nombre} (${o.usuario})? No podrá ingresar y su sesión abierta se cerrará. Sus movimientos seguirán a su nombre.`;
    verificar(confirmacion === esperado, `confirmación: «${confirmacion}»`);
    verificar(siguiente.status === 401, `la sesión abierta recibió ${siguiente.status} (se esperaba 401)`);
    verificar(login.status === 403 && login.body.detail === DESACTIVADA, `ingreso: ${login.status} ${JSON.stringify(login.body)}`);
    verificar(alertaLogin === DESACTIVADA, `pantalla de ingreso: «${alertaLogin}»`);
    verificar(h.body.items?.[0]?.operador_entrada === o.nombre, 'sus movimientos ya no están a su nombre');
    const desactivar = det.body.auditoria?.filter((e: any) => e.accion === 'DESACTIVAR') ?? [];
    verificar(desactivar.length > 0 && String(desactivar.at(-1).actor).includes(a.usuario) && filaAud > 0, `auditoría: ${JSON.stringify(ultima)}`);
    c.anotar(`Confirmación: «${confirmacion}». La sesión abierta recibe 401 en la siguiente solicitud y vuelve a «Ingresar». El ingreso con la contraseña correcta responde 403 «${DESACTIVADA}» (también en pantalla). Sus movimientos siguen a nombre de ${o.nombre}. Auditoría: DESACTIVAR por ${desactivar.at(-1).actor} («Desactivó la cuenta» en pantalla).`);
  },

  'US-17': async (c, browser) => {
    const a = cuenta('admin_prueba');
    const o = cuenta('operador_prueba');
    const estado = await consulta('estado de operador_prueba antes de reactivar', 'SELECT activa FROM cuenta_usuario WHERE id = $1', [o.id]);
    precondicion(estado[0]?.activa === false && !!E.tokenOperadorAnterior, 'operador_prueba no quedó desactivada en US-16 o falta su token anterior');
    const { contexto, page } = await conSesionUI(browser, a.usuario, a.contrasena);
    await menu(page).getByRole('link', { name: 'Cuentas de usuario' }).click();
    await page.getByLabel('Buscar por nombre o usuario').fill(o.usuario);
    await page.getByRole('button', { name: 'Buscar', exact: true }).click();
    await page.getByRole('button', { name: `Reactivar la cuenta de ${o.nombre}` }).click();
    await page.getByText(`Cuenta de ${o.nombre} reactivada: puede volver a ingresar.`).waitFor();
    await captura(page);
    await contexto.close();
    const login = await (await anonimo()).post('/auth/login', { usuario: o.usuario, contrasena: o.contrasena }, 'ingresar después de reactivar');
    const anterior = await conToken(E.tokenOperadorAnterior, 'token anterior de operador_prueba');
    const reuso = await anterior.get('/celdas', 'reutilizar el token anterior');
    const { contexto: ctxO, page: pO } = await conSesionUI(browser, o.usuario, o.contrasena);
    await captura(pO, 'ingreso');
    await ctxO.close();
    const admin = await entrar(a);
    const det = await admin.get(`/cuentas/${o.id}`, 'auditoría de la cuenta');
    const reactivar = det.body.auditoria?.filter((e: any) => e.accion === 'REACTIVAR') ?? [];
    verificar(login.status === 200, `ingreso: ${login.status}`);
    verificar(reuso.status === 401, `token anterior: ${reuso.status} (se esperaba 401)`);
    verificar(reactivar.length > 0 && String(reactivar.at(-1).actor).includes(a.usuario), 'la auditoría no registra REACTIVAR');
    c.anotar(`La cuenta vuelve a ingresar (200, también en pantalla). El token anterior sigue sin validez (401). Auditoría: REACTIVAR por ${reactivar.at(-1).actor}.`);
  },

  'US-18': async (c) => {
    const a = cuenta('admin_prueba');
    const api = await entrar(a, 'admin_prueba (con sesión)');
    // Precondición «dos administradores activos»: se desactivan los demás (semillas y admin.nuevo).
    for (const otro of [E.semilla, E.cuentas['admin.nuevo']].filter(Boolean)) {
      const r = await api.post(`/cuentas/${otro.id}/desactivar`, undefined, `preparación: dejar solo a admin_prueba y admin_dos activos (desactivar ${otro.usuario})`);
      precondicion(r.status === 200 || (r.status === 409 && /ya está desactivada/.test(r.body.detail)), `no se pudo desactivar a ${otro.usuario}: ${r.status}`);
    }
    const antes = await adminsActivos();
    precondicion(antes === 2, `hay ${antes} administradores activos (se necesitan dos)`);
    const propia = await api.post(`/cuentas/${a.id}/desactivar`, undefined, 'admin_prueba intenta desactivar su propia cuenta');
    const otra = await api.post(`/cuentas/${cuenta('admin_dos').id}/desactivar`, undefined, 'admin_prueba desactiva a admin_dos');
    const despues = await adminsActivos();
    verificar(propia.status === 409 && propia.body.detail === 'No puedes desactivar tu propia cuenta.', `propia cuenta: ${propia.status} ${JSON.stringify(propia.body)}`);
    verificar(otra.status === 200 && otra.body.activa === false, `admin_dos: ${otra.status}`);
    verificar(despues === 1, `administradores activos: ${despues}`);
    c.anotar(`Con dos administradores activos: la propia cuenta responde 409 «No puedes desactivar tu propia cuenta.»; admin_dos se desactiva (200). Queda ${despues} administrador activo.`);
  },

  'US-19': async (c) => {
    const a = cuenta('admin_prueba');
    const b = cuenta('admin_dos');
    const intentos: string[] = [];
    let cruce = false;
    for (let i = 1; i <= 5 && !cruce; i++) {
      // Precondición: solo dos administradores activos, cada uno con sesión.
      const sobreviviente = (await consulta('quién sigue activo', 'SELECT nombre_usuario FROM cuenta_usuario WHERE rol = $1 AND activa', ['ADMINISTRADOR'])).map((f) => f.nombre_usuario);
      const activo = sobreviviente.includes(a.usuario) ? a : b;
      const inactivo = activo === a ? b : a;
      const reac = await (await entrar(activo)).post(`/cuentas/${inactivo.id}/reactivar`, undefined, `preparación (intento ${i}): reactivar a ${inactivo.usuario}`);
      precondicion(reac.status === 200 || reac.status === 409, `no se pudo reactivar a ${inactivo.usuario}`);
      precondicion((await adminsActivos()) === 2, 'no quedaron exactamente dos administradores activos');
      const [sa, sb] = [await entrar(a, `sesión de ${a.usuario}`), await entrar(b, `sesión de ${b.usuario}`)];
      const [ra, rb] = await Promise.all([
        sa.post(`/cuentas/${b.id}/desactivar`, undefined, `intento ${i}: ${a.usuario} desactiva a ${b.usuario}`),
        sb.post(`/cuentas/${a.id}/desactivar`, undefined, `intento ${i}: ${b.usuario} desactiva a ${a.usuario}`),
      ]);
      const activos = await adminsActivos();
      intentos.push(`intento ${i}: ${ra.status} y ${rb.status}, quedan ${activos}`);
      const codigos = [ra.status, rb.status].sort();
      verificar(activos === 1, `quedaron ${activos} administradores activos`);
      if (codigos[0] === 200 && codigos[1] === 409) {
        const conflicto = ra.status === 409 ? ra : rb;
        verificar(conflicto.body.detail === 'No se puede desactivar al último administrador activo.', `mensaje del 409: ${JSON.stringify(conflicto.body)}`);
        cruce = true;
      }
    }
    c.anotar(`API, desactivación cruzada al mismo tiempo: ${intentos.join('; ')}.`);
    c.anotar(cruce
      ? 'Una operación se confirma (200) y la otra responde 409 «No se puede desactivar al último administrador activo.». Queda exactamente un administrador activo.'
      : 'En ningún intento las dos solicitudes se cruzaron dentro de la base (la segunda llegó con su sesión ya cerrada: 401); siempre quedó un administrador. El cruce lo fuerza la prueba automatizada.');
    // Restaurar: el otro administrador vuelve a estar activo para los casos siguientes (CE-13).
    const activo = (await consulta('administrador que quedó activo', 'SELECT nombre_usuario FROM cuenta_usuario WHERE rol = $1 AND activa', ['ADMINISTRADOR']))[0].nombre_usuario;
    const sobrevive = activo === a.usuario ? a : b;
    const otro = sobrevive === a ? b : a;
    await (await entrar(sobrevive)).post(`/cuentas/${otro.id}/reactivar`, undefined, `restaurar: reactivar a ${otro.usuario} para los casos siguientes`);
    (c as any).sinCruce = !cruce;
  },
};

export { adminsActivos, buscarYEsperar, conSesionUI, esperarIngreso, MENU_OPERADOR, textoVisible };
export type { Api };
