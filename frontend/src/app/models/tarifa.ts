/** Iteración 3 (D12, RF-32, RF-33): tarifa mensual por tipo de vehículo. Nunca se edita. */
export const TIPOS_VEHICULO_TARIFA = ['MOTO', 'AUTOMOVIL', 'CAMIONETA'] as const;
export type TipoVehiculoTarifa = (typeof TIPOS_VEHICULO_TARIFA)[number];

export interface Tarifa {
  id: number;
  tipo_vehiculo: TipoVehiculoTarifa;
  valor: number;
  vigente_desde: string;
  /** "Nombre (usuario)"; null = la definieron las semillas. */
  definida_por: string | null;
}
export interface TarifaVigente {
  tipo_vehiculo: TipoVehiculoTarifa;
  tarifa: Tarifa | null;
}
export interface TarifaCrear {
  tipo_vehiculo: TipoVehiculoTarifa;
  valor: number;
}
export interface TarifasPagina {
  items: Tarifa[];
  total: number;
  offset: number;
  limit: number;
}
