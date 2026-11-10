import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../auth/auth.service';
import { CeldaGestion } from '../models/celda';
import { Celdas } from './celdas';

describe('Gestión de celdas', () => {
  let fixture: ComponentFixture<Celdas>;
  let http: HttpTestingController;
  // Iteración 2: código con formato C01–C99 / M01–M99, ubicación, estado e historial.
  const cell: CeldaGestion = {
    id: 1,
    codigo: 'C71',
    tipo: 'CARRO',
    ubicacion: null,
    habilitada: true,
    estado: 'LIBRE',
    placa: null,
    tiene_historial: false,
  };
  const ocupada: CeldaGestion = {
    ...cell,
    id: 2,
    codigo: 'C01',
    estado: 'OCUPADA',
    placa: 'ABC123',
    tiene_historial: true,
  };
  const conHistorial: CeldaGestion = { ...cell, id: 3, codigo: 'C02', tiene_historial: true };
  const inhabilitada: CeldaGestion = {
    ...cell,
    id: 4,
    codigo: 'M10',
    tipo: 'MOTO',
    habilitada: false,
    estado: 'INHABILITADA',
  };
  const listado = (items: CeldaGestion[] = [cell], url = '/celdas?offset=0&limit=10') => {
    http.expectOne(url).flush({ items, total: items.length, offset: 0, limit: 10 });
    fixture.detectChanges();
  };
  const texto = () => (fixture.nativeElement as HTMLElement).textContent ?? '';
  const boton = (etiqueta: string) =>
    [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (b) => b.getAttribute('aria-label') === etiqueta || b.textContent?.trim() === etiqueta,
    );

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Celdas],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    // Iteración 2: la gestión es del Administrador.
    TestBed.inject(AuthService).cuenta.set({
      id: 1,
      nombre_usuario: 'admin',
      nombre: 'Sandra Patiño',
      rol: 'ADMINISTRADOR',
      permisos: ['celdas:gestionar', 'celdas:ver'],
    });
    fixture = TestBed.createComponent(Celdas);
    fixture.detectChanges();
    listado();
  });
  afterEach(() => http.verify());

  it('crea desde el formulario HTML con código normalizado y tipo MOTO o CARRO', () => {
    fixture.componentInstance.newCell();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const escribir = (id: string, valor: string) => {
      const input = root.querySelector<HTMLInputElement>(`#${id}`)!;
      input.value = valor;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    };
    escribir('codigo', ' m11 ');
    escribir('ubicacion', '  Sótano 1 ');
    const select = root.querySelector<HTMLSelectElement>('#tipo')!;
    select.value = 'MOTO';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.componentInstance.save();
    const request = http.expectOne({ method: 'POST', url: '/celdas' });
    expect(request.request.body).toEqual({ codigo: 'M11', tipo: 'MOTO', ubicacion: 'Sótano 1' });
    request.flush({ ...cell, codigo: 'M11', tipo: 'MOTO' });
    listado();
    expect(fixture.componentInstance.success()).toContain('registrada');
  });

  it('rechaza blancos y muestra duplicados junto al código', () => {
    const c = fixture.componentInstance;
    c.newCell();
    c.form.setValue({ codigo: ' ', tipo: ' ', ubicacion: '' });
    c.save();
    expect(c.form.invalid).toBe(true);
    c.form.setValue({ codigo: 'C05', tipo: 'Libre', ubicacion: '' });
    expect(c.form.invalid).toBe(true);
    c.form.setValue({ codigo: 'C05', tipo: 'CARRO', ubicacion: '' });
    c.save();
    http
      .expectOne('/celdas')
      .flush(
        { detail: 'Ya existe una celda con ese código.' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.fieldError('codigo')).toContain('Ya existe');
  });

  it('edita mediante PATCH y recarga la lista', () => {
    const c = fixture.componentInstance;
    c.edit(cell);
    http.expectOne('/celdas/1').flush({ ...cell, auditoria: [] });
    c.form.controls.codigo.setValue('M71');
    c.form.controls.tipo.setValue('MOTO');
    c.save();
    const request = http.expectOne({ method: 'PATCH', url: '/celdas/1' });
    expect(request.request.body.id).toBeUndefined();
    expect(request.request.body).toEqual({ codigo: 'M71', tipo: 'MOTO', ubicacion: null });
    request.flush({ ...cell, codigo: 'M71', tipo: 'MOTO' });
    listado();
  });

  // Iteración 2 (cambió el propósito): antes confirmaba la eliminación; las celdas ya no se
  // eliminan (D4), se inhabilitan. La confirmación nombra la celda y permite cancelar (RNF-21).
  it('requiere confirmación y permite cancelar antes de inhabilitar', () => {
    const c = fixture.componentInstance;
    c.confirmDisable(cell);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]').textContent).toContain(
      '¿Inhabilitar la celda C71?',
    );
    c.cancel();
    http.expectNone((request) => request.url.endsWith('/inhabilitar'));
    c.confirmDisable(cell);
    c.disable();
    http
      .expectOne({ method: 'POST', url: '/celdas/1/inhabilitar' })
      .flush({ ...cell, ...inhabilitada, id: 1, codigo: 'C71' });
    listado([{ ...cell, habilitada: false, estado: 'INHABILITADA' }]);
    expect(c.success()).toContain('Celda C71 inhabilitada: ya no se asigna a nuevas entradas.');
    http.expectNone((request) => request.method === 'DELETE');
  });

  it('informa que no se puede cambiar el tipo de una celda ocupada', () => {
    const c = fixture.componentInstance;
    c.edit(cell);
    http.expectOne('/celdas/1').flush({ ...cell, auditoria: [] });
    c.form.controls.codigo.setValue('M71');
    c.form.controls.tipo.setValue('MOTO');
    c.save();
    const detail = 'La celda C71 está ocupada: su código y su tipo no se pueden cambiar.';
    http.expectOne('/celdas/1').flush({ detail }, { status: 409, statusText: 'Conflict' });
    expect(c.actionError()).toBe(detail);
    expect(c.fieldError('tipo')).toBe(detail);
    expect(c.fieldError('codigo')).toBe('');
  });

  // Iteración 2: el Operador solo consulta; crear, editar e inhabilitar son del Administrador.
  it('el Operador ve el listado sin acciones y el Administrador con acciones', () => {
    const auth = TestBed.inject(AuthService);
    const botones = () =>
      [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].map((b) =>
        b.textContent?.trim(),
      );
    auth.cuenta.set({
      id: 2,
      nombre_usuario: 'marta.usuga',
      nombre: 'Marta',
      rol: 'OPERADOR',
      permisos: ['celdas:ver', 'consultas', 'estancias', 'vehiculos:ver'],
    });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('C71');
    expect(botones()).not.toContain('Nueva celda');
    expect(botones()).not.toContain('Editar');
    expect(botones()).not.toContain('Inhabilitar');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Acciones');
    auth.cuenta.set({
      id: 1,
      nombre_usuario: 'admin',
      nombre: 'Admin',
      rol: 'ADMINISTRADOR',
      permisos: ['celdas:gestionar', 'celdas:ver', 'vehiculos:ver'],
    });
    fixture.detectChanges();
    expect(botones()).toContain('Nueva celda');
    expect(botones()).toContain('Editar');
  });

  // --- Iteración 2: HU-22 a HU-25 ---

  it('muestra código, tipo, ubicación y estado, con la placa de las ocupadas (HU-22)', () => {
    fixture.componentInstance.load(0);
    listado([{ ...cell, ubicacion: 'Sótano 1' }, ocupada, inhabilitada]);
    const encabezados = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('thead th'),
    ].map((th) => th.textContent?.trim());
    expect(encabezados).toEqual(['Código', 'Tipo', 'Ubicación', 'Estado', 'Acciones']);
    expect(texto()).toContain('Sótano 1');
    expect(texto()).toContain('Libre');
    expect(texto()).toContain('Ocupada');
    expect(texto()).toContain('ABC123');
    expect(texto()).toContain('Inhabilitada');
  });

  it('busca por código y filtra por tipo y estado', () => {
    const c = fixture.componentInstance;
    c.filtros.setValue({ buscar: ' c7 ', tipo: 'CARRO', estado: 'LIBRE' });
    c.buscar();
    const req = http.expectOne((r) => r.url === '/celdas');
    expect(req.request.params.get('buscar')).toBe('c7');
    expect(req.request.params.get('tipo')).toBe('CARRO');
    expect(req.request.params.get('estado')).toBe('LIBRE');
    req.flush({ items: [], total: 0, offset: 0, limit: 10 });
    fixture.detectChanges();
    expect(texto()).toContain('No hay celdas que coincidan.');
  });

  it('valida el código según el tipo y la ubicación antes de enviar (HU-23)', () => {
    const c = fixture.componentInstance;
    c.newCell();
    for (const [codigo, tipo, mensaje] of [
      ['C00', 'CARRO', 'dos dígitos del 01 al 99'],
      ['C100', 'CARRO', 'dos dígitos del 01 al 99'],
      ['M05', 'CARRO', 'debe tener un código que empiece por C'],
    ]) {
      c.form.setValue({ codigo, tipo, ubicacion: '' });
      c.save();
      expect(c.fieldError('codigo')).toContain(mensaje);
    }
    c.form.setValue({ codigo: 'C05', tipo: 'CARRO', ubicacion: 'u'.repeat(61) });
    c.save();
    expect(c.fieldError('ubicacion')).toContain('máximo 60');
    http.expectNone({ method: 'POST', url: '/celdas' });
    c.form.setValue({ codigo: ' c99 ', tipo: 'CARRO', ubicacion: 'u'.repeat(60) });
    c.save();
    expect(http.expectOne({ method: 'POST', url: '/celdas' }).request.body.codigo).toBe('C99');
  });

  it('con historial u ocupada, el código y el tipo quedan fijos y se explica por qué (HU-24)', () => {
    const c = fixture.componentInstance;
    c.edit(conHistorial);
    http.expectOne('/celdas/3').flush({ ...conHistorial, auditoria: [] });
    fixture.detectChanges();
    expect(texto()).toContain('ya tuvo movimientos');
    expect(c.form.controls.codigo.disabled).toBe(true);
    expect(c.form.controls.tipo.disabled).toBe(true);
    c.form.controls.ubicacion.setValue(' Zona norte ');
    c.save();
    const req = http.expectOne({ method: 'PATCH', url: '/celdas/3' });
    expect(req.request.body).toEqual({ ubicacion: 'Zona norte' }); // solo la ubicación
    req.flush({ ...conHistorial, ubicacion: 'Zona norte' });
    listado();
    c.edit(ocupada);
    http.expectOne('/celdas/2').flush({ ...ocupada, auditoria: [] });
    fixture.detectChanges();
    expect(texto()).toContain('está ocupada: su código y su tipo no se pueden cambiar');
  });

  it('una ocupada no ofrece inhabilitar y explica que primero debe salir el vehículo (HU-25)', () => {
    fixture.componentInstance.load(0);
    listado([ocupada, inhabilitada]);
    expect(boton('Inhabilitar C01')).toBeUndefined();
    expect(texto()).toContain('Ocupada: primero debe salir el vehículo');
    boton('Rehabilitar M10')!.click();
    http
      .expectOne({ method: 'POST', url: '/celdas/4/rehabilitar' })
      .flush({ ...inhabilitada, habilitada: true, estado: 'LIBRE' });
    listado([ocupada, { ...inhabilitada, habilitada: true, estado: 'LIBRE' }]);
    expect(texto()).toContain('Celda M10 rehabilitada: vuelve a estar disponible.');
  });

  it('muestra el 409 del servidor al inhabilitar sin error técnico', () => {
    const c = fixture.componentInstance;
    c.confirmDisable(cell);
    c.disable();
    http
      .expectOne({ method: 'POST', url: '/celdas/1/inhabilitar' })
      .flush(
        { detail: 'La celda C71 está ocupada: primero debe salir el vehículo.' },
        { status: 409, statusText: 'Conflict' },
      );
    listado();
    expect(c.actionError()).toBe('La celda C71 está ocupada: primero debe salir el vehículo.');
  });

  it('el detalle muestra la auditoría de la celda (RF-31)', () => {
    boton('Ver detalle de C71')!.click();
    http.expectOne('/celdas/1').flush({
      ...cell,
      auditoria: [
        {
          fecha: '2026-11-09T20:00:00Z',
          accion: 'CREAR',
          detalle: 'Código C71, tipo CARRO.',
          actor: 'Sandra Patiño (admin)',
        },
        {
          fecha: '2026-11-09T21:00:00Z',
          accion: 'EDITAR',
          detalle: 'ubicación: — → Sótano 1',
          actor: 'Sandra Patiño (admin)',
        },
        {
          fecha: '2026-11-09T22:00:00Z',
          accion: 'INHABILITAR',
          detalle: null,
          actor: 'Sandra Patiño (admin)',
        },
      ],
    });
    fixture.detectChanges();
    expect(texto()).toContain('Creó la celda');
    expect(texto()).toContain('Editó la celda');
    expect(texto()).toContain('ubicación: — → Sótano 1');
    expect(texto()).toContain('Inhabilitó la celda');
    expect(texto()).toContain('Sandra Patiño (admin)');
  });
});
