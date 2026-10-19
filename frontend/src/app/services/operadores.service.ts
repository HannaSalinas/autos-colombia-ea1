import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { Operador, OperadorActualizar, OperadorCrear, OperadoresPagina } from '../models/operador';

import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class OperadoresService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly operators = `${this.base}/operadores`;

  list(offset: number, limit: number) {
    return this.http
      .get<OperadoresPagina>(this.operators, { params: { offset, limit } })
      .pipe(timeout(15000));
  }
  get(id: number) {
    return this.http.get<Operador>(`${this.operators}/${id}`).pipe(timeout(15000));
  }
  create(data: OperadorCrear) {
    return this.http.post<Operador>(this.operators, data).pipe(timeout(15000));
  }
  update(id: number, data: OperadorActualizar) {
    return this.http.patch<Operador>(`${this.operators}/${id}`, data).pipe(timeout(15000));
  }
  delete(id: number) {
    return this.http.delete<void>(`${this.operators}/${id}`).pipe(timeout(15000));
  }
}
