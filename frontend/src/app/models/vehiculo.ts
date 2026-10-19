export const TIPOS_VEHICULO = ['MOTO', 'AUTOMOVIL', 'CAMIONETA'] as const;
export type TipoVehiculo = (typeof TIPOS_VEHICULO)[number];
export interface VehiculoCrear {
  placa: string;
  color: string;
  modelo: number;
  marca: string;
  tipo: TipoVehiculo;
}
export type VehiculoActualizar = Partial<VehiculoCrear>;
export interface Vehiculo extends VehiculoCrear {
  id: number;
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
