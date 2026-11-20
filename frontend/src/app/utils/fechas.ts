/** '2026-11-20' -> '20/11/2026' (fechas de periodos: días de Bogotá que llegan sin hora). */
export const fechaCorta = (iso: string | null | undefined): string =>
  iso ? iso.slice(0, 10).split('-').reverse().join('/') : '—';

/** Instante con hora, mostrado en hora de Colombia (RNF-28), ej. '20 nov 2026, 9:15 a. m.'. */
export const fechaHora = (iso: string | null | undefined): string =>
  iso
    ? new Intl.DateTimeFormat('es-CO', {
        timeZone: 'America/Bogota',
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(iso))
    : '—';

/** Hoy en Bogotá como 'AAAA-MM-DD' (valor por defecto de los filtros de fecha). */
export const hoyBogota = (): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date());
