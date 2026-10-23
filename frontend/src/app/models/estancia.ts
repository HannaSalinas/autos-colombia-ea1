import { Celda } from './celda';
import { Vehiculo } from './vehiculo';

/** Iteración 1: el operador no elige la celda; la asigna el sistema. */
export interface EntradaCrear {
  placa: string;
  operador_id: number;
}
export interface SalidaCrear {
  placa: string;
  operador_id: number;
}
export interface Estancia {
  id: number;
  vehiculo_id: number;
  celda_id: number;
  entrada: string;
  salida: string | null;
  operador_entrada_id: number;
  operador_salida_id: number | null;
}
/** Respuesta de entrada y salida. */
export interface Movimiento extends Estancia {
  placa: string;
  celda: Celda;
  /** Solo al salir. */
  duracion_segundos: number | null;
  /** Texto listo para mostrar, ej. '2 h 15 min'. Solo al salir. */
  permanencia: string | null;
}
export interface EstadoVehiculo {
  vehiculo: Vehiculo;
  esta_dentro: boolean;
  estancia: (Estancia & { celda: Celda }) | null;
}

// --- Corrección de celda y novedades (Fase 3) ---
export const TIPOS_NOVEDAD = [
  { valor: 'RAYON', etiqueta: 'Rayón' },
  { valor: 'GOLPE', etiqueta: 'Golpe' },
  { valor: 'OBJETO_OLVIDADO', etiqueta: 'Objeto olvidado' },
  { valor: 'OTRO', etiqueta: 'Otro' },
] as const;
export type TipoNovedad = (typeof TIPOS_NOVEDAD)[number]['valor'];
export const MOTIVO_MAXIMO = 200;
export const DESCRIPCION_MAXIMA = 500;

export interface CorreccionCrear {
  celda_id: number;
  operador_id: number;
  motivo: string;
}
export interface Correccion {
  id: number;
  estancia_id: number;
  celda_anterior: Celda;
  celda_nueva: Celda;
  operador_id: number;
  fecha: string;
  motivo: string;
}
export interface NovedadCrear {
  tipo: TipoNovedad;
  descripcion: string;
  operador_id: number;
}
export interface Novedad {
  id: number;
  estancia_id: number;
  operador_id: number;
  fecha: string;
  tipo: TipoNovedad;
  descripcion: string;
}
