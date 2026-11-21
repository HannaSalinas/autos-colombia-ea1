/**
 * Datos de prueba del plan PP-03 (hoja Plan) y su preparación. Las cuentas, los clientes, los vehículos
 * y los pagos se crean por la API. Solo los periodos de V-VIG, V-VENC y V-FUT se insertan por SQL, como
 * periodos sin pago iguales a los de las semillas: la API no permite crear un periodo que ya venció o
 * que empezó antes de hoy (un pago empieza hoy o el día siguiente al último fin).
 */
import { anonimo, Api, consulta, contrasenaAleatoria, precondicion, sesion, variable } from '../plan/contexto';

export interface Cuenta {
  usuario: string;
  nombre: string;
  rol: 'ADMINISTRADOR' | 'OPERADOR';
  /** Solo en memoria. */
  contrasena: string;
}

/** Vehículos del plan: rol en el plan → placa, tipo y para qué casos se usa. */
export const VEHICULOS = {
  'V-SIN': { placa: 'PPS301', tipo: 'AUTOMOVIL', uso: 'ME-02 y PA-10 (sin periodos)' },
  'V-VENC': { placa: 'PPV302', tipo: 'AUTOMOVIL', uso: 'ME-02 y PA-01 (periodo vencido hace 5 días)' },
  'V-VIG': { placa: 'PPG303', tipo: 'CAMIONETA', uso: 'ME-01 y PA-02 (vigente, vence en 10 días)' },
  'V-FUT': { placa: 'PPF304', tipo: 'AUTOMOVIL', uso: 'ME-03 (periodo vigente y otro pagado por adelantado)' },
  'PA04-1': { placa: 'PPM305', tipo: 'AUTOMOVIL', uso: 'PA-04 (1 mes)' },
  'PA04-6': { placa: 'PPN31A', tipo: 'MOTO', uso: 'PA-04 (6 meses)' },
  PA05: { placa: 'PPR307', tipo: 'AUTOMOVIL', uso: 'PA-05' },
  PA06: { placa: 'PPT308', tipo: 'AUTOMOVIL', uso: 'PA-06' },
  PA07: { placa: 'PPC309', tipo: 'AUTOMOVIL', uso: 'PA-07' },
  PA08: { placa: 'PPD310', tipo: 'AUTOMOVIL', uso: 'PA-08, AN-03 y AN-05' },
  PA09: { placa: 'PPE311', tipo: 'CAMIONETA', uso: 'PA-09' },
  TA05: { placa: 'PPH312', tipo: 'AUTOMOVIL', uso: 'TA-05 (pago nuevo)' },
  AN01: { placa: 'PPK313', tipo: 'AUTOMOVIL', uso: 'AN-01, ME-04 y AN-04' },
  'AN02-10': { placa: 'PPL314', tipo: 'AUTOMOVIL', uso: 'AN-02 (motivo de 10)' },
  'AN02-200': { placa: 'PPL315', tipo: 'AUTOMOVIL', uso: 'AN-02 (motivo de 200)' },
} as const;
export type RolVehiculo = keyof typeof VEHICULOS;
export const placa = (rol: RolVehiculo): string => VEHICULOS[rol].placa;

export const TARIFAS_INICIALES = { MOTO: 60000, AUTOMOVIL: 120000, CAMIONETA: 140000 } as const;
export const DOC_CL01 = '1020304050';
export const DOC_CL04 = '1098765432';
export const PLACA_INEXISTENTE = 'ZZZ999';

export const E = {
  semilla: {} as Cuenta,
  cuentas: {} as Record<string, Cuenta>,
  /** Cliente dueño de los vehículos del plan. */
  clienteId: 0,
  vehiculoId: {} as Record<string, number>,
  /** Pagos que unos casos dejan para otros. */
  pagos: {} as Record<string, { id: number; comprobante: string; fecha_inicio: string; fecha_fin: string; [campo: string]: any }>,
  hoy: '',
  inicio: new Date(),
};

export function cuenta(usuario: string): Cuenta {
  const c = E.cuentas[usuario];
  if (!c) throw new Error(`La cuenta ${usuario} no existe en el escenario`);
  return c;
}
export const entrar = (usuario: string, nota?: string) => sesion(usuario, cuenta(usuario).contrasena, nota);

// ------------------------------------------------------------------ fechas (hora de Bogotá)
/** Hoy en Bogotá, 'AAAA-MM-DD'. */
export function hoyBogota(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
}
const aFecha = (iso: string) => {
  const [a, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(a, m - 1, d));
};
const aIso = (f: Date) => f.toISOString().slice(0, 10);
export const sumarDias = (iso: string, dias: number) => aIso(new Date(aFecha(iso).getTime() + dias * 86_400_000));
const diasDelMes = (a: number, m0: number) => new Date(Date.UTC(a, m0 + 1, 0)).getUTCDate();

/**
 * Regla del documento (D13), escrita aquí aparte del backend para comparar: el fin es el día anterior a
 * la misma fecha N meses después; si esa fecha no existe, el último día del mes destino.
 */
export function finDePeriodo(inicio: string, meses: number): string {
  const f = aFecha(inicio);
  const total = f.getUTCMonth() + meses;
  const a = f.getUTCFullYear() + Math.floor(total / 12);
  const m0 = total % 12;
  if (f.getUTCDate() > diasDelMes(a, m0)) return aIso(new Date(Date.UTC(a, m0, diasDelMes(a, m0))));
  return sumarDias(aIso(new Date(Date.UTC(a, m0, f.getUTCDate()))), -1);
}
/** Tope del pago adelantado: la misma fecha 12 meses después (último día del mes si no existe). */
export function topeDeAdelanto(hoy: string): string {
  const f = aFecha(hoy);
  const a = f.getUTCFullYear() + 1;
  const m0 = f.getUTCMonth();
  return aIso(new Date(Date.UTC(a, m0, Math.min(f.getUTCDate(), diasDelMes(a, m0)))));
}
/** '2026-11-20' → '20/11/2026' (como en la pantalla y en los mensajes). */
export const fechaCorta = (iso: string) => iso.split('-').reverse().join('/');
/** 120000 → '$ 120.000'. */
export const pesos = (n: number) => `$ ${String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`;

// ------------------------------------------------------------------ ayudas por la API
export async function crearCuenta(api: Api, usuario: string, nombre: string, rol: Cuenta['rol']): Promise<Cuenta> {
  const c: Cuenta = { usuario, nombre, rol, contrasena: contrasenaAleatoria() };
  const r = await api.post('/cuentas', { nombre, nombre_usuario: usuario, contrasena: c.contrasena, rol }, `crear ${usuario}`);
  if (r.status !== 201) throw new Error(`No se pudo crear ${usuario}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
  E.cuentas[usuario] = c;
  return c;
}

export async function tarifaVigente(api: Api, tipo: string): Promise<number> {
  const r = await api.get('/tarifas', `tarifa vigente de ${tipo}`);
  return r.body.find((t: any) => t.tipo_vehiculo === tipo)?.tarifa?.valor;
}

export async function fijarTarifa(api: Api, tipo: string, valor: number, nota?: string): Promise<any> {
  const r = await api.post('/tarifas', { tipo_vehiculo: tipo, valor }, nota ?? `fijar ${tipo} en ${pesos(valor)}`);
  if (r.status !== 201) throw new Error(`No se pudo fijar ${tipo} en ${valor}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
  return r.body;
}

/** Cotiza y registra un pago con el monto del resumen. Falla si no responde 201. */
export async function pagar(api: Api, placaPago: string, meses: number, metodo = 'EFECTIVO', referencia: string | null = null, nota?: string): Promise<any> {
  const cot = await api.get(`/pagos/cotizacion?placa=${placaPago}&meses=${meses}`, `resumen de ${placaPago}, ${meses} mes(es)`);
  if (cot.status !== 200) throw new Error(`Resumen de ${placaPago}: HTTP ${cot.status} ${JSON.stringify(cot.body)}`);
  const r = await api.post('/pagos', { placa: placaPago, meses, metodo, referencia, monto_confirmado: cot.body.monto },
    nota ?? `registrar el pago de ${placaPago}`);
  if (r.status !== 201) throw new Error(`Pago de ${placaPago}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
  return r.body;
}

export async function contar(nota: string, sql: string, parametros: unknown[] = []): Promise<number> {
  const filas = await consulta(nota, sql, parametros);
  return Number(Object.values(filas[0])[0]);
}

// ------------------------------------------------------------------ preparación
export async function preparar(): Promise<void> {
  E.hoy = hoyBogota();
  E.semilla = { usuario: variable('ADMIN_USUARIO'), nombre: '', rol: 'ADMINISTRADOR', contrasena: variable('ADMIN_CONTRASENA') };
  const admin = await sesion(E.semilla.usuario, E.semilla.contrasena, 'cuenta administradora de las semillas (contraseña de .env)');

  // Base recién creada: tarifas iniciales, sin las cuentas, documentos ni placas reservados.
  for (const [tipo, valor] of Object.entries(TARIFAS_INICIALES))
    precondicion((await tarifaVigente(admin, tipo)) === valor, `la tarifa inicial de ${tipo} no es ${valor}`);
  for (const usuario of ['admin_prueba', 'admin_dos', 'operador_prueba']) {
    const r = await admin.get(`/cuentas?buscar=${usuario}`, `comprobar que ${usuario} no existe`);
    precondicion(!r.body.items.some((c: any) => c.nombre_usuario === usuario), `${usuario} ya existía`);
  }
  for (const doc of [DOC_CL01, DOC_CL04]) {
    const n = await contar(`comprobar que CC ${doc} no existe`, 'SELECT count(*) FROM cliente WHERE documento = $1', [doc]);
    precondicion(n === 0, `el documento ${doc} ya existía`);
  }
  for (const p of [...Object.values(VEHICULOS).map((v) => v.placa), PLACA_INEXISTENTE]) {
    const r = await admin.get(`/pagos/estado/${p}`, `comprobar que ${p} no existe`);
    precondicion(r.status === 404, `la placa ${p} ya existía`);
  }

  const adminPrueba = await crearCuenta(admin, 'admin_prueba', 'Administradora de Prueba', 'ADMINISTRADOR');
  await crearCuenta(admin, 'admin_dos', 'Administrador Dos de Prueba', 'ADMINISTRADOR');
  await crearCuenta(admin, 'operador_prueba', 'Operador de Prueba', 'OPERADOR');
  const ap = await sesion(adminPrueba.usuario, adminPrueba.contrasena, 'iniciar sesión como admin_prueba');

  // Precondición de TA-01: un cambio previo de la tarifa de AUTOMOVIL (de ida y vuelta, para que los
  // montos de los demás casos sigan siendo los de las semillas).
  await fijarTarifa(ap, 'AUTOMOVIL', 125000, 'TA-01: cambio previo de AUTOMOVIL a $ 125.000');
  await fijarTarifa(ap, 'AUTOMOVIL', 120000, 'TA-01: AUTOMOVIL vuelve a $ 120.000');

  // Cliente dueño de los vehículos del plan.
  const cliente = await ap.post('/clientes', { tipo_documento: 'CC', documento: '7003000001', nombre: 'Cliente del Plan de Pruebas',
    telefono: '3007003001', correo: 'plan.pruebas@correo.com' }, 'cliente dueño de los vehículos del plan');
  if (cliente.status !== 201) throw new Error(`Cliente del plan: HTTP ${cliente.status} ${JSON.stringify(cliente.body)}`);
  E.clienteId = cliente.body.id;
  for (const [rol, v] of Object.entries(VEHICULOS)) {
    const r = await ap.post('/vehiculos', { placa: v.placa, tipo: v.tipo, marca: 'Plan PP-03', color: 'Gris', modelo: 2024,
      cliente_id: E.clienteId }, `vehículo ${rol}: ${v.placa} (${v.uso})`);
    if (r.status !== 201) throw new Error(`Vehículo ${v.placa}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
    E.vehiculoId[rol] = r.body.id;
  }

  // Periodos sin pago (como los de las semillas), con fechas relativas a hoy en Bogotá.
  const periodo = async (rol: RolVehiculo, inicio: string, fin: string, nota: string) =>
    consulta(nota, `INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin) VALUES ($1, $2, $3)
      RETURNING id, vehiculo_id, fecha_inicio::text, fecha_fin::text, pago_id`, [E.vehiculoId[rol], inicio, fin]);
  await periodo('V-VENC', sumarDias(E.hoy, -35), sumarDias(E.hoy, -5), `V-VENC (${placa('V-VENC')}): periodo vencido hace 5 días`);
  await periodo('V-VIG', sumarDias(E.hoy, -20), sumarDias(E.hoy, 10), `V-VIG (${placa('V-VIG')}): periodo vigente que vence en 10 días`);
  await periodo('V-FUT', sumarDias(E.hoy, -10), sumarDias(E.hoy, 20), `V-FUT (${placa('V-FUT')}): periodo vigente`);

  // V-FUT: el periodo pagado por adelantado se registra por la API (empieza al día siguiente del vigente).
  const op = await entrar('operador_prueba', 'iniciar sesión como operador_prueba');
  const fut = await pagar(op, placa('V-FUT'), 1, 'EFECTIVO', null, `V-FUT: pago por adelantado de ${placa('V-FUT')}`);
  E.pagos['V-FUT'] = fut;
  // Precondición de AN-01: un vehículo cuyo último periodo pagado es el vigente y que está fuera.
  E.pagos.AN01 = await pagar(op, placa('AN01'), 1, 'EFECTIVO', null, `AN-01: pago vigente de ${placa('AN01')}`);
  // Precondición de AN-02: dos pagos anulables (uno para el motivo de 10 y otro para el de 200).
  E.pagos['AN02-10'] = await pagar(op, placa('AN02-10'), 1, 'EFECTIVO', null, `AN-02: pago anulable de ${placa('AN02-10')}`);
  E.pagos['AN02-200'] = await pagar(op, placa('AN02-200'), 1, 'EFECTIVO', null, `AN-02: pago anulable de ${placa('AN02-200')}`);

  const salud = await (await anonimo()).get('/health', 'la API responde');
  precondicion(salud.status === 200, 'la API no responde');
}
