import { Component, DestroyRef, computed, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, fromEvent, switchMap } from 'rxjs';
import { AuthService } from './auth/auth.service';
import { PERMISOS } from './models/auth';

interface OpcionMenu {
  ruta: string;
  etiqueta: string;
  /** Permiso del backend que exige la opción; sin permiso = la ve cualquier cuenta con sesión. */
  permiso?: string;
  exacta?: boolean;
}

/** Todas las opciones posibles. Cada cuenta ve solo las que su lista de permisos permite (RF-20). */
export const MENU: readonly OpcionMenu[] = [
  { ruta: '/', etiqueta: 'Inicio', exacta: true },
  { ruta: '/control-acceso', etiqueta: 'Control de acceso', permiso: PERMISOS.estancias },
  { ruta: '/consultas/ocupacion', etiqueta: 'Ocupación', permiso: PERMISOS.consultas },
  { ruta: '/consultas/historial', etiqueta: 'Historial', permiso: PERMISOS.consultas },
  { ruta: '/gestion/vehiculos', etiqueta: 'Vehículos', permiso: PERMISOS.vehiculosVer },
  { ruta: '/gestion/celdas', etiqueta: 'Celdas', permiso: PERMISOS.celdasVer },
  { ruta: '/gestion/cuentas', etiqueta: 'Cuentas de usuario', permiso: PERMISOS.cuentasGestionar },
];

const ROLES: Record<string, string> = { ADMINISTRADOR: 'Administrador', OPERADOR: 'Operador' };

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  /** Se recalcula sola cuando cambia la cuenta (señales): al ingresar, al salir o al recargar. */
  readonly menu = computed(() =>
    this.auth.cuenta() ? MENU.filter((o) => !o.permiso || this.auth.tiene(o.permiso)) : [],
  );
  readonly rol = computed(() => ROLES[this.auth.cuenta()?.rol ?? ''] ?? '');
  cerrando = false;

  constructor() {
    // HU-17.2: con el botón "atrás" el navegador puede devolver una página guardada en su caché
    // (bfcache) con la sesión que tenía en memoria. Al volver así, se comprueba otra vez la sesión.
    fromEvent<PageTransitionEvent>(window, 'pageshow')
      .pipe(
        filter((evento) => evento.persisted),
        switchMap(() => this.auth.revalidar()),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((conSesion) => {
        if (!conSesion) void this.router.navigate(['/ingresar'], { replaceUrl: true });
      });
  }

  /** HU-17: cierra la sesión en el servidor y vuelve al ingreso sin dejar la página en el historial. */
  cerrarSesion(): void {
    if (this.cerrando) return;
    this.cerrando = true;
    this.auth.cerrarSesion().subscribe(() => {
      this.cerrando = false;
      void this.router.navigate(['/ingresar'], {
        queryParams: { motivo: 'salida' },
        replaceUrl: true,
      });
    });
  }
}
