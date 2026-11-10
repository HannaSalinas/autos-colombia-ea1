import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
} from '@angular/forms';
import { AuthService } from '../auth/auth.service';
import { Confirmacion } from '../confirmacion/confirmacion';
import { PERMISOS } from '../models/auth';
import {
  CeldaCrear,
  CeldaDetalle,
  CeldaGestion,
  ESTADOS_CELDA,
  FiltrosCeldas,
  TIPOS_CELDA,
  TipoCelda,
} from '../models/celda';
import { CeldasService } from '../services/celdas.service';
import { UBICACION_MAXIMA, normalizarCodigoCelda } from '../utils/reglas';

type Field = keyof CeldaCrear;
const PREFIJO: Record<string, string> = { CARRO: 'C', MOTO: 'M' };
const ESTADOS: Record<string, string> = {
  LIBRE: 'Libre',
  OCUPADA: 'Ocupada',
  INHABILITADA: 'Inhabilitada',
};
const ACCIONES: Record<string, string> = {
  CREAR: 'Creó la celda',
  EDITAR: 'Editó la celda',
  INHABILITAR: 'Inhabilitó la celda',
  REHABILITAR: 'Rehabilitó la celda',
};

/**
 * Misma regla que el backend y el CHECK de la base (RNF-16): C (carro) o M (moto) seguido de dos
 * dígitos del 01 al 99, con el prefijo de su tipo. El código se normaliza antes: ' c05 ' -> 'C05'.
 */
function reglaCodigo(grupo: AbstractControl): ValidationErrors | null {
  const codigo = normalizarCodigoCelda(String(grupo.get('codigo')?.value ?? ''));
  const tipo = String(grupo.get('tipo')?.value ?? '');
  if (!codigo) return null; // lo informa el validador del campo
  if (!/^[CM](0[1-9]|[1-9][0-9])$/.test(codigo))
    return { codigo: 'El código debe ser C o M seguido de dos dígitos del 01 al 99 (ej. C05).' };
  if (PREFIJO[tipo] && codigo[0] !== PREFIJO[tipo])
    return {
      codigo: `Una celda de tipo ${tipo} debe tener un código que empiece por ${PREFIJO[tipo]}.`,
    };
  return null;
}

/**
 * Gestión de celdas (HU-22 a HU-25). Ambos roles consultan; solo el Administrador crea, edita,
 * inhabilita y rehabilita. Las celdas nunca se eliminan (D4). Las reglas de estado (ocupada, con
 * historial) se muestran aquí y las vuelve a validar el servidor con bloqueo de la fila.
 */
@Component({
  selector: 'app-celdas',
  imports: [ReactiveFormsModule, Confirmacion],
  templateUrl: './celdas.html',
  styleUrl: './celdas.css',
})
export class Celdas {
  /** Iteración 2: el Operador solo consulta. */
  private readonly auth = inject(AuthService);
  readonly puedeGestionar = computed(() => this.auth.tiene(PERMISOS.celdasGestionar));
  private readonly api = inject(CeldasService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly ubicacionMaxima = UBICACION_MAXIMA;
  readonly form = this.fb.group(
    {
      codigo: this.fb.nonNullable.control('', (c) =>
        typeof c.value === 'string' && c.value.trim() ? null : { required: true },
      ),
      tipo: this.fb.nonNullable.control<TipoCelda | string>('', (c) =>
        (TIPOS_CELDA as readonly string[]).includes(c.value) ? null : { required: true },
      ),
      ubicacion: this.fb.nonNullable.control('', (c) =>
        String(c.value ?? '').trim().length > UBICACION_MAXIMA ? { ubicacion: true } : null,
      ),
    },
    { validators: reglaCodigo },
  );
  readonly filtros = this.fb.nonNullable.group({
    buscar: [''],
    tipo: this.fb.nonNullable.control<TipoCelda | ''>(''),
    estado: this.fb.nonNullable.control<FiltrosCeldas['estado']>(''),
  });
  readonly types = TIPOS_CELDA;
  readonly estados = ESTADOS_CELDA;
  readonly items = signal<CeldaGestion[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly showForm = signal(false);
  readonly editing = signal<number | null>(null);
  /** D8: al editar una celda con historial u ocupada, el código y el tipo quedan fijos. */
  readonly motivoBloqueo = signal('');
  readonly pendingDisable = signal<CeldaGestion | null>(null);
  readonly detalle = signal<CeldaDetalle | null>(null);
  readonly listError = signal('');
  readonly actionError = signal('');
  readonly success = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));
  private filtrosAplicados: FiltrosCeldas = {};

  constructor() {
    this.load();
  }

  load(offset = this.offset()): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .list(offset, this.limit, this.filtrosAplicados)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          if (offset > 0 && offset >= data.total) {
            this.load(Math.max(0, Math.floor((data.total - 1) / this.limit) * this.limit));
            return;
          }
          this.items.set(data.items);
          this.total.set(data.total);
          this.offset.set(offset);
        },
        error: (error) => {
          this.loading.set(false);
          this.listError.set(this.errorMessage(error));
        },
      });
  }

  buscar(): void {
    this.filtrosAplicados = this.filtros.getRawValue();
    this.offset.set(0);
    this.load(0);
  }

  limpiarFiltros(): void {
    this.filtros.reset();
    this.buscar();
  }

  newCell(): void {
    if (this.busy()) return;
    this.form.reset();
    this.form.controls.codigo.enable();
    this.form.controls.tipo.enable();
    this.motivoBloqueo.set('');
    this.editing.set(null);
    this.showForm.set(true);
    this.pendingDisable.set(null);
    this.actionError.set('');
    this.success.set('');
  }

  edit(cell: CeldaGestion): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.actionError.set('');
    this.success.set('');
    this.pendingDisable.set(null);
    this.api
      .get(cell.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.editing.set(data.id);
          this.form.reset({
            codigo: data.codigo,
            tipo: data.tipo,
            ubicacion: data.ubicacion ?? '',
          });
          const motivo =
            data.estado === 'OCUPADA'
              ? `La celda ${data.codigo} está ocupada: su código y su tipo no se pueden cambiar.`
              : data.tiene_historial
                ? `La celda ${data.codigo} ya tuvo movimientos: su código y su tipo quedan fijos para que el historial siga siendo legible. Solo se puede editar su ubicación.`
                : '';
          this.motivoBloqueo.set(motivo);
          if (motivo) {
            this.form.controls.codigo.disable();
            this.form.controls.tipo.disable();
          } else {
            this.form.controls.codigo.enable();
            this.form.controls.tipo.enable();
          }
          this.showForm.set(true);
        },
        error: (error) => {
          this.loading.set(false);
          this.actionError.set(this.errorMessage(error));
        },
      });
  }

  cancel(): void {
    if (this.busy()) return;
    this.showForm.set(false);
    this.pendingDisable.set(null);
    this.actionError.set('');
  }

  fieldError(field: Field): string {
    const control = this.form.controls[field];
    if (!control.touched) return '';
    if (control.errors?.['server']) return String(control.errors['server']);
    if (control.errors?.['required']) return 'Este campo es obligatorio y no puede estar vacío.';
    if (control.errors?.['ubicacion'])
      return `La ubicación admite máximo ${UBICACION_MAXIMA} caracteres.`;
    if (field === 'codigo' && this.form.errors?.['codigo'])
      return String(this.form.errors['codigo']);
    return control.errors ? 'Revisa este campo.' : '';
  }

  save(): void {
    if (this.busy()) return;
    this.form.controls.codigo.setValue(normalizarCodigoCelda(this.form.controls.codigo.value));
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Revisa los campos señalados antes de guardar la celda.');
      return;
    }
    const value = this.form.getRawValue();
    const ubicacion = value.ubicacion.trim() || null;
    const id = this.editing();
    // Al editar una celda con historial solo se envía la ubicación.
    const payload: Partial<CeldaCrear> =
      id !== null && this.motivoBloqueo()
        ? { ubicacion }
        : { codigo: value.codigo, tipo: value.tipo as TipoCelda, ubicacion };
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    const request =
      id === null ? this.api.create(payload as CeldaCrear) : this.api.update(id, payload);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (cell) => {
        this.saving.set(false);
        this.showForm.set(false);
        this.success.set(
          `Celda ${cell.codigo} ${id === null ? 'registrada' : 'actualizada'} correctamente.`,
        );
        if (this.detalle()?.id === cell.id) this.verDetalle(cell);
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        const detail = typeof error.error?.detail === 'string' ? error.error.detail : '';
        this.actionError.set(this.errorMessage(error));
        if (
          error.status === 409 &&
          (detail.includes('ocupada') || detail.includes('movimientos'))
        ) {
          // D8 y celda ocupada: el código y el tipo no se pueden cambiar.
          this.actionError.set(detail);
          this.setFieldError('tipo', detail);
        } else if (error.status === 409) {
          this.setFieldError('codigo', detail || 'Ya existe una celda con ese código.');
        }
      },
    });
  }

  private setFieldError(field: Field, message: string): void {
    this.form.controls[field].setErrors({ server: message });
    this.form.controls[field].markAsTouched();
  }

  /** RNF-21: confirmación que nombra la celda antes de inhabilitarla. */
  confirmDisable(cell: CeldaGestion): void {
    if (this.busy()) return;
    this.pendingDisable.set(cell);
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  disable(): void {
    const cell = this.pendingDisable();
    if (!cell || this.busy()) return;
    this.cambiarEstado(cell, 'inhabilitar');
  }

  enable(cell: CeldaGestion): void {
    if (this.busy()) return;
    this.actionError.set('');
    this.success.set('');
    this.cambiarEstado(cell, 'rehabilitar');
  }

  verDetalle(cell: CeldaGestion): void {
    this.actionError.set('');
    this.api
      .get(cell.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => this.detalle.set(data),
        error: (error) => this.actionError.set(this.errorMessage(error)),
      });
  }

  estado(valor: string): string {
    return ESTADOS[valor] ?? valor;
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

  private cambiarEstado(cell: CeldaGestion, accion: 'inhabilitar' | 'rehabilitar'): void {
    this.saving.set(true);
    const solicitud =
      accion === 'inhabilitar' ? this.api.inhabilitar(cell.id) : this.api.rehabilitar(cell.id);
    solicitud.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (resultado) => {
        this.saving.set(false);
        this.pendingDisable.set(null);
        this.success.set(
          accion === 'inhabilitar'
            ? `Celda ${resultado.codigo} inhabilitada: ya no se asigna a nuevas entradas.`
            : `Celda ${resultado.codigo} rehabilitada: vuelve a estar disponible.`,
        );
        if (this.detalle()?.id === cell.id) this.verDetalle(resultado);
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.pendingDisable.set(null);
        this.actionError.set(this.errorMessage(error));
        this.load();
      },
    });
  }

  /** RNF-15: siempre un mensaje en español; el detalle técnico nunca llega a la pantalla. */
  private errorMessage(error: HttpErrorResponse): string {
    const detail = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (error.status === 404) return 'La celda ya no existe. Actualiza el listado.';
    if (error.status === 409) return detail || 'Ya existe una celda con ese código.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para gestionar celdas.';
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado antes de reintentar.';
  }
}
