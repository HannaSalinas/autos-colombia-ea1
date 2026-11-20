/**
 * Datos compartidos por la preparación, el recorrido y el reporte de los recorridos de navegadores:
 * - rnf20 (EA2, caso NF-02 del plan PP-02): las 10 pantallas de la Iteración 2.
 * - rnf26 (EA3, caso NF-02 del plan PP-03): las 10 pantallas de la Iteración 3.
 * Se elige con la variable RECORRIDO (por defecto rnf20, como en la EA2).
 */
import { mkdirSync } from 'node:fs';

export const RECORRIDO: 'rnf20' | 'rnf26' = process.env.RECORRIDO === 'rnf26' ? 'rnf26' : 'rnf20';
/** Carpeta montada desde el equipo: docs/evidencias/rnf20/ o docs/evidencias/rnf26/ */
export const SALIDA = process.env.SALIDA ?? '/e2e/salida';
/** Resultados intermedios por navegador (dentro del contenedor; no se versionan). */
export const RESULTADOS = `/tmp/${RECORRIDO}-resultados`;
/** Prefijo de las capturas: NF-02_… (EA2) o RNF-26_… (EA3). */
export const PREFIJO = RECORRIDO === 'rnf26' ? 'RNF-26' : 'NF-02';

/** Iteración 3 (RNF-26): ninguna pantalla modifica datos; los registros se detienen en el resumen o
 *  en la confirmación, que se cancelan. */
const PANTALLAS_RNF26 = [
  ['01', 'tarifas_administrador', 'Tarifas del administrador (vigentes e historial)'],
  ['02', 'confirmar_tarifa', 'Confirmación de una tarifa nueva (cancelada)'],
  ['03', 'clientes', 'Clientes: búsqueda con vehículos y detalle'],
  ['04', 'registrar_cliente_errores', 'Registrar cliente con datos inválidos y sus errores'],
  ['05', 'pagos_estado', 'Pagos: estado de la mensualidad de STU852'],
  ['06', 'pagos_resumen', 'Pagos: resumen antes de confirmar (se vuelve sin registrar)'],
  ['07', 'comprobante', 'Detalle del pago con su comprobante'],
  ['08', 'confirmar_anulacion', 'Anulación: motivo y confirmación (cancelada)'],
  ['09', 'recaudo', 'Resumen de recaudo'],
  ['10', 'operador_pagos', 'Operador: menú sin Recaudo y detalle del pago sin Anular'],
] as const;

/** Lista única de las 10 pantallas de la EA2 (la misma del README y del plan de pruebas PP-02). */
const PANTALLAS_RNF20 = [
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

export const PANTALLAS: readonly (readonly [string, string, string])[] =
  RECORRIDO === 'rnf26' ? PANTALLAS_RNF26 : PANTALLAS_RNF20;

/** Textos del reporte de cada recorrido. */
export const REPORTE =
  RECORRIDO === 'rnf26'
    ? {
        titulo: '# Evidencia de RNF-26: compatibilidad de navegadores de la Iteración 3 (caso NF-02 del plan PP-03)',
        comando: 'docker compose --profile e2e run --rm --build e2e-rnf26',
        datos:
          'no modifica datos: el pago llega hasta el resumen, la tarifa y la anulación hasta su confirmación, y las tres se cancelan; el comprobante es el del pago de ejemplo de las semillas.',
        carpeta: 'docs/evidencias/rnf26',
      }
    : {
        titulo: '# Evidencia de RNF-20: compatibilidad de navegadores (caso NF-02)',
        comando: 'docker compose --profile e2e run --rm --build e2e',
        datos: 'no modifica datos: las confirmaciones se cancelan y la cuenta "abc" no llega a enviarse.',
        carpeta: 'docs/evidencias/rnf20',
      };

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
  return `${PREFIJO}_${navegador}_${numero}_${clave}.png`;
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
