import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Vehiculos, modeloMaximo } from './vehiculos';
import { Vehiculo } from '../models/vehiculo';

describe('Gestión de vehículos', () => {
  it('guarda los valores introducidos en los controles HTML', () => {
    flushList();
    component.newVehicle();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    for (const [field, value] of Object.entries({
      placa: ' dom-12a ',
      marca: 'Prueba',
      modelo: '2025',
      color: 'Azul',
    })) {
      const input = root.querySelector<HTMLInputElement>(`#${field}`)!;
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const select = root.querySelector<HTMLSelectElement>('#tipo')!;
    select.value = 'MOTO';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    const owner = root.querySelector<HTMLSelectElement>('#cliente_id')!;
    owner.selectedIndex = 1;
    owner.dispatchEvent(new Event('change', { bubbles: true }));
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    const request = http.expectOne({ method: 'POST', url: '/vehiculos' });
    expect(request.request.body.modelo).toBe(2025);
    expect(request.request.body.placa).toBe('DOM12A');
    expect(request.request.body.cliente_id).toBe(1);
    request.flush({ ...vehicle, placa: 'DOM12A', tipo: 'MOTO' });
    flushList([{ ...vehicle, placa: 'DOM12A', tipo: 'MOTO' }]);
  });
  let fixture: ComponentFixture<Vehiculos>;
  let component: Vehiculos;
  let http: HttpTestingController;
  const vehicle: Vehiculo = {
    id: 1,
    placa: 'ABC123',
    marca: 'Marca',
    color: 'Azul',
    modelo: 2025,
    tipo: 'AUTOMOVIL',
    cliente_id: 1,
    cliente_nombre: 'Laura Gómez',
    mensualidad_vigente: true,
    mensualidad_hasta: '2026-11-20',
  };
  const flushList = (items: Vehiculo[] = [], total = items.length, offset = 0) => {
    http
      .expectOne(`/vehiculos?offset=${offset}&limit=10`)
      .flush({ items, total, offset, limit: 10 });
    fixture.detectChanges();
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Vehiculos],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Vehiculos);
    component = fixture.componentInstance;
    fixture.detectChanges();
    // Iteración 1: el selector de cliente carga todos los clientes al abrir la pantalla.
    http.expectOne('/clientes?offset=0&limit=100').flush({
      items: [{ id: 1, documento: '1001', nombre: 'Laura Gómez', telefono: '300', correo: null }],
      total: 1,
      offset: 0,
      limit: 100,
    });
  });
  afterEach(() => http.verify());

  it('muestra carga y listado vacío', () => {
    expect(fixture.nativeElement.textContent).toContain('Cargando vehículos');
    flushList();
    expect(fixture.nativeElement.textContent).toContain('Aún no hay vehículos');
  });

  it('pagina usando offset y limit', () => {
    flushList([vehicle], 12);
    component.load(10);
    flushList([{ ...vehicle, id: 11 }], 12, 10);
    expect(component.page()).toBe(2);
  });

  it('valida campos vacíos y años no enteros sin enviar solicitudes', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue({ placa: '   ', modelo: 2025.5 });
    component.save();
    expect(component.fieldError('placa')).toContain('obligatorio');
    expect(component.fieldError('modelo')).toContain('entero');
    http.expectNone((request) => request.method === 'POST');
  });

  it('crea con placa normalizada, bloquea doble envío y actualiza el listado', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue({ ...vehicle, placa: ' abc123 ' });
    component.save();
    component.save();
    const request = http.expectOne({ method: 'POST', url: '/vehiculos' });
    expect(request.request.body.placa).toBe('ABC123');
    expect(request.request.body.id).toBeUndefined();
    expect(component.saving()).toBe(true);
    request.flush(vehicle);
    flushList([vehicle]);
    expect(component.success()).toContain('registrado');
    expect(component.showForm()).toBe(false);
  });

  it('señala placa duplicada y permite corregirla', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue(vehicle);
    component.save();
    http
      .expectOne('/vehiculos')
      .flush({ detail: 'Duplicada' }, { status: 409, statusText: 'Conflict' });
    expect(component.fieldError('placa')).toContain('Ya existe');
    expect(component.saving()).toBe(false);
    component.form.controls.placa.setValue('DEF456');
    expect(component.form.controls.placa.valid).toBe(true);
  });

  it('consulta el vehículo y envía PATCH sin id', () => {
    flushList([vehicle]);
    component.edit(vehicle);
    http.expectOne({ method: 'GET', url: '/vehiculos/1' }).flush(vehicle);
    component.form.controls.color.setValue('Rojo');
    component.save();
    const request = http.expectOne({ method: 'PATCH', url: '/vehiculos/1' });
    expect(request.request.body.id).toBeUndefined();
    request.flush({ ...vehicle, color: 'Rojo' });
    flushList([{ ...vehicle, color: 'Rojo' }]);
    expect(component.success()).toContain('actualizado');
  });

  it('confirma con placa, permite cancelar y elimina una sola vez', () => {
    flushList([vehicle]);
    component.confirmDelete(vehicle);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]').textContent).toContain(
      'ABC123',
    );
    component.cancel();
    http.expectNone((request) => request.method === 'DELETE');
    component.confirmDelete(vehicle);
    component.remove();
    component.remove();
    http
      .expectOne({ method: 'DELETE', url: '/vehiculos/1' })
      .flush(null, { status: 204, statusText: 'No Content' });
    flushList();
    expect(component.success()).toContain('eliminado');
  });

  it('informa conflicto de eliminación sin retirar el registro', () => {
    flushList([vehicle]);
    component.confirmDelete(vehicle);
    component.remove();
    http.expectOne('/vehiculos/1').flush({}, { status: 409, statusText: 'Conflict' });
    expect(component.actionError()).toContain('registros relacionados');
    expect(component.items()).toEqual([vehicle]);
  });

  it('informa que un vehículo ya no existe', () => {
    flushList([vehicle]);
    component.edit(vehicle);
    http.expectOne('/vehiculos/1').flush({}, { status: 404, statusText: 'Not Found' });
    expect(component.actionError()).toContain('ya no existe');
  });

  it('asocia los errores 422 a los campos', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue(vehicle);
    component.save();
    http
      .expectOne('/vehiculos')
      .flush(
        { detail: [{ loc: ['body', 'modelo'], msg: 'invalid', type: 'value_error' }] },
        { status: 422, statusText: 'Unprocessable Entity' },
      );
    expect(component.fieldError('modelo')).toContain('servicio rechazó');
  });

  it('muestra error de conexión y permite reintentar la carga', () => {
    http.expectOne('/vehiculos?offset=0&limit=10').error(new ProgressEvent('error'));
    expect(component.listError()).toContain('No se pudo conectar');
    component.load();
    flushList([vehicle]);
    expect(component.listError()).toBe('');
  });

  it('retrocede cuando la última página queda vacía', () => {
    flushList([vehicle], 11);
    component.load(10);
    flushList([{ ...vehicle, id: 11 }], 11, 10);
    component.confirmDelete({ ...vehicle, id: 11 });
    component.remove();
    http.expectOne('/vehiculos/11').flush(null, { status: 204, statusText: 'No Content' });
    flushList([], 10, 10);
    flushList([vehicle], 10, 0);
    expect(component.page()).toBe(1);
  });

  // --- Iteración 1 ---

  it('valida la placa según el tipo antes de enviar', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue({ ...vehicle, placa: 'abc-123', tipo: 'MOTO' });
    component.save();
    expect(component.fieldError('placa')).toContain('moto');
    component.form.patchValue({ placa: 'abc12d', tipo: 'AUTOMOVIL' });
    expect(component.fieldError('placa')).toContain('carro');
    component.form.patchValue({ tipo: 'MOTO' });
    expect(component.fieldError('placa')).toBe('');
    http.expectNone((request) => request.method === 'POST');
  });

  it('acepta modelos de 1900 al año actual + 1', () => {
    flushList();
    component.newVehicle();
    const modelo = component.form.controls.modelo;
    for (const [value, valid] of [
      [1899, false],
      [1900, true],
      [modeloMaximo(), true],
      [modeloMaximo() + 1, false],
    ] as const) {
      modelo.setValue(value);
      expect(modelo.valid).toBe(valid);
    }
  });

  it('exige el cliente', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue({ ...vehicle, cliente_id: null });
    component.save();
    expect(component.fieldError('cliente_id')).toContain('cliente');
    http.expectNone((request) => request.method === 'POST');
  });

  it('muestra el estado de la mensualidad en el listado', () => {
    flushList([
      vehicle,
      {
        ...vehicle,
        id: 2,
        placa: 'DEF456',
        mensualidad_vigente: false,
        mensualidad_hasta: '2026-10-18',
      },
      { ...vehicle, id: 3, placa: 'GHI789', mensualidad_vigente: false, mensualidad_hasta: null },
    ]);
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(text).toContain('Laura Gómez');
    expect(text).toContain('Vigente hasta 20/11/2026');
    expect(text).toContain('Vencida el 18/10/2026');
    expect(text).toContain('Sin mensualidad');
  });

  it('informa que no se puede cambiar el tipo de un vehículo dentro', () => {
    flushList([vehicle]);
    component.edit(vehicle);
    http.expectOne({ method: 'GET', url: '/vehiculos/1' }).flush(vehicle);
    component.form.patchValue({ tipo: 'CAMIONETA' });
    component.save();
    const detail = 'No se puede cambiar el tipo de un vehículo que está dentro del parqueadero.';
    http.expectOne('/vehiculos/1').flush({ detail }, { status: 409, statusText: 'Conflict' });
    expect(component.actionError()).toBe(detail);
    expect(component.fieldError('tipo')).toBe(detail);
    expect(component.fieldError('placa')).toBe('');
  });
});
