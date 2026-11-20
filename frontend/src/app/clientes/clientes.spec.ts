import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from '../auth/auth.service';
import { CuentaSesion } from '../models/auth';
import { Cliente } from '../models/cliente';
import { textoDe } from '../utils/pruebas';
import { Clientes } from './clientes';

const ADMIN: CuentaSesion = {
  id: 1,
  nombre_usuario: 'admin',
  nombre: 'Sandra Patiño',
  rol: 'ADMINISTRADOR',
  permisos: ['vehiculos:ver', 'clientes:gestionar', 'pagos'],
};
const OPERADOR: CuentaSesion = {
  ...ADMIN,
  id: 2,
  rol: 'OPERADOR',
  permisos: ['vehiculos:ver', 'pagos'],
};

describe('Clientes (HU-28)', () => {
  let fixture: ComponentFixture<Clientes>;
  let http: HttpTestingController;
  const laura: Cliente = {
    id: 1,
    tipo_documento: 'CC',
    documento: '1001234567',
    nombre: 'Laura Gómez',
    telefono: '3001112233',
    correo: 'laura.gomez@example.com',
    registrado_en: null,
    registrado_por: null,
    vehiculos: [
      { id: 1, placa: 'ABC123', tipo: 'AUTOMOVIL' },
      { id: 2, placa: 'KLM45D', tipo: 'MOTO' },
    ],
  };
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
    fixture = TestBed.createComponent(Clientes);
    fixture.detectChanges();
    http
      .expectOne('/clientes?offset=0&limit=10')
      .flush({ items: [laura], total: 1, offset: 0, limit: 10 });
    fixture.detectChanges();
  };
  const llenar = () => {
    escribir('#documento', ' t1020304050 ');
    escribir('#nombre', 'Ana Restrepo');
    escribir('#telefono', '3001234567');
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Clientes],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('lista clientes con documento y vehículos; busca por nombre o documento (CL-05)', () => {
    montar(ADMIN);
    expect(texto()).toContain('CC 1001234567 Laura Gómez 3001112233');
    expect(texto()).toContain('ABC123');
    expect(texto()).toContain('KLM45D');
    escribir('#buscar-cliente', ' gómez ');
    root()
      .querySelector('.buscar-cliente')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    const r = http.expectOne((req) => req.url === '/clientes');
    expect(r.request.params.get('buscar')).toBe('gómez');
    r.flush({ items: [], total: 0, offset: 0, limit: 10 });
    fixture.detectChanges();
    expect(texto()).toContain('No hay clientes que coincidan con la búsqueda.');
  });

  it('el detalle muestra quién lo registró y sus vehículos', () => {
    montar(ADMIN);
    boton('Detalle')!.click();
    http.expectOne('/clientes/1').flush({
      ...laura,
      registrado_en: '2026-11-20T14:00:00Z',
      registrado_por: 'Sandra Patiño (admin)',
    });
    fixture.detectChanges();
    expect(texto()).toContain('Detalle de Laura Gómez');
    expect(texto()).toContain('Sandra Patiño (admin)');
    expect(texto()).toContain('ABC123 · AUTOMOVIL');
  });

  it('el Administrador registra con el documento normalizado (CL-01)', () => {
    montar(ADMIN);
    boton('Registrar cliente')!.click();
    fixture.detectChanges();
    llenar();
    boton('Guardar cliente')!.click();
    const r = http.expectOne({ method: 'POST', url: '/clientes' });
    expect(r.request.body).toEqual({
      tipo_documento: 'CC',
      documento: 'T1020304050',
      nombre: 'Ana Restrepo',
      telefono: '3001234567',
      correo: null,
    });
    r.flush({ ...laura, id: 9, documento: 'T1020304050', nombre: 'Ana Restrepo', vehiculos: [] });
    http
      .expectOne((req) => req.url === '/clientes' && req.params.get('buscar') === 'T1020304050')
      .flush({ items: [], total: 0, offset: 0, limit: 10 });
    fixture.detectChanges();
    expect(texto()).toContain('Cliente Ana Restrepo registrado (CC T1020304050).');
  });

  it('rechaza los valores fuera de límite sin enviar nada (CL-02)', () => {
    montar(ADMIN);
    boton('Registrar cliente')!.click();
    fixture.detectChanges();
    escribir('#documento', '1234');
    escribir('#nombre', 'Al');
    escribir('#telefono', '300111223');
    escribir('#correo', 'ana@');
    boton('Guardar cliente')!.click();
    fixture.detectChanges();
    expect(texto()).toContain('El número de documento debe tener de 5 a 15 caracteres');
    expect(texto()).toContain('El nombre completo debe tener de 3 a 80 caracteres.');
    expect(texto()).toContain(
      'El teléfono debe tener 10 dígitos, sin espacios ni otros caracteres.',
    );
    expect(texto()).toContain('El correo no tiene un formato válido (ej. ana@correo.com).');
    http.expectNone({ method: 'POST', url: '/clientes' });
  });

  it('documento repetido: el mensaje del servidor queda en el campo (CL-03)', () => {
    montar(ADMIN);
    boton('Registrar cliente')!.click();
    fixture.detectChanges();
    llenar();
    boton('Guardar cliente')!.click();
    const detalle = 'Ya existe un cliente con el documento CC T1020304050.';
    http
      .expectOne({ method: 'POST', url: '/clientes' })
      .flush({ detail: detalle }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(root().querySelector('#documento-error')?.textContent).toContain(detalle);
  });

  it('el Operador busca pero no ve la acción de registrar (CL-06)', () => {
    montar(OPERADOR);
    expect(texto()).toContain('Laura Gómez');
    expect(boton('Registrar cliente')).toBeUndefined();
  });
});
