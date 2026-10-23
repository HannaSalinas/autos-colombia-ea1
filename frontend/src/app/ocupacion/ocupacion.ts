import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Ocupacion as Reporte } from '../models/reporte';
import { ReportesService } from '../services/reportes.service';

/** Iteración 1, Fase 4: vehículos dentro y celdas disponibles por tipo. */
@Component({
  selector: 'app-ocupacion',
  templateUrl: './ocupacion.html',
  styleUrl: './ocupacion.css',
})
export class Ocupacion {
  private readonly api = inject(ReportesService);
  private readonly destroy = inject(DestroyRef);
  readonly reporte = signal<Reporte | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');

  constructor() {
    this.cargar();
  }

  cargar(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set('');
    this.api
      .ocupacion()
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.reporte.set(data);
        },
        error: () => {
          this.loading.set(false);
          this.error.set('No se pudo cargar el reporte. Comprueba la conexión y actualiza.');
        },
      });
  }

  nombreTipo(tipo: string): string {
    return tipo === 'MOTO' ? 'Motos' : 'Carros';
  }

  /** Porcentaje ocupado, para la barra de cada tipo de celda. */
  porcentaje(ocupadas: number, total: number): number {
    return total ? Math.round((ocupadas / total) * 100) : 0;
  }

  hora(value: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota',
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(value));
  }
}
