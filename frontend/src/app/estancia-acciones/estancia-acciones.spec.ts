import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { EstanciaAcciones } from './estancia-acciones';
import { Correccion } from '../models/estancia';

describe('Acciones sobre la estancia (corrección de celda y novedades)', () => {
  let fixture: ComponentFixture<EstanciaAcciones>;
  let c: EstanciaAcciones;
  let http: HttpTestingController;
  const c01 = { id: 1, codigo: 'C01', tipo: 'CARRO' };
  const c05 = { id: 5, codigo: 'C05', tipo: 'CARRO' };
  const novedad = {
    id: 9,
    estancia_id: 3,
    operador_id: 4,
    fecha: '2026-10-23T15:00:00Z',
    tipo: 'RAYON' as const,
    descripcion: 'Rayón en la puerta',
  };

  const iniciar = (operadorId: number | null = 4) => {
    fixture.componentRef.setInput('estanciaId', 3);
    fixture.componentRef.setInput('celdaActual', 'C01');
    fixture.componentRef.setInput('operadorId', operadorId);
    fixture.detectChanges();
    http.expectOne('/estancias/3/celdas-disponibles').flush([c05]);
    http.expectOne('/estancias/3/correcciones').flush([]);
    http.expectOne('/estancias/3/novedades').flush([novedad]);
    fixture.detectChanges();
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [EstanciaAcciones],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(EstanciaAcciones);
    c = fixture.componentInstance;
  });
  afterEach(() => http.verify());

  it('carga las celdas libres compatibles, las correcciones y las novedades', () => {
    iniciar();
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(c.disponibles()).toEqual([c05]);
    expect(text).toContain('Rayón en la puerta');
    expect(text).toContain('C01');
  });

  it('corrige la celda con motivo y avisa al padre', () => {
    iniciar();
    const emitidas: Correccion[] = [];
    c.corregida.subscribe((x) => emitidas.push(x));
    c.corregir();
    http.expectNone('/estancias/3/correccion-celda');
    expect(c.correccion.invalid).toBe(true);
    c.correccion.setValue({ celda_id: 5, motivo: '  Parqueó   en la C05 ' });
    c.corregir();
    c.corregir();
    const req = http.expectOne('/estancias/3/correccion-celda');
    expect(req.request.body).toEqual({ celda_id: 5, operador_id: 4, motivo: 'Parqueó en la C05' });
    const respuesta = {
      id: 1,
      estancia_id: 3,
      celda_anterior: c01,
      celda_nueva: c05,
      operador_id: 4,
      fecha: '2026-10-23T15:00:00Z',
      motivo: 'Parqueó en la C05',
    };
    req.flush(respuesta);
    expect(emitidas).toEqual([respuesta]);
  });

  it('muestra el rechazo del servidor y recarga las celdas libres', () => {
    iniciar();
    c.correccion.setValue({ celda_id: 5, motivo: 'Motivo' });
    c.corregir();
    http
      .expectOne('/estancias/3/correccion-celda')
      .flush({ detail: 'La celda C05 está ocupada.' }, { status: 409, statusText: 'Conflict' });
    expect(c.errorCorreccion()).toBe('La celda C05 está ocupada.');
    http.expectOne('/estancias/3/celdas-disponibles').flush([]);
    http.expectOne('/estancias/3/correcciones').flush([]);
    http.expectOne('/estancias/3/novedades').flush([novedad]);
    expect(c.disponibles()).toEqual([]);
  });

  it('exige elegir el operador en la consulta', () => {
    iniciar(null);
    c.correccion.setValue({ celda_id: 5, motivo: 'Motivo' });
    c.corregir();
    c.novedad.setValue({ tipo: 'GOLPE', descripcion: 'Golpe' });
    c.registrarNovedad();
    http.expectNone((r) => r.method === 'POST');
    expect(c.errorCorreccion()).toContain('operador');
    expect(c.errorNovedad()).toContain('operador');
  });

  it('registra una novedad y la agrega a la lista', () => {
    iniciar();
    c.novedad.setValue({ tipo: '', descripcion: '   ' });
    c.registrarNovedad();
    http.expectNone('/estancias/3/novedades');
    c.novedad.setValue({ tipo: 'OBJETO_OLVIDADO', descripcion: ' Celular  en la silla ' });
    c.registrarNovedad();
    const req = http.expectOne({ method: 'POST', url: '/estancias/3/novedades' });
    expect(req.request.body).toEqual({
      tipo: 'OBJETO_OLVIDADO',
      descripcion: 'Celular en la silla',
      operador_id: 4,
    });
    req.flush({ ...novedad, id: 10, tipo: 'OBJETO_OLVIDADO', descripcion: 'Celular en la silla' });
    expect(c.novedades().length).toBe(2);
    expect(c.exitoNovedad()).toContain('registrada');
    expect(c.etiqueta('OBJETO_OLVIDADO')).toBe('Objeto olvidado');
  });

  it('informa cuando la estancia ya se cerró', () => {
    iniciar();
    c.novedad.setValue({ tipo: 'GOLPE', descripcion: 'Golpe' });
    c.registrarNovedad();
    const detail = 'La estancia ya está cerrada: no se puede modificar.';
    http
      .expectOne({ method: 'POST', url: '/estancias/3/novedades' })
      .flush({ detail }, { status: 409, statusText: 'Conflict' });
    expect(c.errorNovedad()).toBe(detail);
  });
});
