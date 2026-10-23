// Iteración 1: la celda es de moto o de carro (automóviles y camionetas usan CARRO).
export const TIPOS_CELDA = ['MOTO', 'CARRO'] as const;
export type TipoCelda = (typeof TIPOS_CELDA)[number];
export interface CeldaCrear {
  codigo: string;
  tipo: TipoCelda;
}
export type CeldaActualizar = Partial<CeldaCrear>;
export interface Celda {
  id: number;
  codigo: string;
  /** string: podrían existir celdas antiguas de otro tipo (la base no las borra). */
  tipo: string;
  /** Momento en que quedó libre por última vez; null si nunca se ha usado. */
  disponible_desde?: string | null;
}
export interface CeldasPagina {
  items: Celda[];
  total: number;
  offset: number;
  limit: number;
}
