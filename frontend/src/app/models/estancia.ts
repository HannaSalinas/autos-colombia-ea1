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
