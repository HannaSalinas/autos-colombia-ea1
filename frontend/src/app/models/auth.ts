/** Iteración 2: cuenta con sesión, tal como la devuelven POST /auth/login y GET /auth/yo. */
export type Rol = 'ADMINISTRADOR' | 'OPERADOR';

/**
 * Permisos del backend (app/domain/permisos.py). El frontend NO decide qué puede hacer cada rol:
 * recibe la lista de permisos de la cuenta y muestra solo lo que esa lista permite (D2).
 */
export const PERMISOS = {
  estancias: 'estancias',
  consultas: 'consultas',
  celdasVer: 'celdas:ver',
  celdasGestionar: 'celdas:gestionar',
  vehiculosVer: 'vehiculos:ver',
  vehiculosGestionar: 'vehiculos:gestionar',
  cuentasGestionar: 'cuentas:gestionar',
} as const;
export type Permiso = (typeof PERMISOS)[keyof typeof PERMISOS];

export interface CuentaSesion {
  id: number;
  nombre_usuario: string;
  nombre: string;
  rol: Rol;
  permisos: string[];
}

export interface LoginRespuesta {
  token: string;
  tipo: 'bearer';
  expira_en: string;
  cuenta: CuentaSesion;
}
