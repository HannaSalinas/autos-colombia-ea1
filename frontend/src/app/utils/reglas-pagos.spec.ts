import { FormControl } from '@angular/forms';
import { formatoPesos } from './dinero';
import { fechaCorta } from './fechas';
import {
  mensajeReferencia,
  normalizarDocumento,
  reglaCorreo,
  reglaDocumento,
  reglaMeses,
  reglaMotivoAnulacion,
  reglaNombre,
  reglaTarifa,
  reglaTelefono,
} from './reglas';

// Mismos valores límite que backend/tests/test_reglas_pagos.py (tabla de reglas del documento EA3).
type Regla = typeof reglaMeses;
const valida = (regla: Regla, valor: unknown) => regla(new FormControl(valor)) === null;

describe('Iteración 3: formato de dinero y fechas', () => {
  it('pesos enteros con el formato $ 120.000 (RNF-22)', () => {
    expect(formatoPesos(0)).toBe('$ 0');
    expect(formatoPesos(1000)).toBe('$ 1.000');
    expect(formatoPesos(120000)).toBe('$ 120.000');
    expect(formatoPesos(2000000)).toBe('$ 2.000.000');
    expect(formatoPesos(12000000)).toBe('$ 12.000.000');
  });
  it('fechas de periodo como dd/mm/aaaa', () => {
    expect(fechaCorta('2026-12-19')).toBe('19/12/2026');
    expect(fechaCorta(null)).toBe('—');
  });
});

describe('Iteración 3: reglas en el navegador (RNF-16)', () => {
  it('meses: entero de 1 a 6', () => {
    for (const ok of [1, 6, '3']) expect(valida(reglaMeses, ok)).toBe(true);
    for (const malo of [0, 7, 1.5, '', null]) expect(valida(reglaMeses, malo)).toBe(false);
  });
  it('tarifa: entero entre 1.000 y 2.000.000, sin puntos ni decimales', () => {
    for (const ok of ['1000', '2000000', ' 120000 ', 120000])
      expect(valida(reglaTarifa, ok)).toBe(true);
    for (const malo of ['999', '2000001', '1000.5', '120.000', '', '   ', 'abc', '-1000'])
      expect(valida(reglaTarifa, malo)).toBe(false);
  });
  it('referencia: obligatoria de 4 a 30 en transferencia y tarjeta; vacía en efectivo', () => {
    for (const metodo of ['TRANSFERENCIA', 'TARJETA']) {
      for (const ok of ['A1B2', 'x'.repeat(30), 'TRX-2026-01'])
        expect(mensajeReferencia(metodo, ok)).toBe('');
      expect(mensajeReferencia(metodo, '')).toBe(
        'La referencia es obligatoria para transferencia y tarjeta.',
      );
      for (const malo of ['ABC', 'x'.repeat(31), 'con espacio', 'abc_123'])
        expect(mensajeReferencia(metodo, malo)).toContain('de 4 a 30 caracteres');
    }
    expect(mensajeReferencia('EFECTIVO', '')).toBe('');
    expect(mensajeReferencia('EFECTIVO', 'TRX-1234')).toBe(
      'Un pago en efectivo no lleva referencia: deja el campo vacío.',
    );
  });
  it('motivo de anulación: 10 a 200 sin contar espacios exteriores', () => {
    for (const ok of ['a'.repeat(10), 'a'.repeat(200), '  ' + 'a'.repeat(10) + '  '])
      expect(valida(reglaMotivoAnulacion, ok)).toBe(true);
    for (const malo of ['a'.repeat(9), 'a'.repeat(201), '          ', ''])
      expect(valida(reglaMotivoAnulacion, malo)).toBe(false);
  });
  it('documento: 5 a 15 letras o números, normalizado a mayúsculas', () => {
    expect(normalizarDocumento(' ab12345 ')).toBe('AB12345');
    for (const ok of ['12345', '1'.repeat(15), ' pa1234567 '])
      expect(valida(reglaDocumento, ok)).toBe(true);
    for (const malo of ['1234', '1'.repeat(16), '1.234.567', '123 456', ''])
      expect(valida(reglaDocumento, malo)).toBe(false);
  });
  it('nombre del cliente: 3 a 80 (la misma regla de la Iteración 2)', () => {
    for (const ok of ['Ana', 'a'.repeat(80)]) expect(valida(reglaNombre, ok)).toBe(true);
    for (const malo of ['Al', 'a'.repeat(81), '     '])
      expect(valida(reglaNombre, malo)).toBe(false);
  });
  it('teléfono: 10 dígitos', () => {
    expect(valida(reglaTelefono, '3001112233')).toBe(true);
    for (const malo of ['300111223', '30011122334', '300111223a', '300 111 2233', ''])
      expect(valida(reglaTelefono, malo)).toBe(false);
  });
  it('correo: opcional; si se escribe, con formato válido', () => {
    for (const ok of ['', '   ', 'ana@correo.com']) expect(valida(reglaCorreo, ok)).toBe(true);
    for (const malo of ['ana@', 'texto sin arroba', 'ana@correo'])
      expect(valida(reglaCorreo, malo)).toBe(false);
  });
});
