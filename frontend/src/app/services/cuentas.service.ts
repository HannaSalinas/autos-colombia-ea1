import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import {
  Cuenta,
  CuentaCrear,
  CuentaDetalle,
  CuentasPagina,
  FiltrosCuentas,
} from '../models/cuenta';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class CuentasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/cuentas`;

  listar(filtros: FiltrosCuentas, offset: number, limit: number) {
    let params = new HttpParams().set('offset', offset).set('limit', limit);
    const buscar = filtros.buscar?.trim();
    if (buscar) params = params.set('buscar', buscar);
    if (filtros.rol) params = params.set('rol', filtros.rol);
    if (filtros.estado) params = params.set('estado', filtros.estado);
    return this.http.get<CuentasPagina>(this.base, { params }).pipe(timeout(15000));
  }
  detalle(id: number) {
    return this.http.get<CuentaDetalle>(`${this.base}/${id}`).pipe(timeout(15000));
  }
  crear(data: CuentaCrear) {
    return this.http.post<Cuenta>(this.base, data).pipe(timeout(15000));
  }
  desactivar(id: number) {
    return this.http.post<Cuenta>(`${this.base}/${id}/desactivar`, null).pipe(timeout(15000));
  }
  reactivar(id: number) {
    return this.http.post<Cuenta>(`${this.base}/${id}/reactivar`, null).pipe(timeout(15000));
  }
}
