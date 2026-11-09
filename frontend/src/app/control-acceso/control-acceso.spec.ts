import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../auth/auth.service';
import { ControlAcceso } from './control-acceso';

describe('Control de acceso', () => {
  let http: HttpTestingController;
  let c: ControlAcceso;
  let fixture: ComponentFixture<ControlAcceso>;
  const celda = { id: 2, codigo: 'M01', tipo: 'MOTO' };
  const stay = {
    id: 3,
    vehiculo_id: 1,
    celda_id: 2,
    entrada: '2026-10-19T15:00:00Z',
    salida: null,
    operador_entrada_id: 4,
    operador_salida_id: null,
  };
  const state = {
    vehiculo: {
      id: 1,
      placa: 'KLM45D',
      marca: 'Prueba',
      color: 'Azul',
      modelo: 2026,
      tipo: 'MOTO',
    },
    esta_dentro: true,
    estancia: { ...stay, celda },
  };
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ControlAcceso],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    // Iteración 2: hay una cuenta con sesión y no se carga ningún catálogo de operadores.
    TestBed.inject(AuthService).cuenta.set({
      id: 4,
      nombre_usuario: 'marta.usuga',
      nombre: 'Marta Úsuga (Portería 1)',
      rol: 'OPERADOR',
      permisos: ['estancias'],
    });
    fixture = TestBed.createComponent(ControlAcceso);
    c = fixture.componentInstance;
  });
  afterEach(() => http.verify());

  it('registra entrada con placa normalizada, sin celda ni fecha y sin doble envío', () => {
    c.entrada.setValue({ placa: ' klm-45d ' });
    c.registrarEntrada();
    c.registrarEntrada();
    const req = http.expectOne('/estancias/entrada');
    expect(req.request.body).toEqual({ placa: 'KLM45D' });
    req.flush({ ...stay, placa: 'KLM45D', celda, duracion_segundos: null, permanencia: null });
    expect(c.exitoEntrada()).toContain('M01');
    expect(c.exitoEntrada()).toContain('Bogotá');
    expect(c.ultimaEntrada()?.celda.codigo).toBe('M01');
  });
  it('rechaza blancos y muestra los conflictos de ocupación y referencias', () => {
    c.entrada.setValue({ placa: ' ' });
    c.registrarEntrada();
    http.expectNone('/estancias/entrada');
    for (const [status, detail] of [
      [409, 'El vehículo ya está dentro.'],
      [409, 'El vehículo no tiene mensualidad vigente. No puede ingresar.'],
      [409, 'No hay celdas disponibles para motos.'],
      [404, 'Vehículo no encontrado.'],
    ] as const) {
      c.entrada.controls.placa.setValue('KLM45D');
      c.registrarEntrada();
      http.expectOne('/estancias/entrada').flush({ detail }, { status, statusText: 'Error' });
      expect(c.errorEntrada()).toBe(detail);
      expect(c.ultimaEntrada()).toBeNull();
      expect(c.saving()).toBe(false);
    }
  });
  it('descarta respuestas antiguas y no permite salida al cambiar de placa', () => {
    c.consulta.setValue({ placa: 'KLM45D' });
    c.buscar();
    c.consulta.controls.placa.setValue('XYZ12A');
    http.expectOne('/estancias/vehiculo/KLM45D').flush(state);
    expect(c.estado()).toBeNull();
    c.registrarSalida();
    http.expectNone('/estancias/salida');
    c.consulta.controls.placa.setValue('KLM45D');
    c.buscar();
    http.expectOne('/estancias/vehiculo/KLM45D').flush(state);
    c.consulta.controls.placa.setValue('XYZ12A');
    expect(c.estado()).toBeNull();
  });
  it('consulta antes de salir, envía solo la placa y consulta fuera tras cerrar', () => {
    c.consulta.setValue({ placa: 'klm-45d' });
    c.buscar();
    http.expectOne('/estancias/vehiculo/KLM45D').flush(state);
    c.registrarSalida();
    c.registrarSalida();
    const req = http.expectOne('/estancias/salida');
    expect(req.request.body).toEqual({ placa: 'KLM45D' });
    req.flush({
      ...stay,
      salida: '2026-10-19T16:00:00Z',
      operador_salida_id: 4,
      placa: 'KLM45D',
      celda,
      duracion_segundos: 3600,
      permanencia: '1 h 00 min',
    });
    http
      .expectOne('/estancias/vehiculo/KLM45D')
      .flush({ ...state, esta_dentro: false, estancia: null });
    expect(c.estado()?.esta_dentro).toBe(false);
    expect(c.exitoSalida()).toContain('Salida registrada');
    expect(c.ultimaSalida()?.permanencia).toBe('1 h 00 min');
  });
  it('distingue no registrado y conexión fallida e invalida salida rechazada', () => {
    c.consulta.setValue({ placa: 'KLM45D' });
    c.buscar();
    http
      .expectOne('/estancias/vehiculo/KLM45D')
      .flush({}, { status: 404, statusText: 'Not Found' });
    expect(c.errorConsulta()).toBe('Vehículo no registrado.');
    c.buscar();
    http.expectOne('/estancias/vehiculo/KLM45D').error(new ProgressEvent('error'));
    expect(c.errorConsulta()).toContain('No se pudo conectar');
    c.buscar();
    http.expectOne('/estancias/vehiculo/KLM45D').flush(state);
    c.registrarSalida();
    http
      .expectOne('/estancias/salida')
      .flush({ detail: 'Sin estancia abierta.' }, { status: 409, statusText: 'Conflict' });
    expect(c.estado()).toBeNull();
    expect(c.errorConsulta()).toContain('Consulta nuevamente');
  });
  it('interpreta el offset recibido y presenta el mismo instante en Bogotá', () => {
    expect(c.fecha('2026-10-19T15:00:00Z')).toBe(c.fecha('2026-10-19T10:00:00-05:00'));
    expect(c.fecha('2026-10-19T15:00:00Z')).toContain('10:00:00');
  });

  it('tras corregir la celda muestra el cambio y vuelve a consultar el vehículo', () => {
    c.consulta.setValue({ placa: 'KLM45D' });
    c.buscar();
    http.expectOne('/estancias/vehiculo/KLM45D').flush(state);
    c.alCorregir({
      id: 1,
      estancia_id: 3,
      celda_anterior: celda,
      celda_nueva: { ...celda, id: 7, codigo: 'M07' },
      operador_id: 4,
      fecha: '2026-10-23T15:00:00Z',
      motivo: 'Parqueó en la M07',
    });
    expect(c.exitoCorreccion()).toContain('M01 → M07');
    http
      .expectOne('/estancias/vehiculo/KLM45D')
      .flush({ ...state, estancia: { ...state.estancia, celda: { ...celda, codigo: 'M07' } } });
    expect(c.estado()?.estancia?.celda.codigo).toBe('M07');
    c.registrarSalida();
    expect(c.exitoCorreccion()).toBe('');
    http.expectOne('/estancias/salida').flush({}, { status: 409, statusText: 'Conflict' });
  });

  it('muestra al responsable de la sesión y no tiene selector de operador (Iteración 2)', () => {
    fixture.detectChanges();
    const pagina = fixture.nativeElement as HTMLElement;
    expect(pagina.textContent).toContain(
      'Responsable de las operaciones: Marta Úsuga (Portería 1)',
    );
    expect(pagina.querySelector('select')).toBeNull();
    expect(pagina.textContent).not.toContain('Selecciona un operador');
    http.expectNone((r) => r.url.startsWith('/operadores'));
  });
});
