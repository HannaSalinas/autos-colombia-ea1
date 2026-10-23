import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'control-acceso',
    title: 'Control de acceso | Autos Colombia',
    loadComponent: () => import('./control-acceso/control-acceso').then((m) => m.ControlAcceso),
  },
  {
    path: 'gestion/operadores',
    title: 'Operadores | Autos Colombia',
    loadComponent: () => import('./operadores/operadores').then((m) => m.Operadores),
  },
  {
    path: 'gestion/celdas',
    title: 'Celdas | Autos Colombia',
    loadComponent: () => import('./celdas/celdas').then((m) => m.Celdas),
  },
  { path: '', pathMatch: 'full', loadComponent: () => import('./home/home').then((m) => m.Home) },
  {
    path: 'gestion/vehiculos',
    title: 'Vehículos | Autos Colombia',
    loadComponent: () => import('./vehiculos/vehiculos').then((m) => m.Vehiculos),
  },
  {
    path: 'consultas/ocupacion',
    title: 'Ocupación | Autos Colombia',
    loadComponent: () => import('./ocupacion/ocupacion').then((m) => m.Ocupacion),
  },
  {
    path: 'consultas/historial',
    title: 'Historial | Autos Colombia',
    loadComponent: () => import('./historial/historial').then((m) => m.Historial),
  },
  { path: '**', redirectTo: '' },
];
