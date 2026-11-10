import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../auth/auth.service';
import { Cuenta } from '../models/cuenta';
import { Cuentas } from './cuentas';

// HU-19 Crear cuenta, HU-20 Consultar cuentas, HU-21 Desactivar o reactivar (Iteración 2).
describe('Cuentas de usuario', () => {
  let fixture: ComponentFixture<Cuentas>;
  let c: Cuentas;
  let http: HttpTestingController;
  const admin: Cuenta = {
    id: 1,
    nombre: 'Sandra Patiño',
    nombre_usuario: 'admin',
    rol: 'ADMINISTRADOR',
    activa: true,
    creada_en: '2026-11-08T15:00:00Z',
  };
  const diego: Cuenta = {
    id: 3,
    nombre: 'Diego Arango (Portería 2)',
    nombre_usuario: 'diego.arango',
    rol: 'OPERADOR',
    activa: true,
    creada_en: '2026-11-08T15:00:00Z',
  };
  const listado = (items: Cuenta[] = [admin, diego], url = '/cuentas?offset=0&limit=10') => {
    http.expectOne(url).flush({ items, total: items.length, offset: 0, limit: 10 });
    fixture.detectChanges();
  };
  const texto = () => (fixture.nativeElement as HTMLElement).textContent ?? '';
  const boton = (etiqueta: string) =>
    [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (b) => b.getAttribute('aria-label') === etiqueta || b.textContent?.trim() === etiqueta,
    );

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Cuentas],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    TestBed.inject(AuthService).cuenta.set({
      id: 1,
      nombre_usuario: 'admin',
      nombre: 'Sandra Patiño',
      rol: 'ADMINISTRADOR',
      permisos: ['cuentas:gestionar'],
    });
    fixture = TestBed.createComponent(Cuentas);
    c = fixture.componentInstance;
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  // --- HU-20 ---

  it('lista nombre completo, usuario, rol, estado y fecha de creación', () => {
    listado();
    const encabezados = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('thead th'),
    ].map((th) => th.textContent?.trim());
    expect(encabezados).toEqual([
      'Nombre completo',
      'Usuario',
      'Rol',
      'Estado',
      'Creada',
      'Acciones',
    ]);
    expect(texto()).toContain('Diego Arango (Portería 2)');
    expect(texto()).toContain('diego.arango');
    expect(texto()).toContain('Operador');
    expect(texto()).toContain('Activa');
    expect(texto()).toContain('2026');
  });

  it('busca por nombre o usuario y filtra por rol y estado', () => {
    listado();
    c.filtros.setValue({ buscar: '  diego ', rol: 'OPERADOR', estado: 'INACTIVA' });
    c.buscar();
    const req = http.expectOne((r) => r.url === '/cuentas');
    expect(req.request.params.get('buscar')).toBe('diego');
    expect(req.request.params.get('rol')).toBe('OPERADOR');
    expect(req.request.params.get('estado')).toBe('INACTIVA');
    expect(req.request.params.get('offset')).toBe('0');
    req.flush({ items: [], total: 0, offset: 0, limit: 10 });
    fixture.detectChanges();
    expect(texto()).toContain('No hay cuentas que coincidan.'); // HU-20.3
    c.limpiarFiltros();
    listado();
    expect(texto()).toContain('diego.arango');
  });

  // --- HU-19 ---

  it('valida los límites antes de enviar y normaliza el usuario', () => {
    listado();
    c.nueva();
    c.form.setValue({ nombre: 'Al', nombre_usuario: 'abc', contrasena: 'clave12', rol: '' });
    c.crear();
    fixture.detectChanges();
    http.expectNone({ method: 'POST', url: '/cuentas' });
    expect(texto()).toContain('El nombre completo debe tener de 3 a 80 caracteres.');
    expect(texto()).toContain('Usa de 4 a 30 caracteres');
    expect(texto()).toContain('La contraseña debe tener de 8 a 64 caracteres.');
    expect(texto()).toContain('Elige el rol de la cuenta.');
    c.form.setValue({
      nombre: '  Ana Pérez ',
      nombre_usuario: ' Ana.Perez ',
      contrasena: 'contraseña',
      rol: 'OPERADOR',
    });
    c.crear();
    fixture.detectChanges();
    http.expectNone({ method: 'POST', url: '/cuentas' });
    expect(texto()).toContain('al menos una letra y un número');
    expect(c.form.controls.nombre_usuario.value).toBe('ana.perez');
  });

  it('crea la cuenta y nunca vuelve a mostrar la contraseña', () => {
    listado();
    c.nueva();
    c.form.setValue({
      nombre: '  Ana Pérez ',
      nombre_usuario: ' Ana.Perez ',
      contrasena: 'clave123',
      rol: 'OPERADOR',
    });
    c.crear();
    c.crear();
    const req = http.expectOne({ method: 'POST', url: '/cuentas' });
    expect(req.request.body).toEqual({
      nombre: 'Ana Pérez',
      nombre_usuario: 'ana.perez',
      contrasena: 'clave123',
      rol: 'OPERADOR',
    });
    req.flush(
      { ...diego, id: 9, nombre: 'Ana Pérez', nombre_usuario: 'ana.perez' },
      { status: 201, statusText: 'Created' },
    );
    listado([admin, diego, { ...diego, id: 9, nombre: 'Ana Pérez', nombre_usuario: 'ana.perez' }]);
    expect(texto()).toContain('Cuenta de Ana Pérez (ana.perez) creada y activa.');
    expect(texto()).not.toContain('clave123');
    expect(c.form.controls.contrasena.value).toBe('');
    expect(c.mostrarFormulario()).toBe(false);
  });

  it('usuario en uso: muestra el mensaje del servidor junto al campo y borra la contraseña', () => {
    listado();
    c.nueva();
    c.form.setValue({
      nombre: 'Marta Dos',
      nombre_usuario: 'Marta.Usuga',
      contrasena: 'clave123',
      rol: 'OPERADOR',
    });
    c.crear();
    http
      .expectOne({ method: 'POST', url: '/cuentas' })
      .flush(
        { detail: 'Ese nombre de usuario ya está en uso.' },
        { status: 409, statusText: 'Conflict' },
      );
    fixture.detectChanges();
    expect(c.error('nombre_usuario')).toBe('Ese nombre de usuario ya está en uso.');
    expect(texto()).toContain('Ese nombre de usuario ya está en uso.');
    expect(c.form.controls.contrasena.value).toBe('');
    // Al corregir el usuario, el aviso desaparece.
    c.form.controls.nombre_usuario.setValue('marta.dos');
    expect(c.error('nombre_usuario')).toBe('');
  });

  // --- HU-21 ---

  it('pide confirmación nombrando a la persona antes de desactivar', () => {
    listado();
    boton('Desactivar la cuenta de Diego Arango (Portería 2)')!.click();
    fixture.detectChanges();
    http.expectNone((r) => r.url.endsWith('/desactivar'));
    const dialogo = (fixture.nativeElement as HTMLElement).querySelector('[role="alertdialog"]')!;
    expect(dialogo.textContent).toContain('Diego Arango (Portería 2) (diego.arango)');
    boton('Cancelar')!.click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alertdialog"]')).toBeNull();
    http.expectNone((r) => r.url.endsWith('/desactivar'));
  });

  it('desactiva tras confirmar y luego permite reactivar', () => {
    listado();
    c.pedirDesactivar(diego);
    fixture.detectChanges();
    boton('Sí, desactivar')!.click();
    http
      .expectOne({ method: 'POST', url: '/cuentas/3/desactivar' })
      .flush({ ...diego, activa: false });
    listado([admin, { ...diego, activa: false }]);
    expect(texto()).toContain(
      'Cuenta de Diego Arango (Portería 2) desactivada: ya no puede ingresar.',
    );
    expect(texto()).toContain('Desactivada');
    boton('Reactivar la cuenta de Diego Arango (Portería 2)')!.click();
    http.expectOne({ method: 'POST', url: '/cuentas/3/reactivar' }).flush(diego);
    listado();
    expect(texto()).toContain('reactivada: puede volver a ingresar');
  });

  it('no ofrece desactivar la propia cuenta', () => {
    listado();
    expect(boton('Desactivar la cuenta de Sandra Patiño')).toBeUndefined();
    expect(texto()).toContain('Tu cuenta');
  });

  it('muestra el rechazo del servidor (último administrador) sin error técnico', () => {
    listado();
    c.pedirDesactivar({ ...diego, rol: 'ADMINISTRADOR' });
    c.desactivar();
    http
      .expectOne({ method: 'POST', url: '/cuentas/3/desactivar' })
      .flush(
        { detail: 'No se puede desactivar al último administrador activo.' },
        { status: 409, statusText: 'Conflict' },
      );
    listado();
    expect(texto()).toContain('No se puede desactivar al último administrador activo.');
    c.reactivar(diego);
    http
      .expectOne({ method: 'POST', url: '/cuentas/3/reactivar' })
      .flush('psycopg.errors.InternalError: traceback', { status: 500, statusText: 'Error' });
    listado();
    expect(texto()).toContain('No se pudo conectar con el servicio');
    expect(texto()).not.toContain('psycopg');
  });

  // --- RF-31 ---

  it('el detalle muestra quién y cuándo creó, desactivó o reactivó la cuenta', () => {
    listado();
    boton('Ver detalle de Diego Arango (Portería 2)')!.click();
    http.expectOne('/cuentas/3').flush({
      ...diego,
      auditoria: [
        {
          fecha: '2026-11-08T15:00:00Z',
          accion: 'CREAR',
          detalle: 'Creada por las semillas.',
          actor: null,
        },
        {
          fecha: '2026-11-09T20:30:00Z',
          accion: 'DESACTIVAR',
          detalle: null,
          actor: 'Sandra Patiño (admin)',
        },
      ],
    });
    fixture.detectChanges();
    expect(texto()).toContain('Creó la cuenta');
    expect(texto()).toContain('Sistema (semillas)');
    expect(texto()).toContain('Desactivó la cuenta');
    expect(texto()).toContain('Sandra Patiño (admin)');
    expect(texto()).toContain('3:30'); // 20:30 UTC = 3:30 p. m. en Bogotá
  });
});
