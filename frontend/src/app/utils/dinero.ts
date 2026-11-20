/**
 * Iteración 3 (RNF-22): pesos colombianos enteros con el formato $ 120.000. Se escribe a mano (sin
 * Intl.NumberFormat, que inserta espacios especiales según el navegador) para que el texto sea
 * exactamente el mismo en Chrome, Edge y Firefox, y el mismo que usa el backend en sus mensajes.
 */
export const formatoPesos = (valor: number): string => {
  const signo = valor < 0 ? '-' : '';
  const digitos = String(Math.trunc(Math.abs(valor)));
  return `${signo}$ ${digitos.replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`;
};
