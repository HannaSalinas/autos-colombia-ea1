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

  const iniciar = () => {
    fixture.componentRef.setInput('estanciaId', 3);
    fixture.componentRef.setInput('celdaActual', 'C01');
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
    expect(req.request.body).toEqual({ celda_id: 5, motivo: 'Parqueó en la C05' });
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

  // Iteración 2: antes exigía elegir el operador en la consulta. Ya no hay selector: el
  // responsable lo pone el servidor con la sesión, así que no se envía operador_id.
  it('no pide operador: corrige y registra la novedad sin enviar operador_id', () => {
    iniciar();
    c.correccion.setValue({ celda_id: 5, motivo: 'Motivo' });
    c.corregir();
    const correccion = http.expectOne('/estancias/3/correccion-celda');
    expect(correccion.request.body).toEqual({ celda_id: 5, motivo: 'Motivo' });
    expect(c.errorCorreccion()).toBe('');
    correccion.flush(
      { detail: 'La celda C05 está ocupada.' },
      { status: 409, statusText: 'Conflict' },
    );
    http.expectOne('/estancias/3/celdas-disponibles').flush([c05]);
    http.expectOne('/estancias/3/correcciones').flush([]);
    http.expectOne('/estancias/3/novedades').flush([novedad]);
    c.novedad.setValue({ tipo: 'GOLPE', descripcion: 'Golpe' });
    c.registrarNovedad();
    const nueva = http.expectOne({ method: 'POST', url: '/estancias/3/novedades' });
    expect(nueva.request.body).toEqual({ tipo: 'GOLPE', descripcion: 'Golpe' });
    expect(c.errorNovedad()).toBe('');
    nueva.flush({ ...novedad, id: 11, tipo: 'GOLPE', descripcion: 'Golpe' });
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
    });
    req.flush({ ...novedad, id: 10, tipo: 'OBJETO_OLVIDADO', descripcion: 'Celular en la silla' });
    expect(c.novedades().length).toBe(2);
    expect(c.exitoNovedad()).toContain('registrada');
    expect(c.etiqueta('OBJETO_OLVIDADO')).toBe('Objeto olvidado');
  });

  // Un 403 es falta de permiso, no un problema de conexión: se dice con el mismo texto que usa
  // Control de acceso. Antes caía en "No se pudo conectar con el servicio".
  it('ante un 403 muestra el mensaje de permiso al corregir la celda y al registrar la novedad', () => {
    iniciar();
    const permiso = 'Tu cuenta no tiene permiso para esta operación.';
    const sinPermiso = { status: 403, statusText: 'Forbidden' };
    c.correccion.setValue({ celda_id: 5, motivo: 'Motivo' });
    c.corregir();
    http
      .expectOne('/estancias/3/correccion-celda')
      .flush({ detail: 'No tienes permiso para esta operación.' }, sinPermiso);
    expect(c.errorCorreccion()).toBe(permiso);
    c.novedad.setValue({ tipo: 'GOLPE', descripcion: 'Golpe' });
    c.registrarNovedad();
    http
      .expectOne({ method: 'POST', url: '/estancias/3/novedades' })
      .flush({ detail: 'No tienes permiso para esta operación.' }, sinPermiso);
    expect(c.errorNovedad()).toBe(permiso);
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
