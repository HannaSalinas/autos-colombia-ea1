import { HttpClient } from '@angular/common/http';
import { inject, Injectable, InjectionToken } from '@angular/core';
import { timeout } from 'rxjs';
import { Vehiculo, VehiculoActualizar, VehiculoCrear, VehiculosPagina } from '../models/vehiculo';

// Mismo origen: el proxy de desarrollo define el destino real del backend.
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', { factory: () => '' });

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly vehicles = `${this.base}/vehiculos`;

  health() {
    return this.http.get<{ status?: unknown } | null>(`${this.base}/health`);
  }
  list(offset: number, limit: number) {
    return this.http
      .get<VehiculosPagina>(this.vehicles, { params: { offset, limit } })
      .pipe(timeout(15000));
  }
  get(id: number) {
    return this.http.get<Vehiculo>(`${this.vehicles}/${id}`).pipe(timeout(15000));
  }
  create(data: VehiculoCrear) {
    return this.http.post<Vehiculo>(this.vehicles, data).pipe(timeout(15000));
  }
  update(id: number, data: VehiculoActualizar) {
    return this.http.patch<Vehiculo>(`${this.vehicles}/${id}`, data).pipe(timeout(15000));
  }
  delete(id: number) {
    return this.http.delete<void>(`${this.vehicles}/${id}`).pipe(timeout(15000));
  }
}
