/**
 * Después del recorrido: arma docs/evidencias/rnf20/reporte.md con el navegador, su versión y el
 * resultado de cada pantalla, y comprueba que ningún valor de .env quedó en el reporte ni en los
 * nombres de las capturas.
 */
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  NAVEGADORES,
  PANTALLAS,
  RESULTADOS,
  SALIDA,
  archivo,
  secretos,
  type ResultadoNavegador,
} from './comun';

/** Commit del repositorio, leído de la carpeta .git montada en solo lectura (sin instalar git). */
function commit(): string {
  const git = '/repo-git';
  try {
    const head = readFileSync(join(git, 'HEAD'), 'utf8').trim();
    if (!head.startsWith('ref: ')) return head.slice(0, 7);
    const ref = head.slice(5);
    if (existsSync(join(git, ref))) return readFileSync(join(git, ref), 'utf8').trim().slice(0, 7);
    const empaquetadas = readFileSync(join(git, 'packed-refs'), 'utf8');
    const linea = empaquetadas.split('\n').find((l) => l.endsWith(` ${ref}`));
    return linea ? linea.slice(0, 7) : 'no disponible';
  } catch {
    return 'no disponible';
  }
}

export default async function reporte(): Promise<void> {
  const orden = ['chrome', 'edge', 'firefox'];
  const resultados: ResultadoNavegador[] = orden
    .filter((n) => existsSync(join(RESULTADOS, `${n}.json`)))
    .map((n) => JSON.parse(readFileSync(join(RESULTADOS, `${n}.json`), 'utf8')));
  const fecha = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Bogota', dateStyle: 'short', timeStyle: 'short',
  }).format(new Date());
  const todas = resultados.flatMap((r) => r.pantallas);
  const cumple = resultados.length === orden.length && todas.length > 0 && todas.every((p) => p.estado === 'Sí');

  const lineas = [
    '# Evidencia de RNF-20: compatibilidad de navegadores (caso NF-02)',
    '',
    `Pruebas de extremo a extremo con Playwright 1.64.1 dentro de Docker, el ${fecha} (hora de`,
    `Bogotá), sobre el commit \`${commit()}\`. Comando: \`docker compose --profile e2e run --rm --build e2e\`.`,
    'Cada pantalla se verifica (textos, menús y botones esperados) antes de capturarla, y el recorrido',
    'no modifica datos: las confirmaciones se cancelan y la cuenta "abc" no llega a enviarse.',
    'Los navegadores corren sin ventana (modo headless), con una ventana de 1280 × 900 px; por eso su',
    'identificación dice "HeadlessChrome". La página que dibujan es la misma que con ventana.',
    '',
    '## Navegadores',
    '',
    '| Navegador | Motor | Versión | Aclaración |',
    '| --- | --- | --- | --- |',
    ...orden.map((n) => {
      const r = resultados.find((x) => x.navegador === n);
      const d = NAVEGADORES[n];
      return `| ${d.nombre} | ${d.motor} | ${r ? r.version : 'no se ejecutó'} | ${d.aclaracion} |`;
    }),
    '',
    'Identificación que envía cada navegador (user agent), como prueba de cuál se ejecutó:',
    '',
    ...orden.map((n) => {
      const r = resultados.find((x) => x.navegador === n);
      return `- ${NAVEGADORES[n].nombre}: \`${r ? r.agente : 'no se ejecutó'}\``;
    }),
    '',
    '## Resultado por pantalla',
    '',
    `| Pantalla | ${orden.map((n) => NAVEGADORES[n].nombre.split(' (')[0]).join(' | ')} |`,
    `| --- | ${orden.map(() => '---').join(' | ')} |`,
    ...PANTALLAS.map(([numero, clave, titulo]) => {
      const celdas = orden.map((n) => {
        const p = resultados.find((x) => x.navegador === n)?.pantallas.find((y) => y.numero === numero);
        if (!p) return 'no se ejecutó';
        const enlace = `[captura](${archivo(n, numero, clave)})`;
        return p.estado === 'Sí' ? `Sí · ${enlace}` : `**${p.estado}**${p.estado === 'No' ? ` · ${enlace}` : ''}`;
      });
      return `| ${numero} · ${titulo} | ${celdas.join(' | ')} |`;
    }),
    '',
    `**Resultado: ${cumple ? 'las 10 pantallas funcionan en los tres navegadores' : 'hay pantallas que no funcionan o no se ejecutaron (ver detalle)'}.**`,
    '',
  ];
  // Capturas idénticas entre navegadores: se explican en vez de ocultarlas.
  const huella = (n: string, numero: string, clave: string) => {
    const ruta = join(SALIDA, archivo(n, numero, clave));
    return existsSync(ruta) ? createHash('sha256').update(readFileSync(ruta)).digest('hex') : '';
  };
  const iguales = PANTALLAS.filter(([numero, clave]) => {
    const a = huella('chrome', numero, clave);
    return a !== '' && a === huella('edge', numero, clave);
  }).length;
  if (iguales) {
    lineas.push(
      '## Capturas idénticas entre Chrome y Edge',
      '',
      `${iguales} de las 10 capturas de Chrome y de Edge son idénticas byte por byte. Es lo esperado: los`,
      'dos navegadores usan el mismo motor (Chromium) y las mismas fuentes del contenedor, y la captura es',
      'del contenido de la página, no de la ventana del navegador. Que sí se ejecutaron navegadores',
      'distintos lo muestran la versión y la identificación (user agent) de la tabla de navegadores.',
      '',
    );
  }
  const fallos = resultados.flatMap((r) =>
    r.pantallas.filter((p) => p.estado === 'No').map((p) => `- ${NAVEGADORES[r.navegador].nombre}, pantalla ${p.numero}: ${p.detalle}`),
  );
  if (fallos.length) lineas.push('## Detalle de los fallos', '', ...fallos, '');
  lineas.push(
    'Las contraseñas se toman de `.env` a través de Docker Compose: no aparecen en el código, en las',
    'capturas (los campos de contraseña muestran puntos) ni en este reporte. Al terminar, el propio',
    'recorrido comprueba que ningún valor de `.env` quedó en el reporte ni en los nombres de los archivos.',
    '',
  );
  const texto = lineas.join('\n');

  // Comprobación final: ningún secreto en el reporte ni en los nombres de las capturas.
  const nombres = readdirSync(SALIDA).join('\n');
  const filtrado = secretos().filter((s) => texto.includes(s) || nombres.includes(s));
  if (filtrado.length) throw new Error('Un valor de .env aparece en el reporte o en los archivos: no se guarda el reporte.');
  writeFileSync(join(SALIDA, 'reporte.md'), texto);
  console.log(`Reporte: docs/evidencias/rnf20/reporte.md · ${cumple ? 'todo funciona' : 'HAY FALLOS'}`);
}
