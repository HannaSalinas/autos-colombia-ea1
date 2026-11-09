import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, map, of, tap, timeout } from 'rxjs';
import { CuentaSesion, LoginRespuesta, Permiso } from '../models/auth';
import { API_BASE_URL } from '../services/api.service';

/** Clave del token en sessionStorage: se borra sola al cerrar la pestaña (equipo compartido). */
export const CLAVE_TOKEN = 'autos-colombia.token';

/**
 * Sesión del usuario en el navegador (RF-19, RF-22).
 * - El token se guarda en sessionStorage, no en localStorage: si cierran la pestaña de la
 *   portería, la sesión no queda abierta para el siguiente.
 * - La cuenta y sus permisos viven en señales: el menú y los botones se actualizan solos.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/auth`;

  readonly cuenta = signal<CuentaSesion | null>(null);
  readonly autenticado = computed(() => this.cuenta() !== null);
  private readonly permisos = computed(() => new Set(this.cuenta()?.permisos ?? []));
  /** Solo si el navegador bloquea sessionStorage: entonces la sesión dura lo que dure la página. */
  private tokenEnMemoria: string | null = null;

  tiene(permiso: Permiso | string): boolean {
    return this.permisos().has(permiso);
  }

  token(): string | null {
    // sessionStorage es la fuente de verdad: si otra página de la misma pestaña cerró la sesión,
    // aquí ya no hay token aunque esta página lo tuviera en memoria.
    try {
      return sessionStorage.getItem(CLAVE_TOKEN);
    } catch {
      return this.tokenEnMemoria;
    }
  }

  login(usuario: string, contrasena: string): Observable<CuentaSesion> {
    return this.http.post<LoginRespuesta>(`${this.base}/login`, { usuario, contrasena }).pipe(
      timeout(15000),
      tap((respuesta) => {
        this.guardarToken(respuesta.token);
        this.cuenta.set(respuesta.cuenta);
      }),
      map((respuesta) => respuesta.cuenta),
    );
  }

  /**
   * El navegador restauró esta página desde su caché de "atrás/adelante" (bfcache): la página
   * vuelve con la memoria que tenía, sin pasar por el guard. Se descarta la cuenta en memoria y
   * se vuelve a comprobar la sesión con el servidor (HU-17.2).
   */
  revalidar(): Observable<boolean> {
    this.cuenta.set(null);
    return this.restaurar();
  }

  /** Al recargar la página: si hay token, pregunta al servidor quién es. Nunca lanza error. */
  restaurar(): Observable<boolean> {
    if (this.cuenta()) return of(true);
    if (!this.token()) return of(false);
    return this.http.get<CuentaSesion>(`${this.base}/yo`).pipe(
      timeout(15000),
      tap((cuenta) => this.cuenta.set(cuenta)),
      map(() => true),
      catchError(() => {
        this.limpiar();
        return of(false);
      }),
    );
  }

  /** Cierra la sesión en el servidor (el token deja de valer) y en el navegador, pase lo que pase. */
  cerrarSesion(): Observable<void> {
    const limpiar = () => this.limpiar();
    if (!this.token()) {
      limpiar();
      return of(undefined);
    }
    return this.http.post<void>(`${this.base}/cerrar-sesion`, null).pipe(
      timeout(15000),
      catchError(() => of(undefined)),
      tap({ next: limpiar, error: limpiar, complete: limpiar }),
      map(() => undefined),
    );
  }

  limpiar(): void {
    this.cuenta.set(null);
    this.tokenEnMemoria = null;
    try {
      sessionStorage.removeItem(CLAVE_TOKEN);
    } catch {
      /* nada que borrar */
    }
  }

  private guardarToken(token: string): void {
    try {
      sessionStorage.setItem(CLAVE_TOKEN, token);
    } catch {
      this.tokenEnMemoria = token; // sin almacenamiento la sesión dura mientras la página esté abierta
    }
  }
}
