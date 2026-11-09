import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { Ingreso } from './ingreso';

describe('Pantalla de ingreso (HU-15)', () => {
  let fixture: ComponentFixture<Ingreso>;
  let c: Ingreso;
  let http: HttpTestingController;
  let navegar: ReturnType<typeof vi.spyOn>;

  const montar = (params: Record<string, string> = {}) => {
    TestBed.configureTestingModule({
      imports: [Ingreso],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap(params) } },
        },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    navegar = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    fixture = TestBed.createComponent(Ingreso);
    c = fixture.componentInstance;
    fixture.detectChanges();
  };
  const texto = () => (fixture.nativeElement as HTMLElement).textContent ?? '';
  const responder = (status: number, detail?: string) => {
    c.form.setValue({ usuario: 'marta.usuga', contrasena: 'clave123' });
    c.ingresar();
    http.expectOne('/auth/login').flush(detail ? { detail } : {}, { status, statusText: 'x' });
    fixture.detectChanges();
  };

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it('no tiene selector de rol: solo usuario y contraseña (D1)', () => {
    montar();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('input').length).toBe(2);
    expect(el.querySelector('select')).toBeNull();
    expect((el.querySelector('#contrasena') as HTMLInputElement).type).toBe('password');
  });

  it('indica qué campo falta y no envía la solicitud', () => {
    montar();
    c.form.setValue({ usuario: '   ', contrasena: '' });
    c.ingresar();
    fixture.detectChanges();
    http.expectNone('/auth/login');
    expect(texto()).toContain('Escribe tu usuario.');
    expect(texto()).toContain('Escribe tu contraseña.');
    c.form.setValue({ usuario: 'marta', contrasena: '' });
    fixture.detectChanges();
    expect(texto()).not.toContain('Escribe tu usuario.');
    expect(texto()).toContain('Escribe tu contraseña.');
  });

  it('con credenciales válidas entra y va a la pantalla pedida', () => {
    montar({ volver: '/consultas/historial' });
    c.form.setValue({ usuario: ' Marta.Usuga ', contrasena: 'clave123' });
    c.ingresar();
    c.ingresar();
    const req = http.expectOne('/auth/login');
    expect(req.request.body).toEqual({ usuario: 'Marta.Usuga', contrasena: 'clave123' });
    req.flush({
      token: 't',
      tipo: 'bearer',
      expira_en: '2026-11-09T20:00:00Z',
      cuenta: {
        id: 2,
        nombre_usuario: 'marta.usuga',
        nombre: 'Marta',
        rol: 'OPERADOR',
        permisos: [],
      },
    });
    expect(navegar).toHaveBeenCalledWith('/consultas/historial');
  });

  it('nunca redirige fuera del sistema con un enlace manipulado', () => {
    montar({ volver: '//sitio-malicioso.example' });
    responderExito();
    expect(navegar).toHaveBeenCalledWith('/');
  });

  function responderExito() {
    c.form.setValue({ usuario: 'marta.usuga', contrasena: 'clave123' });
    c.ingresar();
    http.expectOne('/auth/login').flush({
      token: 't',
      tipo: 'bearer',
      expira_en: '2026-11-09T20:00:00Z',
      cuenta: {
        id: 2,
        nombre_usuario: 'marta.usuga',
        nombre: 'Marta',
        rol: 'OPERADOR',
        permisos: [],
      },
    });
  }

  it('credenciales inválidas: mensaje genérico y borra la contraseña', () => {
    montar();
    responder(401, 'Usuario o contraseña inválidos.');
    expect(texto()).toContain('Usuario o contraseña inválidos.');
    expect(c.form.controls.contrasena.value).toBe('');
    expect(navegar).not.toHaveBeenCalled();
  });

  it('cuenta desactivada: pide contactar al administrador', () => {
    montar();
    responder(403, 'Tu cuenta está desactivada. Contacta al administrador.');
    expect(texto()).toContain('Tu cuenta está desactivada. Contacta al administrador.');
  });

  it('nunca muestra un error técnico (RNF-15)', () => {
    montar();
    responder(500, 'Traceback (most recent call last): psycopg.OperationalError');
    expect(texto()).toContain('No se pudo conectar con el servicio');
    expect(texto()).not.toContain('Traceback');
    responder(422);
    expect(texto()).toContain('Escribe tu usuario y tu contraseña.');
  });

  it('muestra el aviso de sesión vencida o de sesión cerrada', () => {
    montar({ motivo: 'sesion' });
    expect(texto()).toContain('Tu sesión venció o fue cerrada. Ingresa de nuevo.');
  });
});
