/**
 * Ejecución del plan de pruebas PP-02 (EA2). Recorre los casos en orden de dependencias (no en el del
 * Excel): por ejemplo, US-20 va antes de US-16 para que operador_prueba tenga movimientos, y PE-05
 * después de CE-11 para que exista una celda inhabilitada. CE-17, NF-01 y NF-02, y la parte pytest de
 * US-13, US-19 y CE-13, los completa el orquestador (scripts/ejecutar_plan_pruebas.sh).
 */
import { test } from '@playwright/test';
import { cerrarBd, cerrarContextos, conectarBd, ejecutarCaso, guardarResultados, resultados } from './contexto';
import { E, preparar } from './escenario';
import { CASOS_USUARIOS } from './casos_usuarios';
import { CASOS_PERMISOS_CELDAS } from './casos_permisos_celdas';

const ORDEN = [
  'US-01', 'US-02', 'US-03', 'US-04', 'US-05', 'US-06', 'US-07', 'US-08', 'US-09', 'US-10', 'US-11', 'US-12',
  'US-13', 'US-14', 'US-15', 'US-20', 'US-16', 'US-17', 'US-18', 'US-19',
  'PE-01', 'PE-02', 'PE-03', 'PE-04',
  'CE-01', 'CE-02', 'CE-03', 'CE-04', 'CE-05', 'CE-06', 'CE-07', 'CE-08', 'CE-09', 'CE-10', 'CE-11',
  'PE-05', 'CE-12', 'CE-13', 'CE-14', 'CE-15', 'CE-16',
];
const CASOS = { ...CASOS_USUARIOS, ...CASOS_PERMISOS_CELDAS };

test('Plan de pruebas PP-02 (casos US, PE y CE)', async ({ browser }) => {
  await conectarBd();
  E.inicio = new Date();
  const prep = await ejecutarCaso('PREPARACION', () => preparar());
  for (const id of ORDEN) {
    await test.step(id, async () => {
      if (prep.estado !== 'Aprobado') {
        resultados.push({
          id, estado: 'Bloqueado', resultado: `No se pudo preparar el conjunto de prueba: ${prep.resultado}`,
          incidencia: `INC-${id}: preparación fallida (${prep.incidencia})`, evidencias: ['PREPARACION_api.json'], fecha: new Date().toISOString(),
        });
        return;
      }
      const r = await ejecutarCaso(id, (c) => CASOS[id](c, browser));
      console.log(`${r.id}: ${r.estado}${r.incidencia ? ` — ${r.incidencia}` : ''}`);
    });
  }
  guardarResultados();
  await cerrarContextos();
  await cerrarBd();
});
