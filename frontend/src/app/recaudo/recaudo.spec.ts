import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Recaudo } from '../models/pago';
import { hoyBogota } from '../utils/fechas';
import { textoDe } from '../utils/pruebas';
import { RecaudoComponent } from './recaudo';

describe('Recaudo (HU-33)', () => {
  let fixture: ComponentFixture<RecaudoComponent>;
  let http: HttpTestingController;
  const resumen: Recaudo = {
    desde: '2026-11-01',
    hasta: '2026-11-20',
    validos: { cantidad: 3, total: 440000 },
    por_metodo: [
      { metodo: 'EFECTIVO', cantidad: 1, total: 240000 },
      { metodo: 'TRANSFERENCIA', cantidad: 1, total: 60000 },
      { metodo: 'TARJETA', cantidad: 1, total: 140000 },
    ],
    por_tipo_vehiculo: [
      { tipo_vehiculo: 'MOTO', cantidad: 1, total: 60000 },
      { tipo_vehiculo: 'AUTOMOVIL', cantidad: 1, total: 240000 },
      { tipo_vehiculo: 'CAMIONETA', cantidad: 1, total: 140000 },
    ],
    anulados: { cantidad: 1, total: 120000 },
  };
  const root = () => fixture.nativeElement as HTMLElement;
  const texto = () => textoDe(root());
  const escribir = (selector: string, valor: string) => {
    const el = root().querySelector<HTMLInputElement>(selector)!;
    el.value = valor;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  };
  const consultar = () => {
    root()
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RecaudoComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(RecaudoComponent);
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('consulta el mes en curso y muestra totales por método, por tipo y anulados aparte (RE-01)', () => {
    const hoy = hoyBogota();
    const r = http.expectOne((req) => req.url === '/reportes/recaudo');
    expect(r.request.params.get('desde')).toBe(hoy.slice(0, 8) + '01');
    expect(r.request.params.get('hasta')).toBe(hoy);
    r.flush(resumen);
    fixture.detectChanges();
    expect(texto()).toContain('Del 01/11/2026 al 20/11/2026');
    expect(texto()).toContain('Total recaudado (pagos válidos) $ 440.000 3 pagos');
    expect(texto()).toContain('Pagos anulados (no suman) $ 120.000 1 pago');
    expect(texto()).toContain('Efectivo 1 $ 240.000');
    expect(texto()).toContain('Transferencia 1 $ 60.000');
    expect(texto()).toContain('CAMIONETA 1 $ 140.000');
  });

  it('un rango sin pagos muestra $ 0 sin error (RE-02)', () => {
    http
      .expectOne((req) => req.url === '/reportes/recaudo')
      .flush({
        ...resumen,
        validos: { cantidad: 0, total: 0 },
        anulados: { cantidad: 0, total: 0 },
        por_metodo: resumen.por_metodo.map((m) => ({ ...m, cantidad: 0, total: 0 })),
        por_tipo_vehiculo: resumen.por_tipo_vehiculo.map((t) => ({ ...t, cantidad: 0, total: 0 })),
      });
    fixture.detectChanges();
    expect(texto()).toContain('Total recaudado (pagos válidos) $ 0 0 pagos');
    expect(texto()).toContain('No hay pagos registrados en este rango.');
  });

  it('rechaza un rango invertido sin consultar (RE-03)', () => {
    http.expectOne((req) => req.url === '/reportes/recaudo').flush(resumen);
    escribir('#desde', '2026-11-20');
    escribir('#hasta', '2026-11-01');
    consultar();
    expect(texto()).toContain('La fecha inicial no puede ser posterior a la fecha final.');
    http.expectNone((req) => req.url === '/reportes/recaudo');
  });

  it('un 403 se muestra en español', () => {
    http
      .expectOne((req) => req.url === '/reportes/recaudo')
      .flush({ detail: 'x' }, { status: 403, statusText: 'Forbidden' });
    fixture.detectChanges();
    expect(texto()).toContain('Tu cuenta no tiene permiso para consultar el recaudo.');
  });
});
