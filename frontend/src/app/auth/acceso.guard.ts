import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

/**
 * Guard de las pantallas protegidas (RF-22, HU-17.2).
 * 1. Sin sesión, lleva a /ingresar (recordando a dónde quería ir). Esto también aplica al botón
 *    "atrás" después de cerrar sesión: el guard vuelve a ejecutarse en cada navegación.
 * 2. Si la ruta pide un permiso (data.permiso) y la cuenta no lo tiene, vuelve al inicio.
 * Ocultar opciones no reemplaza el control del servidor (RF-21): la API también responde 403.
 */
export const accesoGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.restaurar().pipe(
    map((conSesion) => {
      if (!conSesion)
        return router.createUrlTree(['/ingresar'], { queryParams: { volver: state.url } });
      const permiso = route.data['permiso'] as string | undefined;
      return !permiso || auth.tiene(permiso) ? true : router.createUrlTree(['/']);
    }),
  );
};

/** La pantalla de ingreso no se muestra a quien ya tiene sesión. */
export const ingresoGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .restaurar()
    .pipe(map((conSesion) => (conSesion ? router.createUrlTree(['/']) : true)));
};
