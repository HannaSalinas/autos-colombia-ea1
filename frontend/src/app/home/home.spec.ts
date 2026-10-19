import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Home as App } from './home';

describe('App', () => {
  let fixture: ComponentFixture<App>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(App);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function healthRequest() {
    return http.expectOne({ method: 'GET', url: '/health' });
  }

  function statusText() {
    fixture.detectChanges();
    return (fixture.nativeElement as HTMLElement)
      .querySelector('[role="status"]')
      ?.textContent?.trim();
  }

  it('muestra el nombre y la descripción de Autos Colombia', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('h1')?.textContent).toBe('Autos Colombia');
    expect(element.querySelector('.description')?.textContent).toBe(
      'Control de entradas y salidas de vehículos',
    );
    healthRequest().flush({ status: 'ok' });
  });

  it('muestra el estado de comprobación mientras espera la respuesta', () => {
    expect(statusText()).toBe('Comprobando conexión…');
    healthRequest().flush({ status: 'ok' });
  });

  it('muestra el servicio disponible cuando la API responde ok', () => {
    healthRequest().flush({ status: 'ok' });
    expect(statusText()).toBe('Servicio disponible');
  });

  it('muestra el error cuando el servidor falla', () => {
    healthRequest().flush({}, { status: 503, statusText: 'Service Unavailable' });
    expect(statusText()).toBe('No se pudo conectar con el servicio');
  });

  it('muestra el error cuando no hay conexión de red', () => {
    healthRequest().error(new ProgressEvent('error'));
    expect(statusText()).toBe('No se pudo conectar con el servicio');
  });

  it('no considera disponible una respuesta inesperada', () => {
    healthRequest().flush(null);
    expect(statusText()).toBe('No se pudo conectar con el servicio');
  });
});
