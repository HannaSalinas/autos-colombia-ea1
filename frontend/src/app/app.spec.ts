import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { App } from './app';
import { AuthService } from './auth/auth.service';
import { CuentaSesion } from './models/auth';

// Permisos tal como los envía el backend (app/domain/permisos.py).
const OPERADOR: CuentaSesion = {
  id: 2,
  nombre_usuario: 'marta.usuga',
  nombre: 'Marta Úsuga (Portería 1)',
  rol: 'OPERADOR',
  permisos: ['celdas:ver', 'consultas', 'estancias', 'vehiculos:ver'],
};
const ADMINISTRADOR: CuentaSesion = {
  id: 1,
  nombre_usuario: 'admin',
  nombre: 'Sandra Patiño',
  rol: 'ADMINISTRADOR',
  permisos: [
    'celdas:gestionar',
    'celdas:ver',
    'consultas',
    'cuentas:gestionar',
    'estancias',
    'vehiculos:gestionar',
    'vehiculos:ver',
  ],
};

describe('Navegación', () => {
  let auth: AuthService;

  const montar = (cuenta: CuentaSesion | null) => {
    auth.cuenta.set(cuenta);
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    return fixture;
  };
  const enlaces = (el: HTMLElement) =>
    [...el.querySelectorAll('nav a')].map((a) => a.textContent?.trim());

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    auth = TestBed.inject(AuthService);
  });

  it('ofrece acceso a la gestión de vehículos', () => {
    // Iteración 2: el menú aparece con una sesión iniciada.
    const fixture = montar(ADMINISTRADOR);
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('a[href="/gestion/vehiculos"]')
        ?.textContent,
    ).toBe('Vehículos');
  });

  it('sin sesión no muestra menú ni cuenta', () => {
    const el = montar(null).nativeElement as HTMLElement;
    expect(el.querySelector('nav')).toBeNull();
    expect(el.textContent).not.toContain('Cerrar sesión');
  });

  it('el Operador ve solo las opciones de su lista de permisos', () => {
    const el = montar(OPERADOR).nativeElement as HTMLElement;
    expect(enlaces(el)).toEqual([
      'Inicio',
      'Control de acceso',
      'Ocupación',
      'Historial',
      'Vehículos',
      'Celdas',
    ]);
    expect(el.textContent).not.toContain('Operadores');
    expect(el.textContent).not.toContain('Cuentas de usuario'); // HU-16.1
    expect(el.textContent).toContain('Marta Úsuga (Portería 1)');
    expect(el.textContent).toContain('Operador · marta.usuga');
  });

  it('el Administrador ve todas las opciones', () => {
    const el = montar(ADMINISTRADOR).nativeElement as HTMLElement;
    expect(enlaces(el)).toEqual([
      'Inicio',
      'Control de acceso',
      'Ocupación',
      'Historial',
      'Vehículos',
      'Celdas',
      'Cuentas de usuario',
    ]);
    expect(el.textContent).toContain('Administrador · admin');
  });

  it('el menú cambia solo cuando cambia la cuenta (señales)', () => {
    const fixture = montar(ADMINISTRADOR);
    auth.cuenta.set(null);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('nav')).toBeNull();
  });

  it('cerrar sesión avisa al servidor, borra la sesión y vuelve al ingreso sin historial', () => {
    const http = TestBed.inject(HttpTestingController);
    const router = TestBed.inject(Router);
    const navegar = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    sessionStorage.setItem('autos-colombia.token', 'token-de-prueba');
    const fixture = montar(OPERADOR);
    const boton = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Cerrar sesión'),
    )!;
    boton.click();
    http.expectOne({ method: 'POST', url: '/auth/cerrar-sesion' }).flush(null, {
      status: 204,
      statusText: 'No Content',
    });
    expect(auth.cuenta()).toBeNull();
    expect(sessionStorage.getItem('autos-colombia.token')).toBeNull();
    expect(navegar).toHaveBeenCalledWith(['/ingresar'], {
      queryParams: { motivo: 'salida' },
      replaceUrl: true,
    });
    http.verify();
  });

  it('si el botón atrás devuelve una página guardada (bfcache) sin sesión, va al ingreso', () => {
    const router = TestBed.inject(Router);
    const navegar = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    montar(OPERADOR); // la página tenía la cuenta en memoria, pero ya no hay token
    const evento = new Event('pageshow') as PageTransitionEvent;
    Object.defineProperty(evento, 'persisted', { value: true });
    window.dispatchEvent(evento);
    expect(auth.cuenta()).toBeNull();
    expect(navegar).toHaveBeenCalledWith(['/ingresar'], { replaceUrl: true });
  });

  it('una carga normal de la página no revalida', () => {
    const router = TestBed.inject(Router);
    const navegar = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    montar(OPERADOR);
    window.dispatchEvent(new Event('pageshow'));
    expect(auth.cuenta()).toEqual(OPERADOR);
    expect(navegar).not.toHaveBeenCalled();
  });
});
