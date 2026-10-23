/** Quita espacios y guiones y pasa a mayúsculas: ' abc-123 ' -> 'ABC123' (misma regla que el backend). */
export const normalizarPlaca = (placa: string) => placa.replace(/[\s-]+/g, '').toUpperCase();
