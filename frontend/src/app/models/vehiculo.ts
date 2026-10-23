export const TIPOS_VEHICULO = ['MOTO', 'AUTOMOVIL', 'CAMIONETA'] as const;
export type TipoVehiculo = (typeof TIPOS_VEHICULO)[number];
export interface VehiculoCrear {
  placa: string;
  color: string;
  modelo: number;
  marca: string;
  tipo: TipoVehiculo;
  cliente_id: number;
}
export type VehiculoActualizar = Partial<VehiculoCrear>;
export interface Vehiculo extends VehiculoCrear {
  id: number;
  cliente_nombre: string;
  mensualidad_vigente: boolean;
  /** Fecha YYYY-MM-DD: vence (si está vigente) o venció. null si nunca ha pagado. */
  mensualidad_hasta: string | null;
}
export interface VehiculosPagina {
  items: Vehiculo[];
  total: number;
  offset: number;
  limit: number;
}
export interface ErrorValidacion {
  loc: (string | number)[];
  msg: string;
  type: string;
}
export interface ErrorApi {
  detail?: string | ErrorValidacion[];
}
