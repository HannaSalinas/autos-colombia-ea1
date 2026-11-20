import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { PagoResumen } from '../models/pago';
import { ConsultaPagos } from './consulta-pagos';

describe('Pagos registrados (HU-31)', () => {
  let fixture: ComponentFixture<ConsultaPagos>;
  let http: HttpTestingController;
  const fila: PagoResumen = {
    id: 7,
    comprobante: 'RC-000007',
    fecha: '2026-11-20T15:00:00Z',
    placa: 'KLM45D',
    cliente_nombre: 'Laura Gómez',
    fecha_inicio: '2026-11-20',
    fecha_fin: '2026-12-19',
    meses: 1,
    monto: 60000,
    metodo: 'TRANSFERENCIA',
    estado: 'ANULADO',
    registrado_por: 'Marta Úsuga (marta.usuga)',
  };
  const root = () => fixture.nativeElement as HTMLElement;
  const texto = () => root().textContent?.replace(/\s+/g, ' ') ?? '';
  const escribir = (selector: string, valor: string) => {
    const el = root().querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    el.value = valor;
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  };
  const buscar = () => {
    root()
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConsultaPagos],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ConsultaPagos);
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('lista comprobante, fecha, placa, cliente, periodo, meses, monto, método, estado y responsable', () => {
    http
      .expectOne('/pagos?offset=0&limit=10')
      .flush({ items: [fila], total: 1, offset: 0, limit: 10 });
    fixture.detectChanges();
    for (const t of [
      'RC-000007',
      'KLM45D',
      'Laura Gómez',
      '20/11/2026 – 19/12/2026',
      '$ 60.000',
      'Transferencia',
      'Anulado',
      'Marta Úsuga (marta.usuga)',
    ])
      expect(texto()).toContain(t);
    expect(root().querySelector('a[href="/consultas/pagos/7"]')?.textContent?.trim()).toBe(
      'RC-000007',
    );
  });

  it('filtra por placa normalizada, fechas, método y estado; sin coincidencias lo indica', () => {
    http.expectOne('/pagos?offset=0&limit=10').flush({ items: [], total: 0, offset: 0, limit: 10 });
    fixture.detectChanges();
    expect(texto()).toContain('Todavía no hay pagos registrados.');
    escribir('#filtro-placa', ' klm-45d ');
    escribir('#filtro-desde', '2026-11-01');
    escribir('#filtro-hasta', '2026-11-30');
    escribir('#filtro-metodo', 'TRANSFERENCIA');
    escribir('#filtro-estado', 'VALIDO');
    buscar();
    const r = http.expectOne((req) => req.url === '/pagos');
    expect(r.request.params.get('placa')).toBe('KLM45D');
    expect(r.request.params.get('desde')).toBe('2026-11-01');
    expect(r.request.params.get('hasta')).toBe('2026-11-30');
    expect(r.request.params.get('metodo')).toBe('TRANSFERENCIA');
    expect(r.request.params.get('estado')).toBe('VALIDO');
    r.flush({ items: [], total: 0, offset: 0, limit: 10 });
    fixture.detectChanges();
    expect(texto()).toContain('No hay pagos que coincidan con los filtros.');
  });

  it('rechaza un rango con la fecha inicial posterior a la final sin consultar', () => {
    http.expectOne('/pagos?offset=0&limit=10').flush({ items: [], total: 0, offset: 0, limit: 10 });
    escribir('#filtro-desde', '2026-11-30');
    escribir('#filtro-hasta', '2026-11-01');
    buscar();
    expect(texto()).toContain('La fecha inicial no puede ser posterior a la fecha final.');
    http.expectNone((req) => req.url === '/pagos');
  });

  it('sin conexión muestra un mensaje en español', () => {
    http
      .expectOne('/pagos?offset=0&limit=10')
      .flush(null, { status: 0, statusText: 'Unknown Error' });
    fixture.detectChanges();
    expect(texto()).toContain('No se pudo conectar con el servicio.');
  });
});
