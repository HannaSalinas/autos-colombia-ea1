import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { EMPTY, Observable, expand, reduce, throwError, timeout } from 'rxjs';
import { Cliente, ClienteCrear, ClientesPagina } from '../models/cliente';
import { API_BASE_URL } from './api.service';

/** Consulta de clientes (ambos roles). Iteración 3 (D15): el Administrador también los registra. */
@Injectable({ providedIn: 'root' })
export class ClientesService {
  private readonly http = inject(HttpClient);
  private readonly clients = `${inject(API_BASE_URL)}/clientes`;

  list(offset: number, limit: number, buscar = '') {
    let params = new HttpParams().set('offset', offset).set('limit', limit);
    if (buscar.trim()) params = params.set('buscar', buscar.trim());
    return this.http.get<ClientesPagina>(this.clients, { params }).pipe(timeout(15000));
  }
  get(id: number) {
    return this.http.get<Cliente>(`${this.clients}/${id}`).pipe(timeout(15000));
  }
  create(data: ClienteCrear) {
    return this.http.post<Cliente>(this.clients, data).pipe(timeout(15000));
  }

  /** Recorre todas las páginas, como hace EstanciasService con celdas y operadores. */
  todos(): Observable<Cliente[]> {
    return this.list(0, 100).pipe(
      expand((page) => {
        const next = page.offset + page.items.length;
        if (next >= page.total) return EMPTY;
        if (!page.items.length)
          return throwError(() => new Error('Listado de clientes incompleto. Recarga la página.'));
        return this.list(next, 100);
      }),
      reduce((items, page) => [...items, ...page.items], [] as Cliente[]),
    );
  }
}
