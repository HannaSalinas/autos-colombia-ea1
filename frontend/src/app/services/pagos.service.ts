import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import {
  Cotizacion,
  EstadoMensualidadRespuesta,
  FiltrosPagos,
  PagoCrear,
  PagoDetalle,
  PagosPagina,
} from '../models/pago';
import { API_BASE_URL } from './api.service';

/** Iteración 3: pagos de mensualidad (RF-35 a RF-38). */
@Injectable({ providedIn: 'root' })
export class PagosService {
  private readonly http = inject(HttpClient);
  private readonly pagos = `${inject(API_BASE_URL)}/pagos`;

  estado(placa: string) {
    return this.http
      .get<EstadoMensualidadRespuesta>(`${this.pagos}/estado/${encodeURIComponent(placa)}`)
      .pipe(timeout(15000));
  }
  /** El resumen que se confirma antes de registrar (RNF-27). No guarda nada. */
  cotizacion(placa: string, meses: number) {
    return this.http
      .get<Cotizacion>(`${this.pagos}/cotizacion`, { params: { placa, meses } })
      .pipe(timeout(15000));
  }
  registrar(data: PagoCrear) {
    return this.http.post<PagoDetalle>(this.pagos, data).pipe(timeout(15000));
  }
  listar(offset: number, limit: number, filtros: FiltrosPagos = {}) {
    let params = new HttpParams().set('offset', offset).set('limit', limit);
    const placa = filtros.placa?.trim();
    if (placa) params = params.set('placa', placa);
    if (filtros.desde) params = params.set('desde', filtros.desde);
    if (filtros.hasta) params = params.set('hasta', filtros.hasta);
    if (filtros.metodo) params = params.set('metodo', filtros.metodo);
    if (filtros.estado) params = params.set('estado', filtros.estado);
    return this.http.get<PagosPagina>(this.pagos, { params }).pipe(timeout(15000));
  }
  detalle(id: number) {
    return this.http.get<PagoDetalle>(`${this.pagos}/${id}`).pipe(timeout(15000));
  }
  anular(id: number, motivo: string) {
    return this.http
      .post<PagoDetalle>(`${this.pagos}/${id}/anular`, { motivo })
      .pipe(timeout(15000));
  }
}
