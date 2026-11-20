import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../auth/auth.service';
import { CuentaSesion } from '../models/auth';
import { Tarifa, TarifaVigente } from '../models/tarifa';
import { textoDe } from '../utils/pruebas';
import { Tarifas } from './tarifas';

const ADMIN: CuentaSesion = {
  id: 1,
  nombre_usuario: 'admin',
  nombre: 'Sandra Patiño',
  rol: 'ADMINISTRADOR',
  permisos: ['tarifas:ver', 'tarifas:gestionar'],
};
const OPERADOR: CuentaSesion = { ...ADMIN, id: 2, rol: 'OPERADOR', permisos: ['tarifas:ver'] };

describe('Tarifas (HU-26, HU-27)', () => {
  let fixture: ComponentFixture<Tarifas>;
  let http: HttpTestingController;
  const auto: Tarifa = {
    id: 5,
    tipo_vehiculo: 'AUTOMOVIL',
    valor: 120000,
    vigente_desde: '2026-11-20T14:00:00Z',
    definida_por: 'Sandra Patiño (admin)',
  };
  const vigentes: TarifaVigente[] = [
    {
      tipo_vehiculo: 'MOTO',
      tarifa: { ...auto, id: 1, tipo_vehiculo: 'MOTO', valor: 60000, definida_por: null },
    },
    { tipo_vehiculo: 'AUTOMOVIL', tarifa: auto },
    { tipo_vehiculo: 'CAMIONETA', tarifa: null },
  ];
  const root = () => fixture.nativeElement as HTMLElement;
  const texto = () => textoDe(root());
  const boton = (etiqueta: string) =>
    [...root().querySelectorAll('button')].find((b) => b.textContent?.trim() === etiqueta);
  const escribir = (selector: string, valor: string) => {
    const el = root().querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    el.value = valor;
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
    fixture.detectChanges();
  };
  const montar = (cuenta: CuentaSesion) => {
    TestBed.inject(AuthService).cuenta.set(cuenta);
    fixture = TestBed.createComponent(Tarifas);
    fixture.detectChanges();
    http.expectOne('/tarifas').flush(vigentes);
    if (cuenta.rol === 'ADMINISTRADOR')
      http
        .expectOne('/tarifas/historial?offset=0&limit=10')
        .flush({ items: [auto], total: 1, offset: 0, limit: 10 });
    fixture.detectChanges();
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Tarifas],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('el Administrador ve las vigentes con formato $ y el historial con su autor (TA-01)', () => {
    montar(ADMIN);
    expect(texto()).toContain('MOTO $ 60.000 al mes');
    expect(texto()).toContain('AUTOMOVIL $ 120.000 al mes');
    expect(texto()).toContain('CAMIONETA Sin tarifa');
    expect(texto()).toContain('Historial de tarifas');
    expect(texto()).toContain('Sandra Patiño (admin)');
    expect(boton('Nueva tarifa')).toBeDefined();
  });

  it('el Operador ve las vigentes sin actualizar ni historial (TA-02)', () => {
    montar(OPERADOR);
    expect(texto()).toContain('AUTOMOVIL $ 120.000 al mes');
    expect(boton('Nueva tarifa')).toBeUndefined();
    expect(texto()).not.toContain('Historial de tarifas');
  });

  it('valida el valor con las mismas reglas del servidor sin enviar nada (TA-04)', () => {
    montar(ADMIN);
    boton('Nueva tarifa')!.click();
    fixture.detectChanges();
    escribir('#tipo-vehiculo', 'MOTO');
    for (const malo of ['999', '2000001', '1000.5', '120.000', '']) {
      escribir('#valor', malo);
      boton('Guardar tarifa')!.click();
      fixture.detectChanges();
      expect(texto()).toMatch(
        /La tarifa debe ser un valor entero|Escribe el valor mensual en pesos/,
      );
      expect(texto()).not.toContain('Confirmar nueva tarifa');
    }
    http.expectNone({ method: 'POST', url: '/tarifas' });
  });

  it('pide confirmación con el valor anterior y el nuevo, y crea una tarifa nueva (TA-03)', () => {
    montar(ADMIN);
    boton('Nueva tarifa')!.click();
    fixture.detectChanges();
    escribir('#tipo-vehiculo', 'AUTOMOVIL');
    expect(texto()).toContain('Tarifa actual $ 120.000');
    escribir('#valor', ' 2000000 ');
    boton('Guardar tarifa')!.click();
    fixture.detectChanges();
    expect(texto()).toContain(
      '¿Fijar la tarifa mensual de AUTOMOVIL de $ 120.000 a $ 2.000.000? Rige desde este momento para los pagos siguientes; los pagos ya registrados conservan su monto.',
    );
    boton('Sí, guardar la tarifa')!.click();
    const r = http.expectOne({ method: 'POST', url: '/tarifas' });
    expect(r.request.body).toEqual({ tipo_vehiculo: 'AUTOMOVIL', valor: 2000000 });
    r.flush({ ...auto, id: 6, valor: 2000000 });
    http.expectOne('/tarifas').flush(vigentes);
    http
      .expectOne('/tarifas/historial?offset=0&limit=10')
      .flush({ items: [auto], total: 1, offset: 0, limit: 10 });
    fixture.detectChanges();
    expect(texto()).toContain('Nueva tarifa de AUTOMOVIL: $ 2.000.000 al mes, vigente desde');
  });

  it('un 403 del servidor se muestra en español', () => {
    montar(ADMIN);
    boton('Nueva tarifa')!.click();
    fixture.detectChanges();
    escribir('#tipo-vehiculo', 'MOTO');
    escribir('#valor', '70000');
    boton('Guardar tarifa')!.click();
    fixture.detectChanges();
    boton('Sí, guardar la tarifa')!.click();
    http
      .expectOne({ method: 'POST', url: '/tarifas' })
      .flush({ detail: 'x' }, { status: 403, statusText: 'Forbidden' });
    fixture.detectChanges();
    expect(texto()).toContain('Tu cuenta no tiene permiso para gestionar tarifas.');
  });
});
