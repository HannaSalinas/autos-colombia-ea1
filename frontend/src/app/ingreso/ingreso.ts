import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../auth/auth.service';

const noVacio: ValidatorFn = (c) =>
  typeof c.value === 'string' && c.value.trim() ? null : { required: true };

/** Avisos al llegar a esta pantalla desde otra (interceptor o cierre de sesión). */
const AVISOS: Record<string, string> = {
  sesion: 'Tu sesión venció o fue cerrada. Ingresa de nuevo.',
  salida: 'Cerraste sesión.',
};

/**
 * Pantalla de ingreso (HU-15). Nunca se elige el rol (D1): llega con la cuenta.
 * Los mensajes son siempre en español y nunca técnicos (RNF-15).
 */
@Component({
  selector: 'app-ingreso',
  imports: [ReactiveFormsModule],
  templateUrl: './ingreso.html',
  styleUrl: './ingreso.css',
})
export class Ingreso {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroy = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);

  readonly form = this.fb.nonNullable.group({
    usuario: ['', noVacio],
    contrasena: ['', noVacio],
  });
  readonly enviando = signal(false);
  readonly error = signal('');
  readonly aviso = signal(AVISOS[this.route.snapshot.queryParamMap.get('motivo') ?? ''] ?? '');

  ingresar(): void {
    if (this.enviando()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const { usuario, contrasena } = this.form.getRawValue();
    this.enviando.set(true);
    this.error.set('');
    this.aviso.set('');
    this.auth
      .login(usuario.trim(), contrasena)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: () => {
          this.enviando.set(false);
          void this.router.navigateByUrl(this.destino());
        },
        error: (error: HttpErrorResponse) => {
          this.enviando.set(false);
          this.form.controls.contrasena.reset();
          this.error.set(this.mensaje(error));
        },
      });
  }

  campoInvalido(campo: 'usuario' | 'contrasena'): boolean {
    const control = this.form.controls[campo];
    return control.touched && control.invalid;
  }

  /** Solo rutas internas: evita que un enlace manipulado lleve a otro sitio. */
  private destino(): string {
    const volver = this.route.snapshot.queryParamMap.get('volver') ?? '/';
    return volver.startsWith('/') && !volver.startsWith('//') && !volver.startsWith('/ingresar')
      ? volver
      : '/';
  }

  private mensaje(error: HttpErrorResponse): string {
    if (error.status === 401) return 'Usuario o contraseña inválidos.';
    if (error.status === 403)
      return typeof error.error?.detail === 'string'
        ? error.error.detail
        : 'Tu cuenta está desactivada. Contacta al administrador.';
    if (error.status === 422) return 'Escribe tu usuario y tu contraseña.';
    return 'No se pudo conectar con el servicio. Intenta de nuevo en un momento.';
  }
}
