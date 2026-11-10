import { Rol } from './auth';

/** Iteración 2: cuentas de usuario (la contraseña nunca llega del servidor). */
export interface Cuenta {
  id: number;
  nombre: string;
  nombre_usuario: string;
  rol: Rol;
  activa: boolean;
  creada_en: string;
}
export interface CuentaCrear {
  nombre: string;
  nombre_usuario: string;
  contrasena: string;
  rol: Rol;
}
export interface CuentasPagina {
  items: Cuenta[];
  total: number;
  offset: number;
  limit: number;
}
export interface EventoAuditoria {
  fecha: string;
  accion: string;
  detalle: string | null;
  /** null = el sistema (semillas). */
  actor: string | null;
}
export interface CuentaDetalle extends Cuenta {
  auditoria: EventoAuditoria[];
}
export interface FiltrosCuentas {
  buscar?: string;
  rol?: Rol | '';
  estado?: 'ACTIVA' | 'INACTIVA' | '';
}
