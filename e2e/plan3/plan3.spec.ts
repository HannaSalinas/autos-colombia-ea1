/**
 * Ejecución del plan de pruebas PP-03 (EA3). Recorre los casos en orden de dependencias, no en el del
 * Excel: por ejemplo, ME-01 y ME-02 van antes de los pagos que cambian el estado de V-VIG, V-VENC y
 * V-SIN, y ME-04, AN-04 y PA-12 después de AN-01. PA-03 (pruebas de la regla de fechas), NF-01 y NF-02,
 * y la parte pytest de CL-04 y PA-08, los completa el orquestador (scripts/ejecutar_plan_pruebas_ea3.sh).
 */
import { test } from '@playwright/test';
import { cerrarBd, cerrarContextos, conectarBd, ejecutarCaso, guardarResultados, resultados } from '../plan/contexto';
import { E, preparar, VEHICULOS } from './escenario';
import { cerrarPantallas } from './pantalla';
import { CASOS_TARIFAS_CLIENTES } from './casos_tarifas_clientes';
import { CASOS_PAGOS } from './casos_pagos';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { SALIDA } from '../plan/contexto';

const ORDEN = [
  'TA-01', 'TA-02', 'TA-03', 'TA-04', 'TA-06',
  'CL-01', 'CL-02', 'CL-03', 'CL-04', 'CL-05', 'CL-06',
  'ME-05', 'ME-01', 'ME-02', 'ME-03',
  'PA-07', 'PA-04', 'PA-05', 'PA-06', 'PA-01', 'TA-05', 'PA-02', 'PA-08', 'PA-09', 'PA-10',
  'AN-01', 'ME-04', 'AN-04', 'AN-02', 'AN-03', 'AN-05', 'AN-06',
  'PA-11', 'PA-12', 'PA-13', 'RE-01', 'RE-02', 'RE-03', 'RE-04', 'PE-01',
];
const CASOS = { ...CASOS_TARIFAS_CLIENTES, ...CASOS_PAGOS };

test('Plan de pruebas PP-03 (casos TA, CL, ME, PA, AN, RE y PE)', async ({ browser }) => {
  await conectarBd();
  E.inicio = new Date();
  const prep = await ejecutarCaso('PREPARACION', () => preparar());
  // Placas reales de los vehículos de prueba (hoja Plan, B29: V-SIN, V-VENC, V-VIG y V-FUT).
  writeFileSync(join(SALIDA, 'vehiculos.json'), JSON.stringify({ hoy_bogota: E.hoy, vehiculos: VEHICULOS }, null, 2) + '\n');
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
      await cerrarPantallas();
      console.log(`${r.id}: ${r.estado}${r.incidencia ? ` — ${r.incidencia}` : ''}`);
    });
  }
  guardarResultados();
  await cerrarContextos();
  await cerrarBd();
});
