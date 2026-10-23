import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { FiltrosHistorial, HistorialPagina, Ocupacion } from '../models/reporte';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class ReportesService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/reportes`;

  ocupacion() {
    return this.http.get<Ocupacion>(`${this.base}/ocupacion`).pipe(timeout(15000));
  }
  historial(filtros: FiltrosHistorial, offset: number, limit: number) {
    // Solo se envían los filtros con valor.
    const params: Record<string, string | number> = { offset, limit };
    for (const [clave, valor] of Object.entries(filtros)) if (valor) params[clave] = valor;
    return this.http
      .get<HistorialPagina>(`${this.base}/historial`, { params })
      .pipe(timeout(15000));
  }
}
