import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  ESTADOS_PAGO,
  EstadoPago,
  FiltrosPagos,
  METODOS_PAGO,
  MetodoPago,
  PagoResumen,
  etiquetaMetodo,
} from '../models/pago';
import { PagosService } from '../services/pagos.service';
import { formatoPesos } from '../utils/dinero';
import { fechaCorta, fechaHora } from '../utils/fechas';
import { normalizarPlaca } from '../utils/placa';

/**
 * Consultar pagos (HU-31). Ambos roles. Filtros por placa, rango de fechas del pago (días de
 * Bogotá), método y estado. Cada fila lleva al detalle, que muestra el comprobante.
 */
@Component({
  selector: 'app-consulta-pagos',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './consulta-pagos.html',
  styleUrls: ['../estilos/gestion.css', './consulta-pagos.css'],
})
export class ConsultaPagos {
  private readonly api = inject(PagosService);
  private readonly destroyRef = inject(DestroyRef);
  readonly filtros = inject(FormBuilder).nonNullable.group({
    placa: [''],
    desde: [''],
    hasta: [''],
    metodo: [''],
    estado: [''],
  });
  readonly metodos = METODOS_PAGO;
  readonly estadosPago = Object.entries(ESTADOS_PAGO) as [EstadoPago, string][];
  readonly items = signal<PagoResumen[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly listError = signal('');
  readonly filtroError = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));
  readonly pesos = formatoPesos;
  readonly fecha = fechaCorta;
  readonly fechaHora = fechaHora;
  readonly metodo = etiquetaMetodo;
  readonly estados = ESTADOS_PAGO;
  private aplicados: FiltrosPagos = {};

  constructor() {
    this.load(0);
  }

  load(offset = this.offset()): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .listar(offset, this.limit, this.aplicados)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.items.set(data.items);
          this.total.set(data.total);
          this.offset.set(offset);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.listError.set(this.mensajeError(error));
        },
      });
  }

  buscar(): void {
    const valor = this.filtros.getRawValue();
    this.filtroError.set('');
    // Misma regla que el servidor (422): la fecha inicial no puede ser posterior a la final.
    if (valor.desde && valor.hasta && valor.desde > valor.hasta) {
      this.filtroError.set('La fecha inicial no puede ser posterior a la fecha final.');
      return;
    }
    const placa = normalizarPlaca(valor.placa);
    this.filtros.controls.placa.setValue(placa);
    this.aplicados = {
      placa,
      desde: valor.desde,
      hasta: valor.hasta,
      metodo: valor.metodo as MetodoPago | '',
      estado: valor.estado as EstadoPago | '',
    };
    this.load(0);
  }

  limpiar(): void {
    this.filtros.reset();
    this.buscar();
  }

  hayFiltros(): boolean {
    return Object.values(this.aplicados).some((v) => !!v);
  }

  /** RNF-15: siempre un mensaje en español; el detalle técnico nunca llega a la pantalla. */
  private mensajeError(error: HttpErrorResponse): string {
    const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (error.status === 422)
      return detalle || 'Revisa los filtros: hay valores que no cumplen las validaciones.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para consultar pagos.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado.';
  }
}
