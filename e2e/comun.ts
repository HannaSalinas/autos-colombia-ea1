/** Datos compartidos por la preparación, el recorrido y el reporte de NF-02 (RNF-20). */
import { mkdirSync } from 'node:fs';

/** Carpeta montada desde el equipo: docs/evidencias/rnf20/ */
export const SALIDA = process.env.SALIDA ?? '/e2e/salida';
/** Resultados intermedios por navegador (dentro del contenedor; no se versionan). */
export const RESULTADOS = '/tmp/nf02-resultados';

/** Lista única de las 10 pantallas (la misma del README y del plan de pruebas). */
export const PANTALLAS = [
  ['01', 'ingreso', 'Ingreso'],
  ['02', 'error_credenciales', 'Error de credenciales'],
  ['03', 'inicio_administrador', 'Inicio del administrador'],
  ['04', 'cuentas', 'Cuentas de usuario'],
  ['05', 'crear_cuenta_abc', 'Crear cuenta con el usuario "abc" y su error'],
  ['06', 'confirmar_desactivar', 'Confirmación de desactivar a diego.arango (cancelada)'],
  ['07', 'celdas_administrador', 'Celdas del administrador'],
  ['08', 'confirmar_inhabilitar', 'Confirmación de inhabilitar una celda (cancelada)'],
  ['09', 'inicio_operador', 'Inicio del operador'],
  ['10', 'celdas_operador', 'Celdas del operador'],
] as const;

export const NAVEGADORES: Record<string, { nombre: string; motor: string; aclaracion: string }> = {
  chrome: {
    nombre: 'Google Chrome (estable, Linux)',
    motor: 'Chromium (Blink)',
    aclaracion: 'Navegador oficial de Google para Linux, descargado al construir la imagen.',
  },
  edge: {
    nombre: 'Microsoft Edge (estable, Linux)',
    motor: 'Chromium (Blink)',
    aclaracion:
      'Navegador oficial de Microsoft para Linux, no la versión de Windows. Comparte motor con Chrome.',
  },
  firefox: {
    nombre: 'Firefox de Playwright',
    motor: 'Gecko',
    aclaracion:
      'Firefox que distribuye Playwright 1.64.1: motor Gecko de Firefox estable con parches para ' +
      'automatizarlo. No es el instalador oficial de Mozilla y puede ir unas semanas detrás de la última versión.',
  },
};

export function archivo(navegador: string, numero: string, clave: string): string {
  return `NF-02_${navegador}_${numero}_${clave}.png`;
}

export interface ResultadoPantalla {
  numero: string;
  clave: string;
  estado: 'Sí' | 'No' | 'No ejecutada';
  detalle: string;
}

export interface ResultadoNavegador {
  navegador: string;
  version: string;
  /** Identificación que el navegador envía a los sitios (user agent). La de Edge contiene "Edg/". */
  agente: string;
  pantallas: ResultadoPantalla[];
}

/** Valores de .env que nunca deben aparecer en el código, el reporte ni los registros. */
export function secretos(): string[] {
  return ['ADMIN_CONTRASENA', 'MARTA_CONTRASENA']
    .map((nombre) => process.env[nombre] ?? '')
    .filter((valor) => valor.length > 0);
}

/** Reemplaza cualquier secreto por *** (para mensajes de error que vayan al reporte). */
export function sinSecretos(texto: string): string {
  return secretos().reduce((t, s) => t.split(s).join('***'), texto);
}

export function variable(nombre: string): string {
  const valor = process.env[nombre];
  if (!valor) throw new Error(`Falta la variable ${nombre} (se toma de .env a través de docker-compose).`);
  return valor;
}

export function asegurarCarpetas(): void {
  mkdirSync(SALIDA, { recursive: true });
  mkdirSync(RESULTADOS, { recursive: true });
}
