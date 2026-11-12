/**
 * Datos de prueba de la hoja Plan y su preparación, todo por la API (salvo la historia de la EA1, que
 * carga el orquestador con app.demo antes de empezar).
 */
import { anonimo, Api, consulta, contrasenaAleatoria, precondicion, sesion, variable } from './contexto';

export interface Cuenta {
  usuario: string;
  nombre: string;
  rol: 'ADMINISTRADOR' | 'OPERADOR';
  /** Solo en memoria. */
  contrasena: string;
  id?: number;
}

export const E = {
  semilla: {} as Cuenta,
  marta: {} as Cuenta,
  cuentas: {} as Record<string, Cuenta>,
  celdas: {} as Record<string, number>,
  /** Placas de carros con mensualidad vigente (según /vehiculos al preparar). */
  carros: [] as string[],
  /** Placa de la estancia que el operador registró en US-20 (sus movimientos, para US-16). */
  placaOperador: '',
  /** Placa de la estancia abierta en C82. */
  placaC82: '',
  /** Token de operador_prueba anterior a su desactivación (US-16 → US-17). Solo en memoria. */
  tokenOperadorAnterior: '',
  inicio: new Date(),
};

export const NOMBRES: Record<string, string> = {
  admin_prueba: 'Administradora de Prueba',
  admin_dos: 'Administrador Dos de Prueba',
  operador_prueba: 'Operador de Prueba',
};

export function cuenta(usuario: string): Cuenta {
  const c = E.cuentas[usuario];
  if (!c) throw new Error(`La cuenta ${usuario} no existe en el escenario`);
  return c;
}

export const entrar = (c: Cuenta, nota?: string) => sesion(c.usuario, c.contrasena, nota);

/** Crea una cuenta por la API y la guarda en el escenario (con su contraseña solo en memoria). */
export async function crearCuenta(api: Api, usuario: string, nombre: string, rol: Cuenta['rol'], nota?: string): Promise<Cuenta> {
  const c: Cuenta = { usuario, nombre, rol, contrasena: contrasenaAleatoria() };
  const r = await api.post('/cuentas', { nombre, nombre_usuario: usuario, contrasena: c.contrasena, rol }, nota ?? `crear ${usuario}`);
  if (r.status !== 201) throw new Error(`No se pudo crear ${usuario}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
  c.id = r.body.id;
  E.cuentas[usuario] = c;
  return c;
}

export async function idCuenta(usuario: string): Promise<number> {
  const filas = await consulta(`identificador de la cuenta ${usuario}`, 'SELECT id FROM cuenta_usuario WHERE lower(nombre_usuario) = lower($1)', [usuario]);
  return filas[0]?.id;
}

/**
 * Elige un carro con mensualidad vigente que esté fuera en este momento (lo consulta con la sesión
 * indicada). Un carro que ya salió se puede volver a usar.
 */
export async function tomarCarro(api: Api): Promise<string> {
  for (const placa of E.carros) {
    const r = await api.get(`/estancias/vehiculo/${placa}`, 'elegir un carro con mensualidad vigente que esté fuera');
    if (r.status === 200 && !r.body.esta_dentro) return placa;
  }
  throw new Error('No quedan carros con mensualidad vigente fuera del parqueadero');
}

export async function crearCelda(api: Api, codigo: string, ubicacion: string | null, nota?: string): Promise<number> {
  const r = await api.post('/celdas', { codigo, tipo: 'CARRO', ubicacion }, nota ?? `crear ${codigo}`);
  if (r.status !== 201) throw new Error(`No se pudo crear ${codigo}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
  E.celdas[codigo] = r.body.id;
  return r.body.id;
}

/** Registra una entrada real y la corrige de celda: así una estancia queda en la celda pedida. */
async function estanciaEn(api: Api, codigo: string, cerrar: boolean): Promise<string> {
  const placa = await tomarCarro(api);
  const entrada = await api.post('/estancias/entrada', { placa }, `entrada real de ${placa} (la asignación elige la celda)`);
  if (entrada.status !== 201) throw new Error(`Entrada de ${placa}: HTTP ${entrada.status}`);
  const correccion = await api.post(
    `/estancias/${entrada.body.estancia_id ?? entrada.body.id}/correccion-celda`,
    { celda_id: E.celdas[codigo], motivo: `Preparación del plan de pruebas: estancia en ${codigo}` },
    `corregir la celda a ${codigo}`,
  );
  if (correccion.status !== 201) throw new Error(`Corrección a ${codigo}: HTTP ${correccion.status} ${JSON.stringify(correccion.body)}`);
  if (cerrar) {
    const salida = await api.post('/estancias/salida', { placa }, `salida real de ${placa}: la estancia queda cerrada en ${codigo}`);
    if (salida.status !== 200) throw new Error(`Salida de ${placa}: HTTP ${salida.status}`);
  }
  return placa;
}

export async function preparar(): Promise<void> {
  E.semilla = { usuario: variable('ADMIN_USUARIO'), nombre: '', rol: 'ADMINISTRADOR', contrasena: variable('ADMIN_CONTRASENA') };
  E.marta = { usuario: 'marta.usuga', nombre: 'Marta Úsuga (Portería 1)', rol: 'OPERADOR', contrasena: variable('MARTA_CONTRASENA') };
  const admin = await sesion(E.semilla.usuario, E.semilla.contrasena, 'cuenta administradora de las semillas (contraseña de .env)');

  // Las cuentas reservadas no deben existir.
  for (const usuario of ['admin_prueba', 'admin_dos', 'operador_prueba', 'operador.nuevo', 'admin.nuevo', 'pedro.x']) {
    const r = await admin.get(`/cuentas?buscar=${encodeURIComponent(usuario)}`, `comprobar que ${usuario} no existe`);
    precondicion(!r.body.items.some((c: any) => c.nombre_usuario === usuario), `${usuario} ya existía`);
  }
  for (const codigo of ['C80', 'C81', 'C82', 'C83', 'C84', 'C86']) {
    const r = await admin.get(`/celdas?buscar=${codigo}`, `comprobar que ${codigo} no existe`);
    precondicion(!r.body.items.some((c: any) => c.codigo === codigo), `${codigo} ya existía`);
  }

  await crearCuenta(admin, 'admin_prueba', NOMBRES.admin_prueba, 'ADMINISTRADOR');
  await crearCuenta(admin, 'admin_dos', NOMBRES.admin_dos, 'ADMINISTRADOR');
  await crearCuenta(admin, 'operador_prueba', NOMBRES.operador_prueba, 'OPERADOR');
  E.semilla.id = await idCuenta(E.semilla.usuario);
  E.marta.id = await idCuenta('marta.usuga');
  const semilla = await admin.get('/auth/yo', 'nombre de la persona de la cuenta de las semillas');
  E.semilla.nombre = semilla.body.nombre;

  // Carros con mensualidad vigente.
  for (let offset = 0; ; offset += 100) {
    const r = await admin.get(`/vehiculos?offset=${offset}&limit=100`, 'listar vehículos para elegir carros con mensualidad vigente');
    E.carros.push(...r.body.items.filter((v: any) => v.tipo !== 'MOTO' && v.mensualidad_vigente).map((v: any) => v.placa));
    if (offset + 100 >= r.body.total) break;
  }

  // Las semillas tienen pocos carros con mensualidad vigente y la historia de demostración los deja
  // dentro; las mensualidades no tienen endpoint. Se registra la salida real de tres de esas estancias
  // abiertas para tener carros disponibles (los movimientos de la EA1 no cambian: es una salida nueva).
  let liberados = 0;
  for (const placa of E.carros) {
    if (liberados === 3) break;
    const r = await admin.get(`/estancias/vehiculo/${placa}`, 'carros con mensualidad vigente que están dentro');
    if (r.body.esta_dentro) {
      const salida = await admin.post('/estancias/salida', { placa }, `preparación: registrar la salida de ${placa} para tener carros disponibles`);
      precondicion(salida.status === 200, `no se pudo registrar la salida de ${placa}: ${salida.status}`);
      liberados++;
    }
  }

  await crearCelda(admin, 'C80', 'Plan de pruebas: sin historial');
  await crearCelda(admin, 'C81', 'Plan de pruebas: con historial');
  await crearCelda(admin, 'C82', 'Plan de pruebas: ocupada');
  await estanciaEn(admin, 'C81', true);
  E.placaC82 = await estanciaEn(admin, 'C82', false);

  const anon = await anonimo();
  const salud = await anon.get('/health', 'la API responde');
  precondicion(salud.status === 200, 'la API no responde');
}
