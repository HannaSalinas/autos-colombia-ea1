import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { Tarifa, TarifaCrear, TarifasPagina, TarifaVigente } from '../models/tarifa';
import { API_BASE_URL } from './api.service';

/** Iteración 3: tarifas. No hay editar ni eliminar: cada cambio crea una tarifa nueva (D12). */
@Injectable({ providedIn: 'root' })
export class TarifasService {
  private readonly http = inject(HttpClient);
  private readonly tarifas = `${inject(API_BASE_URL)}/tarifas`;

  vigentes() {
    return this.http.get<TarifaVigente[]>(this.tarifas).pipe(timeout(15000));
  }
  historial(offset: number, limit: number, tipo = '') {
    let params = new HttpParams().set('offset', offset).set('limit', limit);
    if (tipo) params = params.set('tipo', tipo);
    return this.http
      .get<TarifasPagina>(`${this.tarifas}/historial`, { params })
      .pipe(timeout(15000));
  }
  crear(data: TarifaCrear) {
    return this.http.post<Tarifa>(this.tarifas, data).pipe(timeout(15000));
  }
}
