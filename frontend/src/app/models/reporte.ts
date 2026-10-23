export interface CeldasPorTipo {
  tipo: 'CARRO' | 'MOTO';
  total: number;
  ocupadas: number;
  libres: number;
}
export interface VehiculoDentro {
  estancia_id: number;
  placa: string;
  tipo_vehiculo: string;
  celda: string;
  entrada: string;
  operador_entrada: string;
  /** Tiempo dentro hasta el momento del reporte, ej. '2 h 15 min'. */
  tiempo: string;
}
export interface Ocupacion {
  generado: string;
  celdas: CeldasPorTipo[];
  dentro: VehiculoDentro[];
}
export interface EstanciaHistorial {
  id: number;
  placa: string;
  tipo_vehiculo: string;
  celda: string;
  entrada: string;
  salida: string | null;
  abierta: boolean;
  duracion_segundos: number | null;
  permanencia: string | null;
  operador_entrada: string;
  operador_salida: string | null;
  novedades: number;
  correcciones: number;
}
export interface HistorialPagina {
  items: EstanciaHistorial[];
  total: number;
  offset: number;
  limit: number;
}
/** Filtros del historial: placa y días de Bogotá (AAAA-MM-DD), todos opcionales. */
export interface FiltrosHistorial {
  placa?: string;
  desde?: string;
  hasta?: string;
}
