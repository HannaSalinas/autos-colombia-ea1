import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Historial } from './historial';

describe('Historial de estancias', () => {
  let fixture: ComponentFixture<Historial>;
  let c: Historial;
  let http: HttpTestingController;
  const estancia = {
    id: 7,
    placa: 'ABC123',
    tipo_vehiculo: 'AUTOMOVIL',
    celda: 'C04',
    entrada: '2026-10-22T13:00:00Z',
    salida: '2026-10-22T15:15:00Z',
    abierta: false,
    duracion_segundos: 8100,
    permanencia: '2 h 15 min',
    operador_entrada: 'Marta',
    operador_salida: 'Diego',
    novedades: 1,
    correcciones: 1,
  };
  const pagina = (items = [estancia], total = items.length, offset = 0) => ({
    items,
    total,
    offset,
    limit: 20,
  });

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Historial],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Historial);
    c = fixture.componentInstance;
    http.expectOne('/reportes/historial?offset=0&limit=20').flush(pagina());
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('carga todo el historial al abrir y muestra la permanencia', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(text).toContain('ABC123');
    expect(text).toContain('2 h 15 min');
    expect(text).toContain('1 nov. · 1 corr.');
  });

  it('filtra por placa normalizada y rango de fechas, y pagina con los mismos filtros', () => {
    c.filtros.setValue({ placa: ' abc-123 ', desde: '2026-10-20', hasta: '2026-10-22' });
    c.buscar();
    http
      .expectOne(
        '/reportes/historial?offset=0&limit=20&placa=ABC123&desde=2026-10-20&hasta=2026-10-22',
      )
      .flush(pagina([estancia], 25));
    expect(c.filtros.controls.placa.value).toBe('ABC123');
    c.cargar(20);
    http
      .expectOne(
        '/reportes/historial?offset=20&limit=20&placa=ABC123&desde=2026-10-20&hasta=2026-10-22',
      )
      .flush(pagina([estancia], 25, 20));
    expect(c.page()).toBe(2);
  });

  it('no busca si desde es posterior a hasta', () => {
    c.filtros.setValue({ placa: '', desde: '2026-10-23', hasta: '2026-10-22' });
    c.buscar();
    http.expectNone((r) => r.url.startsWith('/reportes/historial'));
    expect(c.filtros.errors?.['rango']).toBe(true);
  });

  it('muestra el detalle de novedades y correcciones de una estancia', () => {
    c.verDetalle(estancia);
    http.expectOne('/estancias/7/novedades').flush([
      {
        id: 1,
        estancia_id: 7,
        operador_id: 1,
        fecha: '2026-10-22T14:00:00Z',
        tipo: 'OBJETO_OLVIDADO',
        descripcion: 'Llaves',
      },
    ]);
    http.expectOne('/estancias/7/correcciones').flush([
      {
        id: 2,
        estancia_id: 7,
        celda_anterior: { id: 3, codigo: 'C03', tipo: 'CARRO' },
        celda_nueva: { id: 4, codigo: 'C04', tipo: 'CARRO' },
        operador_id: 1,
        fecha: '2026-10-22T13:10:00Z',
        motivo: 'Parqueó al lado',
      },
    ]);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(text).toContain('Objeto olvidado');
    expect(text).toContain('C03 → C04');
    c.verDetalle(estancia);
    expect(c.detalleId()).toBeNull();
  });

  it('muestra el mensaje del servidor si rechaza los filtros', () => {
    c.filtros.setValue({ placa: 'ABC123', desde: '', hasta: '' });
    c.buscar();
    http
      .expectOne('/reportes/historial?offset=0&limit=20&placa=ABC123')
      .flush({ detail: 'Mensaje del servidor' }, { status: 422, statusText: 'Unprocessable' });
    expect(c.error()).toBe('Mensaje del servidor');
  });
});
