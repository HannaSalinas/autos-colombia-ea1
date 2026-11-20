/** Iteración 3 (RF-34, D15): el Administrador registra clientes; ambos roles los consultan. */
export const TIPOS_DOCUMENTO = [
  { valor: 'CC', etiqueta: 'Cédula de ciudadanía (CC)' },
  { valor: 'CE', etiqueta: 'Cédula de extranjería (CE)' },
  { valor: 'PA', etiqueta: 'Pasaporte (PA)' },
] as const;
export type TipoDocumento = (typeof TIPOS_DOCUMENTO)[number]['valor'];

export interface VehiculoDelCliente {
  id: number;
  placa: string;
  tipo: string;
}
export interface Cliente {
  id: number;
  documento: string;
  nombre: string;
  telefono: string;
  correo: string | null;
  // Iteración 3. Opcionales para no exigirlos en las pantallas de la EA2 que solo listan clientes.
  tipo_documento?: string;
  /** D18: quién y cuándo lo registró. null = anterior a la Iteración 3 o creado por las semillas. */
  registrado_en?: string | null;
  registrado_por?: string | null;
  vehiculos?: VehiculoDelCliente[];
}
export interface ClienteCrear {
  tipo_documento: TipoDocumento;
  documento: string;
  nombre: string;
  telefono: string;
  correo: string | null;
}
export interface ClientesPagina {
  items: Cliente[];
  total: number;
  offset: number;
  limit: number;
}
