/** Iteración 3: pagos de mensualidad. Mismos campos que backend/app/schemas/pago.py. */
export const METODOS_PAGO = [
  { valor: 'EFECTIVO', etiqueta: 'Efectivo' },
  { valor: 'TRANSFERENCIA', etiqueta: 'Transferencia' },
  { valor: 'TARJETA', etiqueta: 'Tarjeta' },
] as const;
export type MetodoPago = (typeof METODOS_PAGO)[number]['valor'];
export type EstadoPago = 'VALIDO' | 'ANULADO';
export type EstadoMensualidad = 'VIGENTE' | 'VENCIDA' | 'SIN_MENSUALIDAD' | 'PAGADA_A_FUTURO';

export interface Periodo {
  fecha_inicio: string;
  fecha_fin: string;
  /** null = periodo anterior a la Iteración 3, sin pago. */
  comprobante: string | null;
}
export interface EstadoMensualidadRespuesta {
  vehiculo_id: number;
  placa: string;
  tipo_vehiculo: string;
  marca: string;
  color: string;
  cliente: {
    id: number;
    tipo_documento: string;
    documento: string;
    nombre: string;
    telefono: string;
  };
  estado: EstadoMensualidad;
  periodo_actual: Periodo | null;
  periodos_futuros: Periodo[];
  periodos_anulados: Periodo[];
  vence: string | null;
  dias_restantes: number | null;
  inicio_nuevo_periodo: string;
  fin_maximo: string;
  tarifa: { id: number; tipo_vehiculo: string; valor: number } | null;
}
export interface Cotizacion {
  placa: string;
  cliente_nombre: string;
  tipo_vehiculo: string;
  meses: number;
  fecha_inicio: string;
  fecha_fin: string;
  tarifa_id: number;
  valor_mensual: number;
  monto: number;
}
export interface PagoCrear {
  placa: string;
  meses: number;
  metodo: MetodoPago;
  referencia?: string | null;
  /** El monto que vio quien cobra en el resumen (RNF-27). El servidor calcula el definitivo. */
  monto_confirmado: number;
}
export interface PagoResumen {
  id: number;
  comprobante: string;
  fecha: string;
  placa: string;
  cliente_nombre: string;
  fecha_inicio: string;
  fecha_fin: string;
  meses: number;
  monto: number;
  metodo: MetodoPago;
  estado: EstadoPago;
  registrado_por: string;
}
export interface PagoDetalle extends PagoResumen {
  vehiculo_id: number;
  tipo_vehiculo: string;
  cliente_tipo_documento: string;
  cliente_documento: string;
  valor_mensual: number;
  referencia: string | null;
  anulado_en: string | null;
  anulado_por: string | null;
  motivo_anulacion: string | null;
  /** Solo el pago VÁLIDO del último periodo del vehículo se puede anular (D14). */
  anulable: boolean;
}
export interface PagosPagina {
  items: PagoResumen[];
  total: number;
  offset: number;
  limit: number;
}
export interface FiltrosPagos {
  placa?: string;
  desde?: string;
  hasta?: string;
  metodo?: MetodoPago | '';
  estado?: EstadoPago | '';
}

export const ESTADOS_MENSUALIDAD: Record<EstadoMensualidad, string> = {
  VIGENTE: 'Vigente',
  VENCIDA: 'Vencida',
  SIN_MENSUALIDAD: 'Sin mensualidad',
  PAGADA_A_FUTURO: 'Pagada a futuro',
};
export const ESTADOS_PAGO: Record<EstadoPago, string> = { VALIDO: 'Válido', ANULADO: 'Anulado' };
export const etiquetaMetodo = (metodo: string): string =>
  METODOS_PAGO.find((m) => m.valor === metodo)?.etiqueta ?? metodo;

// --- Resumen de recaudo (RF-39, HU-33) ---
export interface TotalRecaudo {
  cantidad: number;
  total: number;
}
export interface Recaudo {
  desde: string;
  hasta: string;
  validos: TotalRecaudo;
  por_metodo: (TotalRecaudo & { metodo: MetodoPago })[];
  por_tipo_vehiculo: (TotalRecaudo & { tipo_vehiculo: string })[];
  anulados: TotalRecaudo;
}
