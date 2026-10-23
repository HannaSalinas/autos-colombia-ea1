import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { Correccion, Novedad, TIPOS_NOVEDAD } from '../models/estancia';
import { EstanciaHistorial, FiltrosHistorial } from '../models/reporte';
import { EstanciasService } from '../services/estancias.service';
import { ReportesService } from '../services/reportes.service';
import { normalizarPlaca } from '../utils/placa';

/** 'desde' no puede ser posterior a 'hasta' (fechas AAAA-MM-DD se comparan como texto). */
const rangoValido: ValidatorFn = (group) => {
  const desde = group.get('desde')?.value;
  const hasta = group.get('hasta')?.value;
  return desde && hasta && desde > hasta ? { rango: true } : null;
};

/** Iteración 1, Fase 4: historial de estancias filtrable por placa y por días de Bogotá. */
@Component({
  selector: 'app-historial',
  imports: [ReactiveFormsModule],
  templateUrl: './historial.html',
  styleUrl: './historial.css',
})
export class Historial {
  private readonly api = inject(ReportesService);
  private readonly estancias = inject(EstanciasService);
  private readonly fb = inject(FormBuilder);
  private readonly destroy = inject(DestroyRef);

  readonly filtros = this.fb.nonNullable.group(
    { placa: '', desde: '', hasta: '' },
    { validators: rangoValido },
  );
  readonly items = signal<EstanciaHistorial[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 20;
  readonly loading = signal(false);
  readonly error = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));
  /** Filtros con los que se cargó la página actual (al paginar se reutilizan). */
  private aplicados: FiltrosHistorial = {};

  readonly detalleId = signal<number | null>(null);
  readonly detalle = signal<{ novedades: Novedad[]; correcciones: Correccion[] } | null>(null);
  readonly detalleError = signal('');

  constructor() {
    this.buscar();
  }

  buscar(): void {
    if (this.filtros.invalid) return;
    const raw = this.filtros.getRawValue();
    const placa = raw.placa.trim() ? normalizarPlaca(raw.placa) : '';
    this.filtros.controls.placa.setValue(placa);
    this.aplicados = { placa, desde: raw.desde, hasta: raw.hasta };
    this.cargar(0);
  }

  limpiar(): void {
    this.filtros.reset();
    this.buscar();
  }

  cargar(offset: number): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set('');
    this.cerrarDetalle();
    this.api
      .historial(this.aplicados, offset, this.limit)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.items.set(data.items);
          this.total.set(data.total);
          this.offset.set(offset);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.error.set(
            typeof error.error?.detail === 'string'
              ? error.error.detail
              : 'No se pudo cargar el historial. Comprueba la conexión y vuelve a buscar.',
          );
        },
      });
  }

  verDetalle(estancia: EstanciaHistorial): void {
    if (this.detalleId() === estancia.id) {
      this.cerrarDetalle();
      return;
    }
    this.detalleId.set(estancia.id);
    this.detalle.set(null);
    this.detalleError.set('');
    forkJoin({
      novedades: this.estancias.novedades(estancia.id),
      correcciones: this.estancias.correcciones(estancia.id),
    })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          if (this.detalleId() === estancia.id) this.detalle.set(data);
        },
        error: () => this.detalleError.set('No se pudo cargar el detalle de la estancia.'),
      });
  }

  cerrarDetalle(): void {
    this.detalleId.set(null);
    this.detalle.set(null);
    this.detalleError.set('');
  }

  etiqueta(tipo: string): string {
    return TIPOS_NOVEDAD.find((t) => t.valor === tipo)?.etiqueta ?? tipo;
  }

  fecha(value: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota',
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(value));
  }
}
