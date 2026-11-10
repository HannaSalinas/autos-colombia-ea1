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
  { path: '**', redirectTo: '' },
];
