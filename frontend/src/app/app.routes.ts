import { Routes } from '@angular/router';
import { accesoGuard, ingresoGuard } from './auth/acceso.guard';
import { PERMISOS } from './models/auth';

/**
 * Iteración 2: todas las pantallas, salvo /ingresar, exigen sesión (accesoGuard). Las que
 * dependen de un permiso lo declaran en `data.permiso`, el mismo nombre que usa el backend.
 * La pantalla de Operadores de la EA1 ya no tiene ruta: las personas se crean con su cuenta.
 */
export const routes: Routes = [
  {
    path: 'ingresar',
    title: 'Ingresar | Autos Colombia',
    canActivate: [ingresoGuard],
    loadComponent: () => import('./ingreso/ingreso').then((m) => m.Ingreso),
  },
  {
    path: 'control-acceso',
    title: 'Control de acceso | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.estancias },
    loadComponent: () => import('./control-acceso/control-acceso').then((m) => m.ControlAcceso),
  },
  {
    path: 'gestion/celdas',
    title: 'Celdas | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.celdasVer },
    loadComponent: () => import('./celdas/celdas').then((m) => m.Celdas),
  },
  {
    path: '',
    pathMatch: 'full',
    canActivate: [accesoGuard],
    loadComponent: () => import('./home/home').then((m) => m.Home),
  },
  {
    path: 'gestion/vehiculos',
    title: 'Vehículos | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.vehiculosVer },
    loadComponent: () => import('./vehiculos/vehiculos').then((m) => m.Vehiculos),
  },
  {
    path: 'consultas/ocupacion',
    title: 'Ocupación | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.consultas },
    loadComponent: () => import('./ocupacion/ocupacion').then((m) => m.Ocupacion),
  },
  {
    path: 'consultas/historial',
    title: 'Historial | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.consultas },
    loadComponent: () => import('./historial/historial').then((m) => m.Historial),
  },
  {
    path: 'gestion/cuentas',
    title: 'Cuentas de usuario | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.cuentasGestionar },
    loadComponent: () => import('./cuentas/cuentas').then((m) => m.Cuentas),
  },
  // Iteración 3: pagos de mensualidad (ambos roles; anular solo el Administrador, dentro del detalle).
  {
    // No es /pagos: ese prefijo es de la API y nginx lo envía al backend.
    path: 'registrar-pago',
    title: 'Pagos | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.pagos },
    loadComponent: () => import('./pagos/pagos').then((m) => m.Pagos),
  },
  {
    path: 'consultas/pagos',
    title: 'Pagos registrados | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.pagos },
    loadComponent: () => import('./consulta-pagos/consulta-pagos').then((m) => m.ConsultaPagos),
  },
  {
    path: 'consultas/pagos/:id',
    title: 'Detalle del pago | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.pagos },
    loadComponent: () => import('./pago-detalle/pago-detalle').then((m) => m.PagoDetalleComponent),
  },
  {
    path: 'consultas/recaudo',
    title: 'Recaudo | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.recaudoVer },
    loadComponent: () => import('./recaudo/recaudo').then((m) => m.RecaudoComponent),
  },
  {
    path: 'gestion/clientes',
    title: 'Clientes | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.vehiculosVer },
    loadComponent: () => import('./clientes/clientes').then((m) => m.Clientes),
  },
  {
    path: 'gestion/tarifas',
    title: 'Tarifas | Autos Colombia',
    canActivate: [accesoGuard],
    data: { permiso: PERMISOS.tarifasVer },
    loadComponent: () => import('./tarifas/tarifas').then((m) => m.Tarifas),
  },
  { path: '**', redirectTo: '' },
];
