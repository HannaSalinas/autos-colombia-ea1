import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { EMPTY, Observable, expand, reduce, throwError, timeout } from 'rxjs';
import { Celda } from '../models/celda';
import { Operador } from '../models/operador';
import {
  Correccion,
  CorreccionCrear,
  EntradaCrear,
  EstadoVehiculo,
  Movimiento,
  Novedad,
  NovedadCrear,
  SalidaCrear,
} from '../models/estancia';
import { API_BASE_URL } from './api.service';
import { CeldasService } from './celdas.service';
import { OperadoresService } from './operadores.service';

interface Pagina<T> {
  items: T[];
  offset: number;
  limit: number;
  total: number;
}

@Injectable({ providedIn: 'root' })
export class EstanciasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/estancias`;
  private readonly cells = inject(CeldasService);
  private readonly operators = inject(OperadoresService);

  entrada(data: EntradaCrear) {
    return this.http.post<Movimiento>(`${this.base}/entrada`, data).pipe(timeout(15000));
  }
  salida(data: SalidaCrear) {
    return this.http.post<Movimiento>(`${this.base}/salida`, data).pipe(timeout(15000));
  }
  consultar(placa: string) {
    return this.http
      .get<EstadoVehiculo>(`${this.base}/vehiculo/${encodeURIComponent(placa)}`)
      .pipe(timeout(15000));
  }
  // Fase 3: corrección de celda y novedades de una estancia.
  celdasDisponibles(estanciaId: number) {
    return this.http
      .get<Celda[]>(`${this.base}/${estanciaId}/celdas-disponibles`)
      .pipe(timeout(15000));
  }
  corregirCelda(estanciaId: number, data: CorreccionCrear) {
    return this.http
      .post<Correccion>(`${this.base}/${estanciaId}/correccion-celda`, data)
      .pipe(timeout(15000));
  }
  correcciones(estanciaId: number) {
    return this.http
      .get<Correccion[]>(`${this.base}/${estanciaId}/correcciones`)
      .pipe(timeout(15000));
  }
  novedades(estanciaId: number) {
    return this.http.get<Novedad[]>(`${this.base}/${estanciaId}/novedades`).pipe(timeout(15000));
  }
  registrarNovedad(estanciaId: number, data: NovedadCrear) {
    return this.http
      .post<Novedad>(`${this.base}/${estanciaId}/novedades`, data)
      .pipe(timeout(15000));
  }
  celdas(): Observable<Celda[]> {
    return this.todas((offset) => this.cells.list(offset, 100));
  }
  operadores(): Observable<Operador[]> {
    return this.todas((offset) => this.operators.list(offset, 100));
  }

  private todas<T>(load: (offset: number) => Observable<Pagina<T>>): Observable<T[]> {
    return load(0).pipe(
      expand((page) => {
        const next = page.offset + page.items.length;
        if (next >= page.total) return EMPTY;
        if (!page.items.length)
          return throwError(() => new Error('Catálogo incompleto. Recarga las opciones.'));
        return load(next);
      }),
      reduce((items, page) => [...items, ...page.items], [] as T[]),
    );
  }
}
