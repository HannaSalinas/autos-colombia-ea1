export interface Cliente {
  id: number;
  documento: string;
  nombre: string;
  telefono: string;
  correo: string | null;
}
export interface ClientesPagina {
  items: Cliente[];
  total: number;
  offset: number;
  limit: number;
}
