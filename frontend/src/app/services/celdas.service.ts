import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import {
  CeldaActualizar,
  CeldaCrear,
  CeldaDetalle,
  CeldaGestion,
  CeldasPagina,
  FiltrosCeldas,
} from '../models/celda';

import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class CeldasService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly cells = `${this.base}/celdas`;

  list(offset: number, limit: number, filtros: FiltrosCeldas = {}) {
    let params = new HttpParams().set('offset', offset).set('limit', limit);
    const buscar = filtros.buscar?.trim();
    if (buscar) params = params.set('buscar', buscar);
    if (filtros.tipo) params = params.set('tipo', filtros.tipo);
    if (filtros.estado) params = params.set('estado', filtros.estado);
    return this.http.get<CeldasPagina>(this.cells, { params }).pipe(timeout(15000));
  }
  get(id: number) {
    return this.http.get<CeldaDetalle>(`${this.cells}/${id}`).pipe(timeout(15000));
  }
  create(data: CeldaCrear) {
    return this.http.post<CeldaGestion>(this.cells, data).pipe(timeout(15000));
  }
  update(id: number, data: CeldaActualizar) {
    return this.http.patch<CeldaGestion>(`${this.cells}/${id}`, data).pipe(timeout(15000));
  }
  // Iteración 2: las celdas no se eliminan (D4); se inhabilitan y se rehabilitan.
  inhabilitar(id: number) {
    return this.http
      .post<CeldaGestion>(`${this.cells}/${id}/inhabilitar`, null)
      .pipe(timeout(15000));
  }
  rehabilitar(id: number) {
    return this.http
      .post<CeldaGestion>(`${this.cells}/${id}/rehabilitar`, null)
      .pipe(timeout(15000));
  }
}
