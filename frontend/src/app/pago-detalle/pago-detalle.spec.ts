import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { AuthService } from '../auth/auth.service';
import { CuentaSesion } from '../models/auth';
import { textoDe } from '../utils/pruebas';
import { PagoDetalle } from '../models/pago';
import { PagoDetalleComponent } from './pago-detalle';

const ADMIN: CuentaSesion = {
  id: 1,
  nombre_usuario: 'admin',
  nombre: 'Sandra Patiño',
  rol: 'ADMINISTRADOR',
  permisos: ['pagos', 'pagos:anular'],
};
const OPERADOR: CuentaSesion = { ...ADMIN, id: 2, rol: 'OPERADOR', permisos: ['pagos'] };

describe('Detalle del pago y anulación (HU-31, HU-32)', () => {
  let fixture: ComponentFixture<PagoDetalleComponent>;
  let http: HttpTestingController;
  const pago: PagoDetalle = {
    id: 41,
    comprobante: 'RC-000041',
    fecha: '2026-11-20T15:00:00Z',
    placa: 'ABC123',
    cliente_nombre: 'Laura Gómez',
    fecha_inicio: '2026-12-01',
    fecha_fin: '2026-12-31',
    meses: 1,
    monto: 120000,
    metodo: 'EFECTIVO',
    estado: 'VALIDO',
    registrado_por: 'Marta Úsuga (marta.usuga)',
    vehiculo_id: 9,
    tipo_vehiculo: 'AUTOMOVIL',
    cliente_tipo_documento: 'CC',
    cliente_documento: '1001234567',
    valor_mensual: 120000,
    referencia: null,
    anulado_en: null,
    anulado_por: null,
    motivo_anulacion: null,
    anulable: true,
  };
  const root = () => fixture.nativeElement as HTMLElement;
  const texto = () => textoDe(root());
  const boton = (etiqueta: string) =>
    [...root().querySelectorAll('button')].find((b) => b.textContent?.trim() === etiqueta);
  const montar = (cuenta: CuentaSesion, respuesta: PagoDetalle = pago) => {
    TestBed.inject(AuthService).cuenta.set(cuenta);
    fixture = TestBed.createComponent(PagoDetalleComponent);
    fixture.detectChanges();
    http.expectOne('/pagos/41').flush(respuesta);
    fixture.detectChanges();
  };
  const escribirMotivo = (valor: string) => {
    const area = root().querySelector<HTMLTextAreaElement>('#motivo')!;
    area.value = valor;
    area.dispatchEvent(new Event('input', { bubbles: true }));
    fixture.detectChanges();
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PagoDetalleComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: '41' }) } },
        },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('muestra el comprobante completo (PA-12)', () => {
    montar(ADMIN);
    for (const t of [
      'Comprobante de pago',
      'RC-000041',
      'ABC123 · AUTOMOVIL',
      'Laura Gómez · CC 1001234567',
      'Del 01/12/2026 al 31/12/2026',
      'Total pagado $ 120.000',
      'Efectivo',
      'Válido',
    ])
      expect(texto()).toContain(t);
  });

  it('el Administrador anula el último pago con motivo y confirmación que nombra el pago (AN-01, AN-02)', () => {
    montar(ADMIN);
    boton('Anular pago')!.click();
    fixture.detectChanges();
    escribirMotivo('a'.repeat(9));
    boton('Continuar')!.click();
    fixture.detectChanges();
    expect(texto()).toContain('El motivo debe tener de 10 a 200 caracteres.');
    expect(texto()).not.toContain('Confirmar anulación');
    escribirMotivo('  Cobro duplicado por error  ');
    expect(texto()).toContain('25/200'); // sin contar los espacios exteriores
    boton('Continuar')!.click();
    fixture.detectChanges();
    expect(texto()).toContain(
      '¿Anular el pago RC-000041 de ABC123 por $ 120.000 (del 01/12/2026 al 31/12/2026)? Esta acción no se puede deshacer.',
    );
    boton('Sí, anular el pago')!.click();
    const r = http.expectOne({ method: 'POST', url: '/pagos/41/anular' });
    expect(r.request.body).toEqual({ motivo: 'Cobro duplicado por error' });
    r.flush({
      ...pago,
      estado: 'ANULADO',
      anulable: false,
      anulado_en: '2026-11-20T16:00:00Z',
      anulado_por: 'Sandra Patiño (admin)',
      motivo_anulacion: 'Cobro duplicado por error',
    });
    fixture.detectChanges();
    expect(texto()).toContain(
      'Pago RC-000041 anulado. Su periodo ya no habilita la entrada del vehículo ABC123.',
    );
    expect(texto()).toContain('PAGO ANULADO');
    expect(texto()).toContain('Anulado por Sandra Patiño (admin)');
    expect(texto()).toContain('Motivo: Cobro duplicado por error');
    expect(boton('Anular pago')).toBeUndefined();
  });

  it('cancelar no anula', () => {
    montar(ADMIN);
    boton('Anular pago')!.click();
    fixture.detectChanges();
    boton('Cancelar')!.click();
    fixture.detectChanges();
    expect(root().querySelector('#motivo')).toBeNull();
    http.expectNone({ method: 'POST', url: '/pagos/41/anular' });
  });

  it('si no es el último periodo no ofrece anular y explica por qué (AN-03)', () => {
    montar(ADMIN, { ...pago, anulable: false });
    expect(boton('Anular pago')).toBeUndefined();
    expect(texto()).toContain(
      'Este pago no se puede anular: solo se anula el pago del último periodo del vehículo, y ABC123 tiene un periodo posterior.',
    );
  });

  it('el Operador no ve la acción de anular (AN-05)', () => {
    montar(OPERADOR);
    expect(boton('Anular pago')).toBeUndefined();
    expect(texto()).not.toContain('no se puede anular');
  });

  it('un 409 del servidor se muestra y se recarga el pago', () => {
    montar(ADMIN);
    boton('Anular pago')!.click();
    fixture.detectChanges();
    escribirMotivo('Error al digitar la placa');
    boton('Continuar')!.click();
    fixture.detectChanges();
    boton('Sí, anular el pago')!.click();
    const detalle = 'Solo se puede anular el pago del último periodo del vehículo.';
    http
      .expectOne({ method: 'POST', url: '/pagos/41/anular' })
      .flush({ detail: detalle }, { status: 409, statusText: 'Conflict' });
    http.expectOne('/pagos/41').flush({ ...pago, anulable: false });
    fixture.detectChanges();
    expect(texto()).toContain(detalle);
    expect(boton('Anular pago')).toBeUndefined();
  });

  it('pago inexistente: mensaje claro', () => {
    TestBed.inject(AuthService).cuenta.set(ADMIN);
    fixture = TestBed.createComponent(PagoDetalleComponent);
    fixture.detectChanges();
    http
      .expectOne('/pagos/41')
      .flush({ detail: 'Pago no encontrado.' }, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();
    expect(texto()).toContain('El pago no existe. Vuelve a la consulta de pagos.');
  });
});
