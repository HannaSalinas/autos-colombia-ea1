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

// --- Iteración 3: pagos, tarifas y clientes. Mismos límites y mensajes que
// backend/app/domain/pagos.py y los CHECK de las migraciones 0009 y 0010 (RNF-16). ---
export const MESES_MINIMO = 1;
export const MESES_MAXIMO = 6;
export const TARIFA_MINIMA = 1000;
export const TARIFA_MAXIMA = 2000000;
export const REFERENCIA_MINIMA = 4;
export const REFERENCIA_MAXIMA = 30;
export const MOTIVO_ANULACION_MINIMO = 10;
export const MOTIVO_ANULACION_MAXIMO = 200;
export const DOCUMENTO_MINIMO = 5;
export const DOCUMENTO_MAXIMO = 15;

/** ' ab12345 ' -> 'AB12345' (se normaliza antes de validar, igual que la API). */
export const normalizarDocumento = (documento: string) => documento.trim().toUpperCase();

export const reglaMeses: ValidatorFn = (c) => {
  const meses = Number(c.value);
  return Number.isInteger(meses) && meses >= MESES_MINIMO && meses <= MESES_MAXIMO
    ? null
    : { meses: `Los meses deben ser un número entero de ${MESES_MINIMO} a ${MESES_MAXIMO}.` };
};

/** La tarifa se escribe solo con dígitos: 120000. Sin puntos ni decimales (1000.5 no es válido). */
export const reglaTarifa: ValidatorFn = (c) => {
  const valor = texto(c.value).trim() || (typeof c.value === 'number' ? String(c.value) : '');
  if (!valor) return { tarifa: 'Escribe el valor mensual en pesos.' };
  const numero = Number(valor);
  return /^[0-9]+$/.test(valor) && numero >= TARIFA_MINIMA && numero <= TARIFA_MAXIMA
    ? null
    : {
        tarifa:
          'La tarifa debe ser un valor entero en pesos, sin decimales, entre $ 1.000 y $ 2.000.000.',
      };
};

/** Obligatoria para TRANSFERENCIA y TARJETA (4 a 30 letras, números o guion); vacía en EFECTIVO. */
export const mensajeReferencia = (metodo: string, referencia: unknown): string => {
  const valor = texto(referencia).trim();
  if (metodo === 'EFECTIVO')
    return valor ? 'Un pago en efectivo no lleva referencia: deja el campo vacío.' : '';
  if (!valor) return 'La referencia es obligatoria para transferencia y tarjeta.';
  return /^[A-Za-z0-9-]{4,30}$/.test(valor)
    ? ''
    : `La referencia debe tener de ${REFERENCIA_MINIMA} a ${REFERENCIA_MAXIMA} caracteres: letras, números o guion.`;
};

export const reglaMotivoAnulacion: ValidatorFn = (c) => {
  const motivo = texto(c.value).trim();
  if (!motivo) return { motivo: 'El motivo de la anulación es obligatorio.' };
  return motivo.length >= MOTIVO_ANULACION_MINIMO && motivo.length <= MOTIVO_ANULACION_MAXIMO
    ? null
    : {
        motivo: `El motivo debe tener de ${MOTIVO_ANULACION_MINIMO} a ${MOTIVO_ANULACION_MAXIMO} caracteres.`,
      };
};

export const reglaDocumento: ValidatorFn = (c) => {
  const documento = normalizarDocumento(texto(c.value));
  if (!documento) return { documento: 'Escribe el número de documento.' };
  return /^[A-Z0-9]{5,15}$/.test(documento)
    ? null
    : {
        documento: `El número de documento debe tener de ${DOCUMENTO_MINIMO} a ${DOCUMENTO_MAXIMO} caracteres: letras y números, sin espacios ni puntos.`,
      };
};

export const reglaTelefono: ValidatorFn = (c) => {
  const telefono = texto(c.value).trim();
  if (!telefono) return { telefono: 'Escribe el teléfono.' };
  return /^[0-9]{10}$/.test(telefono)
    ? null
    : { telefono: 'El teléfono debe tener 10 dígitos, sin espacios ni otros caracteres.' };
};

/** Opcional. La misma expresión del CHECK ck_cliente_correo_formato. */
export const reglaCorreo: ValidatorFn = (c) => {
  const correo = texto(c.value).trim();
  if (!correo) return null;
  return /^[^@\s]+@[^@\s]+[.][^@\s]+$/.test(correo)
    ? null
    : { correo: 'El correo no tiene un formato válido (ej. ana@correo.com).' };
};
