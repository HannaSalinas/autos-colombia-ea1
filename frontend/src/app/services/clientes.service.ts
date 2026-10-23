import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { EMPTY, Observable, expand, reduce, throwError, timeout } from 'rxjs';
import { Cliente, ClientesPagina } from '../models/cliente';
import { API_BASE_URL } from './api.service';

/** Solo lectura: la gestión de clientes llega en la Iteración 2. */
@Injectable({ providedIn: 'root' })
export class ClientesService {
  private readonly http = inject(HttpClient);
  private readonly clients = `${inject(API_BASE_URL)}/clientes`;

  list(offset: number, limit: number) {
    return this.http
      .get<ClientesPagina>(this.clients, { params: { offset, limit } })
      .pipe(timeout(15000));
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
