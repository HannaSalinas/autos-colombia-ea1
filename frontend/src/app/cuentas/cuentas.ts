import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { AuthService } from '../auth/auth.service';
import { Confirmacion } from '../confirmacion/confirmacion';
import { Rol } from '../models/auth';
import { Cuenta, CuentaDetalle, FiltrosCuentas } from '../models/cuenta';
import { CuentasService } from '../services/cuentas.service';
import {
  CONTRASENA_MAXIMA,
  NOMBRE_MAXIMO,
  USUARIO_MAXIMO,
  mensajeDe,
  normalizarUsuario,
  reglaContrasena,
  reglaNombre,
  reglaUsuario,
} from '../utils/reglas';

const ROLES: Record<string, string> = { ADMINISTRADOR: 'Administrador', OPERADOR: 'Operador' };
const ACCIONES: Record<string, string> = {
  CREAR: 'Creó la cuenta',
  DESACTIVAR: 'Desactivó la cuenta',
  REACTIVAR: 'Reactivó la cuenta',
};

/**
 * Gestión de cuentas de usuario (HU-19, HU-20, HU-21). Solo para el Administrador.
 * No se editan los datos de las cuentas ni se borran (D4, D6): se crean, se consultan y se
 * desactivan o reactivan. Las reglas de estado las vuelve a validar el servidor con bloqueos.
 */
@Component({
  selector: 'app-cuentas',
  imports: [ReactiveFormsModule, Confirmacion],
  templateUrl: './cuentas.html',
  styleUrl: './cuentas.css',
})
export class Cuentas {
  private readonly api = inject(CuentasService);
  private readonly auth = inject(AuthService);
  private readonly destroy = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly limit = 10;
  readonly maximos = {
    nombre: NOMBRE_MAXIMO,
    usuario: USUARIO_MAXIMO,
    contrasena: CONTRASENA_MAXIMA,
  };

  readonly form = this.fb.nonNullable.group({
    nombre: ['', reglaNombre],
    nombre_usuario: ['', reglaUsuario],
    contrasena: ['', reglaContrasena],
    rol: this.fb.nonNullable.control<Rol | ''>('', (c) =>
      c.value ? null : { rol: 'Elige el rol de la cuenta.' },
    ),
  });
  readonly filtros = this.fb.nonNullable.group({
    buscar: [''],
    rol: this.fb.nonNullable.control<Rol | ''>(''),
    estado: this.fb.nonNullable.control<'ACTIVA' | 'INACTIVA' | ''>(''),
  });

  readonly items = signal<Cuenta[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly cargando = signal(false);
  readonly guardando = signal(false);
  readonly ocupado = computed(() => this.cargando() || this.guardando());
  readonly mostrarFormulario = signal(false);
  readonly errorLista = signal('');
  readonly errorAccion = signal('');
  readonly exito = signal('');
  readonly porDesactivar = signal<Cuenta | null>(null);
  /** Mensaje del servidor cuando el usuario ya existe (409). Se borra al cambiar el usuario. */
  readonly usuarioEnUso = signal('');
  readonly detalle = signal<CuentaDetalle | null>(null);
  readonly miCuentaId = computed(() => this.auth.cuenta()?.id ?? null);
  private filtrosAplicados: FiltrosCuentas = {};

  constructor() {
    this.form.controls.nombre_usuario.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => this.usuarioEnUso.set(''));
    this.cargar(0);
  }

  cargar(offset = this.offset()): void {
    this.cargando.set(true);
    this.errorLista.set('');
    this.api
      .listar(this.filtrosAplicados, offset, this.limit)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (pagina) => {
          this.cargando.set(false);
          // Si la página quedó vacía (por ejemplo, tras filtrar), vuelve a la anterior.
          if (!pagina.items.length && pagina.total && offset > 0) {
            this.cargar(Math.max(0, offset - this.limit));
            return;
          }
          this.items.set(pagina.items);
          this.total.set(pagina.total);
          this.offset.set(offset);
        },
        error: (error: HttpErrorResponse) => {
          this.cargando.set(false);
          this.errorLista.set(this.mensaje(error));
        },
      });
  }

  buscar(): void {
    this.filtrosAplicados = this.filtros.getRawValue();
    this.cargar(0);
  }

  limpiarFiltros(): void {
    this.filtros.reset();
    this.buscar();
  }

  nueva(): void {
    this.form.reset();
    this.usuarioEnUso.set('');
    this.exito.set('');
    this.errorAccion.set('');
    this.mostrarFormulario.set(true);
  }

  cancelar(): void {
    this.form.reset();
    this.mostrarFormulario.set(false);
    this.porDesactivar.set(null);
  }

  /** HU-19: crea la cuenta activa. La contraseña se borra del formulario y nunca se muestra. */
  crear(): void {
    if (this.guardando()) return;
    this.form.controls.nombre_usuario.setValue(
      normalizarUsuario(this.form.controls.nombre_usuario.value),
    );
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const datos = this.form.getRawValue();
    this.guardando.set(true);
    this.errorAccion.set('');
    this.api
      .crear({
        nombre: datos.nombre.trim(),
        nombre_usuario: datos.nombre_usuario,
        contrasena: datos.contrasena,
        rol: datos.rol as Rol,
      })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (cuenta) => {
          this.guardando.set(false);
          this.form.reset();
          this.mostrarFormulario.set(false);
          this.exito.set(`Cuenta de ${cuenta.nombre} (${cuenta.nombre_usuario}) creada y activa.`);
          this.cargar(this.offset());
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.form.controls.contrasena.reset();
          if (error.status === 409) {
            this.usuarioEnUso.set(this.detalleDe(error) || 'Ese nombre de usuario ya está en uso.');
          } else {
            this.errorAccion.set(this.mensaje(error));
          }
        },
      });
  }

  error(campo: keyof typeof this.form.controls): string {
    if (campo === 'nombre_usuario' && this.usuarioEnUso()) return this.usuarioEnUso();
    const control = this.form.controls[campo];
    return control.touched ? mensajeDe(control.errors) : '';
  }

  /** RNF-21: primero se pide confirmación nombrando a la persona. */
  pedirDesactivar(cuenta: Cuenta): void {
    this.exito.set('');
    this.errorAccion.set('');
    this.mostrarFormulario.set(false);
    this.porDesactivar.set(cuenta);
  }

  desactivar(): void {
    const cuenta = this.porDesactivar();
    if (!cuenta || this.guardando()) return;
    this.cambiarEstado(cuenta, 'desactivar');
  }

  reactivar(cuenta: Cuenta): void {
    if (this.guardando()) return;
    this.exito.set('');
    this.errorAccion.set('');
    this.cambiarEstado(cuenta, 'reactivar');
  }

  verDetalle(cuenta: Cuenta): void {
    this.errorAccion.set('');
    this.api
      .detalle(cuenta.id)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (detalle) => this.detalle.set(detalle),
        error: (error: HttpErrorResponse) => this.errorAccion.set(this.mensaje(error)),
      });
  }

  esMiCuenta(cuenta: Cuenta): boolean {
    return cuenta.id === this.miCuentaId();
  }

  rol(valor: string): string {
    return ROLES[valor] ?? valor;
  }

  accion(valor: string): string {
    return ACCIONES[valor] ?? valor;
  }

  fecha(valor: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota',
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(valor));
  }

  pagina(): number {
    return Math.floor(this.offset() / this.limit) + 1;
  }

  paginas(): number {
    return Math.max(1, Math.ceil(this.total() / this.limit));
  }

  private cambiarEstado(cuenta: Cuenta, accion: 'desactivar' | 'reactivar'): void {
    this.guardando.set(true);
    const solicitud =
      accion === 'desactivar' ? this.api.desactivar(cuenta.id) : this.api.reactivar(cuenta.id);
    solicitud.pipe(takeUntilDestroyed(this.destroy)).subscribe({
      next: (resultado) => {
        this.guardando.set(false);
        this.porDesactivar.set(null);
        this.exito.set(
          `Cuenta de ${resultado.nombre} ${resultado.activa ? 'reactivada: puede volver a ingresar' : 'desactivada: ya no puede ingresar'}.`,
        );
        if (this.detalle()?.id === cuenta.id) this.verDetalle(resultado);
        this.cargar(this.offset());
      },
      error: (error: HttpErrorResponse) => {
        this.guardando.set(false);
        this.porDesactivar.set(null);
        this.errorAccion.set(this.mensaje(error));
        this.cargar(this.offset());
      },
    });
  }

  private detalleDe(error: HttpErrorResponse): string {
    return typeof error.error?.detail === 'string' ? error.error.detail : '';
  }

  /** RNF-15: siempre un mensaje en español; nunca el detalle técnico. */
  private mensaje(error: HttpErrorResponse): string {
    if (error.status === 409 && this.detalleDe(error)) return this.detalleDe(error);
    if (error.status === 404) return 'La cuenta ya no existe. Actualiza el listado.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para gestionar cuentas.';
    if (error.status === 422) return 'Revisa los datos: hay campos que no cumplen las reglas.';
    return 'No se pudo conectar con el servicio. Intenta de nuevo.';
  }
}
