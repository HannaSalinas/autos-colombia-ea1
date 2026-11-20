import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../auth/auth.service';
import { PERMISOS } from '../models/auth';
import { Cliente, ClienteCrear, TIPOS_DOCUMENTO, TipoDocumento } from '../models/cliente';
import { ClientesService } from '../services/clientes.service';
import { fechaHora } from '../utils/fechas';
import {
  mensajeDe,
  normalizarDocumento,
  reglaCorreo,
  reglaDocumento,
  reglaNombre,
  reglaTelefono,
} from '../utils/reglas';

type Campo = keyof ClienteCrear;

/**
 * Clientes (HU-28). Ambos roles buscan por nombre o documento y ven los vehículos de cada cliente.
 * Solo el Administrador registra (D15). Sin edición ni eliminación en esta iteración (D17). Las
 * reglas son las mismas del backend y de la base (RNF-16); el documento repetido lo detecta el
 * servidor (409), también si dos personas registran el mismo documento a la vez.
 */
@Component({
  selector: 'app-clientes',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './clientes.html',
  styleUrls: ['../estilos/gestion.css', './clientes.css'],
})
export class Clientes {
  private readonly auth = inject(AuthService);
  private readonly api = inject(ClientesService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly puedeRegistrar = computed(() => this.auth.tiene(PERMISOS.clientesGestionar));
  readonly tiposDocumento = TIPOS_DOCUMENTO;
  readonly form = this.fb.nonNullable.group({
    tipo_documento: this.fb.nonNullable.control<TipoDocumento | ''>('CC', (c) =>
      c.value ? null : { tipo: 'Selecciona el tipo de documento.' },
    ),
    documento: this.fb.nonNullable.control('', reglaDocumento),
    nombre: this.fb.nonNullable.control('', reglaNombre),
    telefono: this.fb.nonNullable.control('', reglaTelefono),
    correo: this.fb.nonNullable.control('', reglaCorreo),
  });
  readonly busquedaForm = this.fb.nonNullable.group({ buscar: [''] });
  readonly items = signal<Cliente[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly cargando = signal(false);
  readonly guardando = signal(false);
  readonly mostrarFormulario = signal(false);
  readonly detalle = signal<Cliente | null>(null);
  readonly errorLista = signal('');
  readonly errorAccion = signal('');
  readonly exito = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));
  readonly fechaHora = fechaHora;
  private busqueda = '';

  constructor() {
    this.cargar(0);
  }

  cargar(offset = this.offset()): void {
    if (this.cargando()) return;
    this.cargando.set(true);
    this.errorLista.set('');
    this.api
      .list(offset, this.limit, this.busqueda)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (pagina) => {
          this.cargando.set(false);
          this.items.set(pagina.items);
          this.total.set(pagina.total);
          this.offset.set(offset);
        },
        error: (error: HttpErrorResponse) => {
          this.cargando.set(false);
          this.errorLista.set(this.mensajeError(error));
        },
      });
  }

  buscar(): void {
    this.busqueda = this.busquedaForm.controls.buscar.value.trim();
    this.cargar(0);
  }

  limpiar(): void {
    this.busquedaForm.reset();
    this.buscar();
  }

  nuevo(): void {
    this.form.reset({ tipo_documento: 'CC', documento: '', nombre: '', telefono: '', correo: '' });
    this.mostrarFormulario.set(true);
    this.errorAccion.set('');
    this.exito.set('');
  }

  cancelar(): void {
    if (this.guardando()) return;
    this.mostrarFormulario.set(false);
    this.errorAccion.set('');
  }

  errorCampo(campo: Campo): string {
    const control = this.form.controls[campo];
    if (!control.touched) return '';
    return control.errors?.['server']
      ? String(control.errors['server'])
      : mensajeDe(control.errors);
  }

  guardar(): void {
    if (this.guardando()) return;
    this.form.controls.documento.setValue(normalizarDocumento(this.form.controls.documento.value));
    this.form.markAllAsTouched();
    this.errorAccion.set('');
    if (this.form.invalid) {
      this.errorAccion.set('Revisa los campos señalados antes de registrar el cliente.');
      return;
    }
    const valor = this.form.getRawValue();
    this.guardando.set(true);
    this.api
      .create({
        tipo_documento: valor.tipo_documento as TipoDocumento,
        documento: valor.documento,
        nombre: valor.nombre.trim(),
        telefono: valor.telefono.trim(),
        correo: valor.correo.trim() || null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (cliente) => {
          this.guardando.set(false);
          this.mostrarFormulario.set(false);
          this.exito.set(
            `Cliente ${cliente.nombre} registrado (${cliente.tipo_documento} ${cliente.documento}). Para asociarle un vehículo, regístralo en Vehículos.`,
          );
          this.detalle.set(cliente);
          this.busquedaForm.setValue({ buscar: cliente.documento });
          this.buscar();
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
          this.errorAccion.set(this.mensajeError(error));
          if (error.status === 409) {
            this.form.controls.documento.setErrors({
              server: detalle || 'Ya existe un cliente con ese tipo y número de documento.',
            });
            this.form.controls.documento.markAsTouched();
          }
        },
      });
  }

  verDetalle(cliente: Cliente): void {
    this.errorAccion.set('');
    this.api
      .get(cliente.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (datos) => this.detalle.set(datos),
        error: (error: HttpErrorResponse) => this.errorAccion.set(this.mensajeError(error)),
      });
  }

  registro(cliente: Cliente): string {
    return cliente.registrado_en
      ? `${fechaHora(cliente.registrado_en)} · ${cliente.registrado_por ?? ''}`
      : 'Antes de la Iteración 3 (semillas)';
  }

  /** RNF-15: siempre un mensaje en español; el detalle técnico nunca llega a la pantalla. */
  private mensajeError(error: HttpErrorResponse): string {
    const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (error.status === 404) return 'El cliente ya no existe. Actualiza el listado.';
    if (error.status === 409)
      return detalle || 'Ya existe un cliente con ese tipo y número de documento.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para registrar clientes.';
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado.';
  }
}
