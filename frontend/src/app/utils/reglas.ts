import { ValidatorFn } from '@angular/forms';

/**
 * Iteración 2: las mismas reglas y límites que backend/app/domain/reglas.py y los CHECK de la base
 * (RNF-16: tres niveles con las mismas reglas). Cada validador devuelve { regla: 'mensaje' }.
 */
export const USUARIO_MINIMO = 4;
export const USUARIO_MAXIMO = 30;
export const NOMBRE_MINIMO = 3;
export const NOMBRE_MAXIMO = 80;
export const CONTRASENA_MINIMA = 8;
export const CONTRASENA_MAXIMA = 64;
export const CONTRASENA_MAXIMA_BYTES = 72;
export const UBICACION_MAXIMA = 60;

/** ' Marta.Usuga ' -> 'marta.usuga' (se normaliza antes de validar, igual que la API). */
export const normalizarUsuario = (usuario: string) => usuario.trim().toLowerCase();
/** ' c05 ' -> 'C05'. */
export const normalizarCodigoCelda = (codigo: string) => codigo.trim().toUpperCase();

const texto = (valor: unknown) => (typeof valor === 'string' ? valor : '');

export const reglaUsuario: ValidatorFn = (c) => {
  const usuario = normalizarUsuario(texto(c.value));
  if (!usuario) return { usuario: 'Escribe el nombre de usuario.' };
  return /^[a-z0-9._]{4,30}$/.test(usuario)
    ? null
    : {
        usuario: `Usa de ${USUARIO_MINIMO} a ${USUARIO_MAXIMO} caracteres: minúsculas, dígitos, punto o guion bajo.`,
      };
};

export const reglaNombre: ValidatorFn = (c) => {
  const nombre = texto(c.value).trim();
  if (!nombre) return { nombre: 'Escribe el nombre completo.' };
  return nombre.length >= NOMBRE_MINIMO && nombre.length <= NOMBRE_MAXIMO
    ? null
    : {
        nombre: `El nombre completo debe tener de ${NOMBRE_MINIMO} a ${NOMBRE_MAXIMO} caracteres.`,
      };
};

export const reglaContrasena: ValidatorFn = (c) => {
  const clave = texto(c.value); // la contraseña no se recorta: los espacios cuentan
  if (!clave) return { contrasena: 'Escribe la contraseña inicial.' };
  // Array.from cuenta caracteres reales (como Python), no unidades UTF-16.
  const largo = Array.from(clave).length;
  if (largo < CONTRASENA_MINIMA || largo > CONTRASENA_MAXIMA)
    return {
      contrasena: `La contraseña debe tener de ${CONTRASENA_MINIMA} a ${CONTRASENA_MAXIMA} caracteres.`,
    };
  if (!/\p{L}/u.test(clave) || !/[0-9]/.test(clave))
    return { contrasena: 'La contraseña debe tener al menos una letra y un número.' };
  if (new TextEncoder().encode(clave).length > CONTRASENA_MAXIMA_BYTES)
    return { contrasena: 'La contraseña es demasiado larga: usa menos caracteres especiales.' };
  return null;
};

/** Primer mensaje de error de un control (o '' si es válido). */
export const mensajeDe = (errores: Record<string, unknown> | null): string => {
  const primero = errores ? Object.values(errores)[0] : null;
  return typeof primero === 'string' ? primero : primero ? 'Revisa este campo.' : '';
};
