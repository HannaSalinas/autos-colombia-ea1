import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

const esLogin = (url: string) => url.endsWith('/auth/login');

/**
 * Interceptor del token (RF-21, HU-16.4):
 * - Agrega `Authorization: Bearer <token>` a cada solicitud a la API, salvo al login.
 * - Si el servidor responde 401 (sesión vencida, cerrada o cuenta desactivada), borra la sesión
 *   y lleva a la pantalla de ingreso con un aviso. El 401 del propio login lo maneja su pantalla.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = auth.token();
  const solicitud =
    token && !esLogin(req.url)
      ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : req;
  return next(solicitud).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && !esLogin(req.url)) {
        auth.limpiar();
        void router.navigate(['/ingresar'], { queryParams: { motivo: 'sesion' } });
      }
      return throwError(() => error);
    }),
  );
};
