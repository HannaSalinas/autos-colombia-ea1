/** Antes del recorrido: espera a que el sistema responda y limpia las capturas de una ejecución anterior. */
import { readdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { RESULTADOS, SALIDA, asegurarCarpetas, variable } from './comun';

export default async function preparar(): Promise<void> {
  const base = process.env.BASE_URL ?? 'http://frontend';
  asegurarCarpetas();
  for (const nombre of readdirSync(SALIDA)) {
    if (/^NF-02_.*\.png$/.test(nombre) || nombre === 'reporte.md') rmSync(join(SALIDA, nombre));
  }
  rmSync(RESULTADOS, { recursive: true, force: true });
  asegurarCarpetas();

  // El backend aplica migraciones y semillas al arrancar: se espera a que el ingreso funcione.
  const usuario = variable('ADMIN_USUARIO');
  const contrasena = variable('ADMIN_CONTRASENA');
  const limite = Date.now() + 180_000;
  let ultimo = '';
  while (Date.now() < limite) {
    try {
      const salud = await fetch(`${base}/health`);
      if (salud.ok) {
        const ingreso = await fetch(`${base}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ usuario, contrasena }),
        });
        if (ingreso.ok) return;
        ultimo = `el ingreso del administrador respondió ${ingreso.status}`;
      } else {
        ultimo = `/health respondió ${salud.status}`;
      }
    } catch {
      ultimo = 'el sistema todavía no responde';
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`El sistema no quedó listo en 3 minutos: ${ultimo}.`);
}
