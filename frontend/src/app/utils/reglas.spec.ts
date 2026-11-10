import { FormControl } from '@angular/forms';
import {
  normalizarCodigoCelda,
  normalizarUsuario,
  reglaContrasena,
  reglaNombre,
  reglaUsuario,
} from './reglas';

// Mismos valores límite que backend/tests/test_reglas_cuentas_celdas.py (tabla de reglas).
const valida = (regla: typeof reglaUsuario, valor: string) =>
  regla(new FormControl(valor)) === null;

describe('Reglas de cuentas en el navegador (RNF-16)', () => {
  it('usuario: 4 a 30, minúsculas, dígitos, punto y guion bajo', () => {
    for (const ok of ['abcd', 'marta', 'a'.repeat(30), 'marta.usuga', 'diego_2', '  abcd  '])
      expect(valida(reglaUsuario, ok)).toBe(true);
    for (const malo of ['abc', 'a'.repeat(31), '', '    ', 'marta usuga', 'marta-usuga', 'martá'])
      expect(valida(reglaUsuario, malo)).toBe(false);
  });

  it('usuario: se normaliza antes de validar (Marta = marta)', () => {
    expect(normalizarUsuario(' Marta.Usuga ')).toBe('marta.usuga');
    expect(valida(reglaUsuario, ' MARTA ')).toBe(true);
  });

  it('nombre completo: 3 a 80, sin contar los espacios exteriores', () => {
    for (const ok of ['Ana', 'a'.repeat(80), '   Ana  '])
      expect(valida(reglaNombre, ok)).toBe(true);
    for (const malo of ['Al', 'a'.repeat(81), '', '     ', '  Al  '])
      expect(valida(reglaNombre, malo)).toBe(false);
  });

  it('contraseña: 8 a 64, con letra y número, máximo 72 bytes', () => {
    for (const ok of ['clave123', 'a1'.repeat(32), 'contraseña1', ' clave123 '])
      expect(valida(reglaContrasena, ok)).toBe(true);
    for (const malo of ['clave12', 'a1'.repeat(32) + 'x', 'contraseña', '12345678', ''])
      expect(valida(reglaContrasena, malo)).toBe(false);
    const multibyte = 'ñ'.repeat(40) + '1'.repeat(24); // 64 caracteres, 104 bytes
    expect(reglaContrasena(new FormControl(multibyte))).toEqual({
      contrasena: 'La contraseña es demasiado larga: usa menos caracteres especiales.',
    });
  });

  it('código de celda: se normaliza a mayúsculas sin espacios exteriores', () => {
    expect(normalizarCodigoCelda(' c05 ')).toBe('C05');
  });
});
