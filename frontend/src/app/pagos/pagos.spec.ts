import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Cotizacion, EstadoMensualidadRespuesta, PagoDetalle } from '../models/pago';
import { textoDe } from '../utils/pruebas';
import { Pagos } from './pagos';

describe('Pagos: estado y registro (HU-29, HU-30)', () => {
  let fixture: ComponentFixture<Pagos>;
  let http: HttpTestingController;
  const estado: EstadoMensualidadRespuesta = {
    vehiculo_id: 9,
    placa: 'ABC123',
    tipo_vehiculo: 'AUTOMOVIL',
    marca: 'Mazda',
    color: 'Rojo',
    cliente: {
      id: 1,
      tipo_documento: 'CC',
      documento: '1001234567',
      nombre: 'Laura Gómez',
      telefono: '3001112233',
    },
    estado: 'VIGENTE',
    periodo_actual: { fecha_inicio: '2026-11-10', fecha_fin: '2026-11-30', comprobante: null },
    periodos_futuros: [],
    periodos_anulados: [],
    vence: '2026-11-30',
    dias_restantes: 10,
    inicio_nuevo_periodo: '2026-12-01',
    fin_maximo: '2027-11-20',
    tarifa: { id: 3, tipo_vehiculo: 'AUTOMOVIL', valor: 120000 },
  };
  const cotizacion: Cotizacion = {
    placa: 'ABC123',
    cliente_nombre: 'Laura Gómez',
    tipo_vehiculo: 'AUTOMOVIL',
    meses: 2,
    fecha_inicio: '2026-12-01',
    fecha_fin: '2027-01-31',
    tarifa_id: 3,
    valor_mensual: 120000,
    monto: 240000,
  };
  const pago: PagoDetalle = {
    id: 41,
    comprobante: 'RC-000041',
    fecha: '2026-11-20T15:00:00Z',
    placa: 'ABC123',
    cliente_nombre: 'Laura Gómez',
    fecha_inicio: '2026-12-01',
    fecha_fin: '2027-01-31',
    meses: 2,
    monto: 240000,
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
  const escribir = (selector: string, valor: string) => {
    const el = root().querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    el.value = valor;
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
    fixture.detectChanges();
  };
  const boton = (etiqueta: string) =>
    [...root().querySelectorAll('button')].find((b) => b.textContent?.trim() === etiqueta)!;
  /** Las opciones usan [ngValue]: se elige por el texto visible ('2 meses'). */
  const elegirMeses = (etiqueta: string) => {
    const select = root().querySelector<HTMLSelectElement>('#meses')!;
    select.value = [...select.options].find((o) => o.textContent?.trim() === etiqueta)!.value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    fixture.detectChanges();
  };
  const enviar = (selector: string) => {
    root()
      .querySelector(selector)!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
  };
  const buscar = (placa = ' abc-123 ', respuesta: EstadoMensualidadRespuesta = estado) => {
    escribir('#placa', placa);
    enviar('.buscar-placa');
    http.expectOne('/pagos/estado/ABC123').flush(respuesta);
    fixture.detectChanges();
  };
  const cotizar = (meses: string, respuesta: Cotizacion = cotizacion) => {
    http
      .expectOne(
        (r) =>
          r.url === '/pagos/cotizacion' &&
          r.params.get('placa') === 'ABC123' &&
          r.params.get('meses') === meses,
      )
      .flush(respuesta);
    fixture.detectChanges();
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Pagos],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Pagos);
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('busca la placa normalizada y muestra el estado con vencimiento, días y tarifa', () => {
    buscar();
    expect(texto()).toContain('ABC123');
    expect(texto()).toContain('Vigente');
    expect(texto()).toContain('Vigente hasta el 30/11/2026 · Faltan 10 días. Puede entrar.');
    expect(texto()).toContain('Laura Gómez · CC 1001234567 · 3001112233');
    expect(texto()).toContain('$ 120.000 al mes (AUTOMOVIL)');
    expect(texto()).toContain('El nuevo periodo empezaría el 01/12/2026');
  });

  it('placa vacía o inexistente: mensaje claro, sin error técnico (ME-05)', () => {
    enviar('.buscar-placa');
    expect(texto()).toContain('Escribe la placa del vehículo.');
    escribir('#placa', 'zzz999');
    enviar('.buscar-placa');
    http
      .expectOne('/pagos/estado/ZZZ999')
      .flush({ detail: 'Vehículo no encontrado.' }, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();
    expect(texto()).toContain(
      'La placa ZZZ999 no está registrada. Revísala o registra el vehículo en Vehículos.',
    );
  });

  it('muestra vencida, sin mensualidad, periodos hacia adelante y anulados marcados (ME-02 a ME-04)', () => {
    buscar(' abc123', {
      ...estado,
      estado: 'SIN_MENSUALIDAD',
      periodo_actual: null,
      vence: null,
      dias_restantes: null,
      periodos_anulados: [
        { fecha_inicio: '2026-11-18', fecha_fin: '2026-12-17', comprobante: 'RC-000007' },
      ],
    });
    expect(texto()).toContain('No tiene mensualidad. No puede entrar hasta que pague.');
    expect(texto()).toContain('Del 18/11/2026 al 17/12/2026 · RC-000007 · Anulado (no cuenta)');
    buscar('abc123', {
      ...estado,
      estado: 'VENCIDA',
      periodo_actual: null,
      vence: '2026-11-15',
      dias_restantes: null,
    });
    expect(texto()).toContain('Venció el 15/11/2026. No puede entrar hasta que pague.');
    buscar('abc123', {
      ...estado,
      periodos_futuros: [
        { fecha_inicio: '2026-12-01', fecha_fin: '2026-12-31', comprobante: 'RC-000002' },
      ],
      dias_restantes: 0,
    });
    expect(texto()).toContain('Vence hoy');
    expect(texto()).toContain('Del 01/12/2026 al 31/12/2026 · RC-000002');
  });

  it('sin tarifa definida avisa y no deja registrar', () => {
    buscar('abc123', { ...estado, tarifa: null });
    expect(texto()).toContain(
      'No hay tarifa definida para AUTOMOVIL: el Administrador debe definirla en Tarifas',
    );
    expect(root().querySelector<HTMLFieldSetElement>('form fieldset')?.disabled).toBe(true);
  });

  it('la referencia aparece en transferencia y tarjeta y se valida igual que el servidor (PA-05)', () => {
    buscar();
    expect(root().querySelector('#referencia')).toBeNull();
    escribir('#metodo', 'TRANSFERENCIA');
    expect(root().querySelector('#referencia')).not.toBeNull();
    boton('Revisar pago').click();
    fixture.detectChanges();
    expect(texto()).toContain('La referencia es obligatoria para transferencia y tarjeta.');
    escribir('#referencia', 'ABC');
    expect(texto()).toContain(
      'La referencia debe tener de 4 a 30 caracteres: letras, números o guion.',
    );
    http.expectNone((r) => r.url === '/pagos/cotizacion');
  });

  it('muestra el resumen antes de confirmar y al volver no registra nada (RNF-27, PA-07)', () => {
    buscar();
    elegirMeses('2 meses');
    boton('Revisar pago').click();
    fixture.detectChanges();
    cotizar('2');
    expect(texto()).toContain('Resumen del pago');
    expect(texto()).toContain('ABC123 · AUTOMOVIL');
    expect(texto()).toContain('Del 01/12/2026 al 31/01/2027');
    expect(texto()).toContain('2 meses × $ 120.000');
    expect(texto()).toContain('Monto a pagar $ 240.000');
    boton('Volver y corregir').click();
    fixture.detectChanges();
    expect(texto()).not.toContain('Resumen del pago');
    http.expectNone({ method: 'POST', url: '/pagos' });
  });

  it('confirma con el monto del resumen y muestra el comprobante (PA-01, PA-02)', () => {
    buscar();
    elegirMeses('2 meses');
    escribir('#metodo', 'TARJETA');
    escribir('#referencia', ' VOUCHER-77 ');
    boton('Revisar pago').click();
    fixture.detectChanges();
    cotizar('2');
    expect(texto()).toContain('Tarjeta · Referencia');
    boton('Confirmar pago').click();
    const registro = http.expectOne({ method: 'POST', url: '/pagos' });
    expect(registro.request.body).toEqual({
      placa: 'ABC123',
      meses: 2,
      metodo: 'TARJETA',
      referencia: 'VOUCHER-77',
      monto_confirmado: 240000,
    });
    registro.flush({ ...pago, metodo: 'TARJETA', referencia: 'VOUCHER-77' });
    http.expectOne('/pagos/estado/ABC123').flush({ ...estado, inicio_nuevo_periodo: '2027-02-01' });
    fixture.detectChanges();
    expect(texto()).toContain(
      'Pago registrado. Comprobante RC-000041. El vehículo queda al día hasta el 31/01/2027.',
    );
    expect(texto()).toContain('Comprobante de pago');
    expect(texto()).toContain('Total pagado $ 240.000');
    expect(texto()).toContain('Tarjeta · Referencia VOUCHER-77');
    expect(texto()).toContain('Marta Úsuga (marta.usuga)');
    boton('Registrar otro pago').click();
    fixture.detectChanges();
    expect(texto()).toContain('El nuevo periodo empezaría el 01/02/2027');
  });

  it('efectivo envía la referencia vacía como null', () => {
    buscar();
    boton('Revisar pago').click();
    fixture.detectChanges();
    cotizar('1', { ...cotizacion, meses: 1, monto: 120000 });
    boton('Confirmar pago').click();
    const registro = http.expectOne({ method: 'POST', url: '/pagos' });
    expect(registro.request.body.referencia).toBeNull();
    expect(registro.request.body.monto_confirmado).toBe(120000);
    registro.flush(pago);
    http.expectOne('/pagos/estado/ABC123').flush(estado);
  });

  it('si la tarifa cambió, no registra, muestra el monto nuevo y deja confirmar otra vez (HU-30.2, PA-09)', () => {
    buscar();
    boton('Revisar pago').click();
    fixture.detectChanges();
    cotizar('1', { ...cotizacion, meses: 1, monto: 120000 });
    boton('Confirmar pago').click();
    const aviso =
      'La tarifa cambió después del resumen: el monto ahora es $ 130.000. Revisa el nuevo resumen y confirma otra vez.';
    http
      .expectOne({ method: 'POST', url: '/pagos' })
      .flush({ detail: aviso }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    cotizar('1', { ...cotizacion, meses: 1, valor_mensual: 130000, monto: 130000 });
    expect(texto()).toContain(aviso);
    expect(texto()).toContain('Monto a pagar $ 130.000');
    expect(texto()).not.toContain('Pago registrado');
    boton('Confirmar pago').click();
    const segundo = http.expectOne({ method: 'POST', url: '/pagos' });
    expect(segundo.request.body.monto_confirmado).toBe(130000);
    segundo.flush({ ...pago, meses: 1, monto: 130000, valor_mensual: 130000 });
    http.expectOne('/pagos/estado/ABC123').flush(estado);
    fixture.detectChanges();
    expect(texto()).toContain('Total pagado $ 130.000');
  });

  it('un rechazo del servidor (tope de 12 meses) se muestra en español (PA-06)', () => {
    buscar();
    elegirMeses('6 meses');
    boton('Revisar pago').click();
    fixture.detectChanges();
    const detalle =
      'El pago dejaría la mensualidad vigente hasta el 30/05/2028: lo máximo es 12 meses desde hoy (20/11/2027). Registra menos meses.';
    http
      .expectOne((r) => r.url === '/pagos/cotizacion')
      .flush({ detail: detalle }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(texto()).toContain(detalle);
    expect(texto()).not.toContain('Resumen del pago');
  });
});
