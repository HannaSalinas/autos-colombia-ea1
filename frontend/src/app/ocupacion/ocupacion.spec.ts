import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Ocupacion } from './ocupacion';

describe('Reporte de ocupación', () => {
  let fixture: ComponentFixture<Ocupacion>;
  let http: HttpTestingController;
  const reporte = {
    generado: '2026-10-23T20:00:00Z',
    celdas: [
      { tipo: 'CARRO', total: 70, ocupadas: 4, libres: 66 },
      { tipo: 'MOTO', total: 10, ocupadas: 1, libres: 9 },
    ],
    dentro: [
      {
        estancia_id: 1,
        placa: 'KLM45D',
        tipo_vehiculo: 'MOTO',
        celda: 'M01',
        entrada: '2026-10-23T15:00:00Z',
        operador_entrada: 'Marta Úsuga (Portería 1)',
        tiempo: '5 h 00 min',
      },
    ],
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Ocupacion],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Ocupacion);
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('muestra celdas libres por tipo y los vehículos dentro con su celda y hora', () => {
    http.expectOne('/reportes/ocupacion').flush(reporte);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(text).toContain('66');
    expect(text).toContain('libres de 70');
    expect(text).toContain('libres de 10');
    expect(text).toContain('KLM45D');
    expect(text).toContain('M01');
    expect(text).toContain('10:00'); // 15:00 UTC = 10:00 en Bogotá
    expect(fixture.componentInstance.porcentaje(4, 70)).toBe(6);
  });

  it('muestra un mensaje si no hay vehículos y permite actualizar', () => {
    http.expectOne('/reportes/ocupacion').flush({ ...reporte, dentro: [] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No hay vehículos dentro');
    fixture.componentInstance.cargar();
    http.expectOne('/reportes/ocupacion').error(new ProgressEvent('error'));
    expect(fixture.componentInstance.error()).toContain('No se pudo cargar');
  });
});
