import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { Cliente } from '../models/cliente';
import { ApiService } from '../services/api.service';
import { ClientesService } from '../services/clientes.service';
import { normalizarPlaca } from '../utils/placa';
import {
  ErrorApi,
  TIPOS_VEHICULO,
  TipoVehiculo,
  Vehiculo,
  VehiculoCrear,
} from '../models/vehiculo';

const nonBlank: ValidatorFn = (control) =>
  typeof control.value === 'string' && control.value.trim() ? null : { required: true };
// Año actual en Bogotá: el modelo va de 1900 al año actual + 1 (misma regla que el backend).
export const MODELO_MINIMO = 1900;
export const modeloMaximo = () =>
  Number(new Intl.DateTimeFormat('en', { timeZone: 'America/Bogota', year: 'numeric' }).format()) +
  1;
const year: ValidatorFn = (control) =>
  Number.isInteger(control.value) &&
  control.value >= MODELO_MINIMO &&
  control.value <= modeloMaximo()
    ? null
    : { year: true };
const PLACA_CARRO = /^[A-Z]{3}[0-9]{3}$/;
const PLACA_MOTO = /^[A-Z]{3}[0-9]{2}[A-Z]$/;
/** Valida la placa según el tipo elegido; el error queda en el formulario completo. */
const placaSegunTipo: ValidatorFn = (group) => {
  const placa = normalizarPlaca(String(group.get('placa')?.value ?? ''));
  const tipo = group.get('tipo')?.value;
  if (!placa || !tipo) return null;
  const valida = tipo === 'MOTO' ? PLACA_MOTO.test(placa) : PLACA_CARRO.test(placa);
  return valida ? null : { placaFormato: tipo === 'MOTO' ? 'moto' : 'carro' };
};
type Field = keyof VehiculoCrear;

@Component({
  selector: 'app-vehiculos',
  imports: [ReactiveFormsModule],
  templateUrl: './vehiculos.html',
  styleUrl: './vehiculos.css',
})
export class Vehiculos {
  private readonly api = inject(ApiService);
  private readonly clientsApi = inject(ClientesService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly types = TIPOS_VEHICULO;
  readonly fields: { key: 'placa' | 'color' | 'modelo' | 'marca'; label: string; type: string }[] =
    [
      { key: 'placa', label: 'Placa', type: 'text' },
      { key: 'marca', label: 'Marca', type: 'text' },
      { key: 'modelo', label: 'Modelo (año)', type: 'number' },
      { key: 'color', label: 'Color', type: 'text' },
    ];
  readonly minYear = MODELO_MINIMO;
  readonly maxYear = modeloMaximo();
  readonly form = this.fb.group(
    {
      placa: this.fb.nonNullable.control('', nonBlank),
      color: this.fb.nonNullable.control('', nonBlank),
      modelo: this.fb.control<number | null>(null, [Validators.required, year]),
      marca: this.fb.nonNullable.control('', nonBlank),
      tipo: this.fb.nonNullable.control<TipoVehiculo | ''>('', [
        Validators.required,
        (control) => (this.types.includes(control.value) ? null : { type: true }),
      ]),
      cliente_id: this.fb.control<number | null>(null, Validators.required),
    },
    { validators: placaSegunTipo },
  );
  readonly clients = signal<Cliente[]>([]);
  readonly clientsError = signal('');
  readonly items = signal<Vehiculo[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly showForm = signal(false);
  readonly editing = signal<number | null>(null);
  readonly pendingDelete = signal<Vehiculo | null>(null);
  readonly listError = signal('');
  readonly actionError = signal('');
  readonly success = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));

  constructor() {
    this.load();
    this.loadClients();
  }

  loadClients(): void {
    this.clientsError.set('');
    this.clientsApi
      .todos()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (clients) => this.clients.set(clients),
        error: () =>
          this.clientsError.set('No se pudieron cargar los clientes. Recarga la página.'),
      });
  }

  /** Texto de la columna Mensualidad: 'Vigente hasta 20/11/2026', 'Empieza el …', 'Vencida el …'. */
  mensualidad(vehicle: Vehiculo): string {
    // Fechas 'AAAA-MM-DD' sin hora: se reordenan sin convertir zona horaria.
    const fecha = (iso: string) => iso.split('-').reverse().join('/');
    if (vehicle.mensualidad_vigente && vehicle.mensualidad_hasta)
      return `Vigente hasta ${fecha(vehicle.mensualidad_hasta)}`;
    if (vehicle.mensualidad_proxima) return `Empieza el ${fecha(vehicle.mensualidad_proxima)}`;
    if (vehicle.mensualidad_hasta) return `Vencida el ${fecha(vehicle.mensualidad_hasta)}`;
    return 'Sin mensualidad';
  }

  load(offset = this.offset()): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .list(offset, this.limit)
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

  newVehicle(): void {
    if (this.busy()) return;
    this.form.reset();
    this.editing.set(null);
    this.showForm.set(true);
    this.pendingDelete.set(null);
    this.actionError.set('');
    this.success.set('');
  }

  edit(vehicle: Vehiculo): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.actionError.set('');
    this.success.set('');
    this.pendingDelete.set(null);
    this.api
      .get(vehicle.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.editing.set(data.id);
          this.form.reset(data);
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
    this.pendingDelete.set(null);
    this.actionError.set('');
  }

  fieldError(field: Field): string {
    const control = this.form.controls[field];
    const formato = this.form.errors?.['placaFormato'];
    if (field === 'placa' && control.touched && !control.errors && formato)
      return formato === 'moto'
        ? 'La placa de moto debe tener 3 letras, 2 números y 1 letra (ej. ABC12D).'
        : 'La placa de carro debe tener 3 letras y 3 números (ej. ABC123).';
    if (!control.touched || !control.errors) return '';
    if (control.errors['server']) return String(control.errors['server']);
    if (field === 'cliente_id' && control.errors['required']) return 'Selecciona el cliente.';
    if (control.errors['required']) return 'Este campo es obligatorio y no puede estar vacío.';
    if (field === 'modelo')
      return `Introduce un año entero entre ${this.minYear} y ${this.maxYear}.`;
    if (field === 'tipo') return 'Selecciona un tipo válido.';
    return 'Revisa este campo.';
  }

  save(): void {
    if (this.busy()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Revisa los campos señalados antes de guardar el vehículo.');
      return;
    }
    const value = this.form.getRawValue();
    const payload: VehiculoCrear = {
      placa: normalizarPlaca(value.placa),
      color: value.color.trim(),
      marca: value.marca.trim(),
      modelo: value.modelo!,
      tipo: value.tipo as TipoVehiculo,
      cliente_id: value.cliente_id!,
    };
    this.form.controls.placa.setValue(payload.placa);
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    const id = this.editing();
    const request = id === null ? this.api.create(payload) : this.api.update(id, payload);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (vehicle) => {
        this.saving.set(false);
        this.showForm.set(false);
        this.success.set(
          `Vehículo ${vehicle.placa} ${id === null ? 'registrado' : 'actualizado'} correctamente.`,
        );
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        const body = error.error as ErrorApi | null;
        const detail = typeof body?.detail === 'string' ? body.detail : '';
        this.actionError.set(this.errorMessage(error));
        if (error.status === 409 && detail.includes('tipo')) {
          // Iteración 1: no se cambia el tipo de un vehículo que está dentro.
          this.actionError.set(detail);
          this.setFieldError('tipo', detail);
        } else if (error.status === 409) {
          this.setFieldError('placa', 'Ya existe un vehículo con esa placa.');
        } else if (detail && error.status !== 0) {
          // Mensajes de negocio del backend (cliente inexistente, placa según tipo, etc.).
          this.actionError.set(detail);
        }
        if (error.status === 422 && Array.isArray(body?.detail)) {
          for (const issue of body.detail) {
            const field = issue.loc.at(-1);
            if (typeof field === 'string' && Object.hasOwn(this.form.controls, field)) {
              this.setFieldError(
                field as Field,
                'El servicio rechazó este valor. Revisa el campo.',
              );
            }
          }
        }
      },
    });
  }

  private setFieldError(field: Field, message: string): void {
    this.form.controls[field].setErrors({ server: message });
    this.form.controls[field].markAsTouched();
  }

  confirmDelete(vehicle: Vehiculo): void {
    if (this.busy()) return;
    this.pendingDelete.set(vehicle);
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  remove(): void {
    const vehicle = this.pendingDelete();
    if (!vehicle || this.busy()) return;
    this.saving.set(true);
    this.actionError.set('');
    this.api
      .delete(vehicle.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.pendingDelete.set(null);
          this.success.set(`Vehículo ${vehicle.placa} eliminado correctamente.`);
          this.load();
        },
        error: (error) => {
          this.saving.set(false);
          this.actionError.set(this.errorMessage(error, true));
          if (error.status === 404) {
            this.pendingDelete.set(null);
            this.load();
          }
        },
      });
  }

  private errorMessage(error: HttpErrorResponse, deleting = false): string {
    if (error.status === 404) return 'El vehículo ya no existe. Actualiza el listado.';
    if (error.status === 409)
      return deleting
        ? 'No se puede eliminar: el vehículo tiene registros relacionados o un conflicto con otros datos.'
        : 'Ya existe un vehículo con esa placa.';
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado antes de reintentar.';
  }
}
