// Iteración 1: la celda es de moto o de carro (automóviles y camionetas usan CARRO).
export const TIPOS_CELDA = ['MOTO', 'CARRO'] as const;
export type TipoCelda = (typeof TIPOS_CELDA)[number];
// Iteración 2: estado calculado por el servidor (nunca se guarda).
export const ESTADOS_CELDA = ['LIBRE', 'OCUPADA', 'INHABILITADA'] as const;
export type EstadoCelda = (typeof ESTADOS_CELDA)[number];

export interface CeldaCrear {
  codigo: string;
  tipo: TipoCelda;
  ubicacion?: string | null;
}
export type CeldaActualizar = Partial<CeldaCrear>;
export interface Celda {
  id: number;
  codigo: string;
  /** string: podrían existir celdas antiguas de otro tipo (la base no las borra). */
  tipo: string;
  /** Momento en que quedó libre por última vez; null si nunca se ha usado. */
  disponible_desde?: string | null;
  ubicacion?: string | null;
  habilitada?: boolean;
}
/** Celda en la gestión de celdas (Iteración 2). */
export interface CeldaGestion extends Celda {
  estado: EstadoCelda;
  /** Placa del vehículo si está ocupada. */
  placa: string | null;
  /** D8: con historial, su código y su tipo ya no se pueden cambiar. */
  tiene_historial: boolean;
}
export interface EventoAuditoriaCelda {
  fecha: string;
  accion: string;
  detalle: string | null;
  actor: string | null;
}
export interface CeldaDetalle extends CeldaGestion {
  auditoria: EventoAuditoriaCelda[];
}
export interface CeldasPagina {
  items: CeldaGestion[];
  total: number;
  offset: number;
  limit: number;
}
export interface FiltrosCeldas {
  buscar?: string;
  tipo?: TipoCelda | '';
  estado?: EstadoCelda | '';
}
