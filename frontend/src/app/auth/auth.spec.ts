import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  UrlTree,
  provideRouter,
} from '@angular/router';
import { Observable, firstValueFrom } from 'rxjs';
import { CuentaSesion } from '../models/auth';
import { accesoGuard, ingresoGuard } from './acceso.guard';
import { authInterceptor } from './auth.interceptor';
import { AuthService, CLAVE_TOKEN } from './auth.service';

const CUENTA: CuentaSesion = {
  id: 2,
  nombre_usuario: 'marta.usuga',
  nombre: 'Marta Úsuga (Portería 1)',
  rol: 'OPERADOR',
  permisos: ['celdas:ver', 'consultas', 'estancias', 'vehiculos:ver'],
};

describe('Sesión en el navegador (Iteración 2)', () => {
  let http: HttpTestingController;
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });
  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  const ingresar = () => {
    auth.login('marta.usuga', 'clave123').subscribe();
    http.expectOne('/auth/login').flush({
      token: 't-123',
      tipo: 'bearer',
      expira_en: '2026-11-09T20:00:00Z',
      cuenta: CUENTA,
    });
  };

  describe('AuthService', () => {
    it('al ingresar guarda el token en sessionStorage y la cuenta en una señal', () => {
      auth.login('marta.usuga', 'clave123').subscribe();
      const req = http.expectOne('/auth/login');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ usuario: 'marta.usuga', contrasena: 'clave123' });
      expect(req.request.headers.has('Authorization')).toBe(false);
      req.flush({
        token: 't-123',
        tipo: 'bearer',
        expira_en: '2026-11-09T20:00:00Z',
        cuenta: CUENTA,
      });
      expect(sessionStorage.getItem(CLAVE_TOKEN)).toBe('t-123');
      expect(localStorage.getItem(CLAVE_TOKEN)).toBeNull();
      expect(auth.cuenta()).toEqual(CUENTA);
      expect(auth.autenticado()).toBe(true);
    });

    it('si el ingreso falla no guarda nada', () => {
      auth.login('marta.usuga', 'mala').subscribe({ error: () => undefined });
      http
        .expectOne('/auth/login')
        .flush({ detail: 'Usuario o contraseña inválidos.' }, { status: 401, statusText: 'x' });
      expect(sessionStorage.getItem(CLAVE_TOKEN)).toBeNull();
      expect(auth.cuenta()).toBeNull();
    });

    it('tiene() responde según la lista de permisos que envió el servidor', () => {
      expect(auth.tiene('estancias')).toBe(false);
      auth.cuenta.set(CUENTA);
      expect(auth.tiene('estancias')).toBe(true);
      expect(auth.tiene('celdas:gestionar')).toBe(false);
      expect(auth.tiene('cuentas:gestionar')).toBe(false);
    });

    it('al recargar la página recupera la cuenta con GET /auth/yo', async () => {
      sessionStorage.setItem(CLAVE_TOKEN, 't-123');
      const resultado = firstValueFrom(auth.restaurar());
      const req = http.expectOne('/auth/yo');
      expect(req.request.headers.get('Authorization')).toBe('Bearer t-123');
      req.flush(CUENTA);
      expect(await resultado).toBe(true);
      expect(auth.cuenta()).toEqual(CUENTA);
    });

    it('sin token no pregunta al servidor', async () => {
      expect(await firstValueFrom(auth.restaurar())).toBe(false);
      http.expectNone('/auth/yo');
    });

    it('sessionStorage manda: si otra página de la pestaña cerró la sesión, no queda token', () => {
      ingresar();
      sessionStorage.removeItem(CLAVE_TOKEN);
      expect(auth.token()).toBeNull();
    });

    it('al volver desde la caché del navegador descarta la cuenta en memoria y revalida', async () => {
      ingresar();
      sessionStorage.removeItem(CLAVE_TOKEN); // la sesión se cerró en otra página
      expect(await firstValueFrom(auth.revalidar())).toBe(false);
      expect(auth.cuenta()).toBeNull();
      http.expectNone('/auth/yo');
    });

    it('al volver desde la caché con token vigente, lo confirma con el servidor', async () => {
      ingresar();
      const resultado = firstValueFrom(auth.revalidar());
      http.expectOne('/auth/yo').flush(CUENTA);
      expect(await resultado).toBe(true);
      expect(auth.cuenta()).toEqual(CUENTA);
    });

    it('cerrar sesión avisa al servidor y borra todo, aunque el servidor no responda', () => {
      ingresar();
      auth.cerrarSesion().subscribe();
      const req = http.expectOne('/auth/cerrar-sesion');
      expect(req.request.headers.get('Authorization')).toBe('Bearer t-123');
      req.error(new ProgressEvent('error'));
      expect(auth.cuenta()).toBeNull();
      expect(sessionStorage.getItem(CLAVE_TOKEN)).toBeNull();
    });
  });

  describe('Interceptor', () => {
    it('agrega el token a las solicitudes a la API', () => {
      ingresar();
      TestBed.inject(HttpClient).get('/celdas').subscribe();
      expect(http.expectOne('/celdas').request.headers.get('Authorization')).toBe('Bearer t-123');
    });

    it('un 401 borra la sesión y lleva al ingreso con aviso', () => {
      const navegar = vi.spyOn(router, 'navigate').mockResolvedValue(true);
      ingresar();
      TestBed.inject(HttpClient)
        .get('/celdas')
        .subscribe({ error: () => undefined });
      http.expectOne('/celdas').flush({ detail: 'x' }, { status: 401, statusText: 'x' });
      expect(auth.cuenta()).toBeNull();
      expect(sessionStorage.getItem(CLAVE_TOKEN)).toBeNull();
      expect(navegar).toHaveBeenCalledWith(['/ingresar'], { queryParams: { motivo: 'sesion' } });
    });

    it('un 403 no cierra la sesión', () => {
      const navegar = vi.spyOn(router, 'navigate').mockResolvedValue(true);
      ingresar();
      TestBed.inject(HttpClient)
        .post('/celdas', {})
        .subscribe({ error: () => undefined });
      http.expectOne('/celdas').flush({ detail: 'x' }, { status: 403, statusText: 'x' });
      expect(auth.cuenta()).toEqual(CUENTA);
      expect(navegar).not.toHaveBeenCalled();
    });

    it('el 401 del propio ingreso lo maneja su pantalla (no redirige)', () => {
      const navegar = vi.spyOn(router, 'navigate').mockResolvedValue(true);
      auth.login('x', 'y').subscribe({ error: () => undefined });
      http.expectOne('/auth/login').flush({}, { status: 401, statusText: 'x' });
      expect(navegar).not.toHaveBeenCalled();
    });
  });

  describe('Guards', () => {
    const correr = (guard: typeof accesoGuard, permiso?: string, url = '/control-acceso') => {
      const ruta = { data: permiso ? { permiso } : {} } as unknown as ActivatedRouteSnapshot;
      const estado = { url } as RouterStateSnapshot;
      return TestBed.runInInjectionContext(
        () => guard(ruta, estado) as Observable<boolean | UrlTree>,
      );
    };
    const texto = (r: boolean | UrlTree) => (r instanceof UrlTree ? router.serializeUrl(r) : r);

    it('sin sesión lleva al ingreso recordando a dónde quería ir', async () => {
      expect(texto(await firstValueFrom(correr(accesoGuard)))).toBe(
        '/ingresar?volver=%2Fcontrol-acceso',
      );
    });

    it('con sesión y el permiso de la ruta deja pasar', async () => {
      auth.cuenta.set(CUENTA);
      expect(await firstValueFrom(correr(accesoGuard, 'estancias'))).toBe(true);
    });

    it('sin el permiso de la ruta vuelve al inicio', async () => {
      auth.cuenta.set(CUENTA);
      expect(texto(await firstValueFrom(correr(accesoGuard, 'cuentas:gestionar')))).toBe('/');
    });

    it('después de cerrar sesión (botón atrás) vuelve a pedir ingresar', async () => {
      ingresar();
      auth.cerrarSesion().subscribe();
      http.expectOne('/auth/cerrar-sesion').flush(null, { status: 204, statusText: 'x' });
      expect(texto(await firstValueFrom(correr(accesoGuard)))).toContain('/ingresar');
    });

    it('la pantalla de ingreso no se muestra a quien ya tiene sesión', async () => {
      auth.cuenta.set(CUENTA);
      expect(texto(await firstValueFrom(correr(ingresoGuard)))).toBe('/');
      auth.cuenta.set(null);
      expect(await firstValueFrom(correr(ingresoGuard))).toBe(true);
    });
  });
});
