import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../auth/auth.service';
import { Comprobante } from '../comprobante/comprobante';
import { Confirmacion } from '../confirmacion/confirmacion';
import { PERMISOS } from '../models/auth';
import { PagoDetalle } from '../models/pago';
import { PagosService } from '../services/pagos.service';
import { formatoPesos } from '../utils/dinero';
import { fechaCorta } from '../utils/fechas';
import {
  MOTIVO_ANULACION_MAXIMO,
  MOTIVO_ANULACION_MINIMO,
  mensajeDe,
  reglaMotivoAnulacion,
} from '../utils/reglas';

/**
 * Detalle de un pago (HU-31) con su comprobante y la anulación (HU-32). Solo el Administrador ve la
 * acción Anular, y solo cuando el pago es el del último periodo del vehículo (D14); si no, se explica
 * por qué. Anular exige un motivo y una confirmación que nombra el pago (RNF-27). El pago nunca se
 * elimina: queda ANULADO con quién, cuándo y por qué.
 */
@Component({
  selector: 'app-pago-detalle',
  imports: [ReactiveFormsModule, RouterLink, Comprobante, Confirmacion],
  templateUrl: './pago-detalle.html',
  styleUrls: ['../estilos/gestion.css', './pago-detalle.css'],
})
export class PagoDetalleComponent {
  private readonly api = inject(PagosService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));
  readonly puedeAnular = computed(() => this.auth.tiene(PERMISOS.pagosAnular));
  readonly motivo = inject(FormBuilder).nonNullable.control('', reglaMotivoAnulacion);
  readonly motivoMinimo = MOTIVO_ANULACION_MINIMO;
  readonly motivoMaximo = MOTIVO_ANULACION_MAXIMO;
  readonly pago = signal<PagoDetalle | null>(null);
  readonly cargando = signal(true);
  readonly anulando = signal(false);
  /** Paso 1: escribir el motivo. Paso 2: confirmar (la confirmación nombra el pago). */
  readonly pidiendoMotivo = signal(false);
  readonly confirmando = signal(false);
  readonly error = signal('');
  readonly errorAccion = signal('');
  readonly exito = signal('');
  readonly pesos = formatoPesos;
  readonly fecha = fechaCorta;

  constructor() {
    this.cargar();
  }

  cargar(): void {
    if (!Number.isInteger(this.id) || this.id < 1) {
      this.cargando.set(false);
      this.error.set('El pago no existe. Vuelve a la consulta de pagos.');
      return;
    }
    this.cargando.set(true);
    this.api
      .detalle(this.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (pago) => {
          this.cargando.set(false);
          this.pago.set(pago);
        },
        error: (error: HttpErrorResponse) => {
          this.cargando.set(false);
          this.error.set(
            error.status === 404
              ? 'El pago no existe. Vuelve a la consulta de pagos.'
              : this.mensajeError(error),
          );
        },
      });
  }

  iniciarAnulacion(): void {
    this.motivo.reset('');
    this.pidiendoMotivo.set(true);
    this.confirmando.set(false);
    this.errorAccion.set('');
    this.exito.set('');
  }

  errorMotivo(): string {
    return this.motivo.touched ? mensajeDe(this.motivo.errors) : '';
  }

  largoMotivo(): number {
    return this.motivo.value.trim().length;
  }

  /** Con un motivo válido se pide la confirmación explícita. */
  continuar(): void {
    this.motivo.markAsTouched();
    if (this.motivo.invalid) return;
    this.confirmando.set(true);
  }

  cancelar(): void {
    if (this.anulando()) return;
    this.pidiendoMotivo.set(false);
    this.confirmando.set(false);
  }

  anular(): void {
    const pago = this.pago();
    if (!pago || this.anulando()) return;
    this.anulando.set(true);
    this.errorAccion.set('');
    this.api
      .anular(pago.id, this.motivo.value.trim())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (anulado) => {
          this.anulando.set(false);
          this.pidiendoMotivo.set(false);
          this.confirmando.set(false);
          this.pago.set(anulado);
          this.exito.set(
            `Pago ${anulado.comprobante} anulado. Su periodo ya no habilita la entrada del vehículo ${anulado.placa}.`,
          );
        },
        error: (error: HttpErrorResponse) => {
          this.anulando.set(false);
          this.confirmando.set(false);
          this.errorAccion.set(this.mensajeError(error));
          // Otro usuario pudo registrar un pago posterior o anularlo: se muestra el estado actual.
          if (error.status === 409) {
            this.pidiendoMotivo.set(false);
            this.recargar();
          }
        },
      });
  }

  imprimir(): void {
    window.print();
  }

  private recargar(): void {
    this.api
      .detalle(this.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (pago) => this.pago.set(pago), error: () => undefined });
  }

  /** RNF-15: siempre un mensaje en español; el detalle técnico nunca llega a la pantalla. */
  private mensajeError(error: HttpErrorResponse): string {
    const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (error.status === 404) return 'El pago ya no existe. Vuelve a la consulta de pagos.';
    if (error.status === 409) return detalle || 'El pago no se puede anular en su estado actual.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para esta operación.';
    if (error.status === 422)
      return `Revisa el motivo: debe tener de ${MOTIVO_ANULACION_MINIMO} a ${MOTIVO_ANULACION_MAXIMO} caracteres.`;
    return 'No se pudo conectar con el servicio. Comprueba la conexión y vuelve a intentarlo.';
  }
}
