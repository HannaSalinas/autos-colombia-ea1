import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Recaudo, etiquetaMetodo } from '../models/pago';
import { ReportesService } from '../services/reportes.service';
import { formatoPesos } from '../utils/dinero';
import { fechaCorta, hoyBogota } from '../utils/fechas';

/**
 * Resumen de recaudo (HU-33, solo Administrador). Para un rango de días de Bogotá: total de los
 * pagos válidos por método y por tipo de vehículo, y los anulados aparte. Ambos se cuentan por la
 * fecha del pago (RF-39). Por defecto, el mes en curso hasta hoy.
 */
@Component({
  selector: 'app-recaudo',
  imports: [ReactiveFormsModule],
  templateUrl: './recaudo.html',
  styleUrls: ['../estilos/gestion.css', './recaudo.css'],
})
export class RecaudoComponent {
  private readonly api = inject(ReportesService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly hoy = hoyBogota();
  readonly rango = inject(FormBuilder).nonNullable.group({
    desde: [this.hoy.slice(0, 8) + '01'],
    hasta: [this.hoy],
  });
  readonly resumen = signal<Recaudo | null>(null);
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly pesos = formatoPesos;
  readonly fecha = fechaCorta;
  readonly metodo = etiquetaMetodo;

  constructor() {
    this.consultar();
  }

  consultar(): void {
    if (this.cargando()) return;
    const { desde, hasta } = this.rango.getRawValue();
    this.error.set('');
    if (!desde || !hasta) {
      this.error.set('Indica la fecha inicial y la fecha final.');
      return;
    }
    // Misma regla que el servidor (422).
    if (desde > hasta) {
      this.resumen.set(null);
      this.error.set('La fecha inicial no puede ser posterior a la fecha final.');
      return;
    }
    this.cargando.set(true);
    this.api
      .recaudo(desde, hasta)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resumen) => {
          this.cargando.set(false);
          this.resumen.set(resumen);
        },
        error: (error: HttpErrorResponse) => {
          this.cargando.set(false);
          this.resumen.set(null);
          this.error.set(this.mensajeError(error));
        },
      });
  }

  /** RNF-15: siempre un mensaje en español; el detalle técnico nunca llega a la pantalla. */
  private mensajeError(error: HttpErrorResponse): string {
    const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (error.status === 422) return detalle || 'Revisa las fechas del rango.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para consultar el recaudo.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y vuelve a consultar.';
  }
}
