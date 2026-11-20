import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { AuthService } from '../auth/auth.service';
import { Confirmacion } from '../confirmacion/confirmacion';
import { PERMISOS } from '../models/auth';
import { TIPOS_VEHICULO_TARIFA, Tarifa, TarifaVigente, TipoVehiculoTarifa } from '../models/tarifa';
import { TarifasService } from '../services/tarifas.service';
import { formatoPesos } from '../utils/dinero';
import { fechaHora } from '../utils/fechas';
import { mensajeDe, reglaTarifa } from '../utils/reglas';

/**
 * Tarifas (HU-26 y HU-27). Ambos roles ven la tarifa vigente de cada tipo de vehículo. Solo el
 * Administrador define una tarifa nueva (con confirmación) y ve el historial con su autor. Una
 * tarifa nunca se edita ni se elimina: cada cambio crea una nueva, vigente desde ese momento (D12).
 */
@Component({
  selector: 'app-tarifas',
  imports: [ReactiveFormsModule, Confirmacion],
  templateUrl: './tarifas.html',
  styleUrls: ['../estilos/gestion.css', './tarifas.css'],
})
export class Tarifas {
  private readonly auth = inject(AuthService);
  private readonly api = inject(TarifasService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly puedeGestionar = computed(() => this.auth.tiene(PERMISOS.tarifasGestionar));
  readonly tipos = TIPOS_VEHICULO_TARIFA;
  readonly form = this.fb.nonNullable.group({
    tipo_vehiculo: this.fb.nonNullable.control<TipoVehiculoTarifa | ''>('', (c) =>
      c.value ? null : { tipo: 'Selecciona el tipo de vehículo.' },
    ),
    valor: this.fb.nonNullable.control('', reglaTarifa),
  });
  readonly filtroTipo = this.fb.nonNullable.control<TipoVehiculoTarifa | ''>('');
  readonly vigentes = signal<TarifaVigente[]>([]);
  readonly historial = signal<Tarifa[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly cargando = signal(false);
  readonly cargandoHistorial = signal(false);
  readonly guardando = signal(false);
  readonly mostrarFormulario = signal(false);
  readonly confirmando = signal(false);
  readonly error = signal('');
  readonly errorHistorial = signal('');
  readonly errorAccion = signal('');
  readonly exito = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));
  readonly pesos = formatoPesos;
  readonly fechaHora = fechaHora;

  constructor() {
    this.cargarVigentes();
    if (this.puedeGestionar()) this.cargarHistorial(0);
  }

  cargarVigentes(): void {
    this.cargando.set(true);
    this.error.set('');
    this.api
      .vigentes()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (vigentes) => {
          this.cargando.set(false);
          this.vigentes.set(vigentes);
        },
        error: (error: HttpErrorResponse) => {
          this.cargando.set(false);
          this.error.set(this.mensajeError(error));
        },
      });
  }

  cargarHistorial(offset = this.offset()): void {
    this.cargandoHistorial.set(true);
    this.errorHistorial.set('');
    this.api
      .historial(offset, this.limit, this.filtroTipo.value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (pagina) => {
          this.cargandoHistorial.set(false);
          this.historial.set(pagina.items);
          this.total.set(pagina.total);
          this.offset.set(offset);
        },
        error: (error: HttpErrorResponse) => {
          this.cargandoHistorial.set(false);
          this.errorHistorial.set(this.mensajeError(error));
        },
      });
  }

  nuevaTarifa(tipo: TipoVehiculoTarifa | '' = ''): void {
    this.form.reset({ tipo_vehiculo: tipo, valor: '' });
    this.mostrarFormulario.set(true);
    this.confirmando.set(false);
    this.errorAccion.set('');
    this.exito.set('');
  }

  errorCampo(campo: 'tipo_vehiculo' | 'valor'): string {
    const control = this.form.controls[campo];
    if (!control.touched) return '';
    return control.errors?.['server']
      ? String(control.errors['server'])
      : mensajeDe(control.errors);
  }

  /** Valor escrito como número (solo dígitos, ya validado). */
  valorNuevo(): number {
    return Number(this.form.controls.valor.value.trim());
  }

  actual(tipo: string): Tarifa | null {
    return this.vigentes().find((v) => v.tipo_vehiculo === tipo)?.tarifa ?? null;
  }

  mensajeConfirmacion(): string {
    const tipo = this.form.controls.tipo_vehiculo.value;
    const anterior = this.actual(tipo);
    const cambio = anterior
      ? `de ${formatoPesos(anterior.valor)} a ${formatoPesos(this.valorNuevo())}`
      : `en ${formatoPesos(this.valorNuevo())}`;
    return `¿Fijar la tarifa mensual de ${tipo} ${cambio}? Rige desde este momento para los pagos siguientes; los pagos ya registrados conservan su monto.`;
  }

  /** RNF-21: con datos válidos se pide una confirmación que nombra el tipo y los valores. */
  revisar(): void {
    this.form.controls.valor.setValue(this.form.controls.valor.value.trim());
    this.form.markAllAsTouched();
    this.errorAccion.set('');
    if (this.form.invalid) {
      this.errorAccion.set('Revisa los campos señalados antes de guardar la tarifa.');
      return;
    }
    this.confirmando.set(true);
  }

  cancelar(): void {
    if (this.guardando()) return;
    this.mostrarFormulario.set(false);
    this.confirmando.set(false);
    this.errorAccion.set('');
  }

  guardar(): void {
    if (this.guardando()) return;
    const tipo = this.form.controls.tipo_vehiculo.value as TipoVehiculoTarifa;
    this.guardando.set(true);
    this.api
      .crear({ tipo_vehiculo: tipo, valor: this.valorNuevo() })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (tarifa) => {
          this.guardando.set(false);
          this.mostrarFormulario.set(false);
          this.confirmando.set(false);
          this.exito.set(
            `Nueva tarifa de ${tarifa.tipo_vehiculo}: ${formatoPesos(tarifa.valor)} al mes, vigente desde ${fechaHora(tarifa.vigente_desde)}`,
          );
          this.cargarVigentes();
          this.cargarHistorial(0);
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.confirmando.set(false);
          this.errorAccion.set(this.mensajeError(error));
        },
      });
  }

  /** RNF-15: siempre un mensaje en español; el detalle técnico nunca llega a la pantalla. */
  private mensajeError(error: HttpErrorResponse): string {
    const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para gestionar tarifas.';
    if (error.status === 409)
      return detalle || 'La tarifa entra en conflicto con otra. Intenta de nuevo.';
    if (error.status === 422)
      return 'La tarifa debe ser un valor entero en pesos, sin decimales, entre $ 1.000 y $ 2.000.000.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza la página.';
  }
}
