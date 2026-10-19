export interface OperadorCrear {
  nombre: string;
  telefono: string;
}
export type OperadorActualizar = Partial<OperadorCrear>;
export interface Operador extends OperadorCrear {
  id: number;
}
export interface OperadoresPagina {
  items: Operador[];
  total: number;
  offset: number;
  limit: number;
}
