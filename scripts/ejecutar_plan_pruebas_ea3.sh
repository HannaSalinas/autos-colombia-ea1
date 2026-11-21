#!/usr/bin/env bash
# Ejecución automatizada del plan de pruebas de la EA3 (PP-03) contra el sistema real.
#
#   scripts/ejecutar_plan_pruebas_ea3.sh
#
# 1. Recrea la base desde cero (docker compose down -v y up --build): solo las semillas.
# 2. Ejecuta los casos TA, CL, ME, PA, AN, RE y PE con Playwright (servicio plan-pruebas-ea3):
#    pantalla, API y base. Los datos de prueba se crean por la API (los periodos de V-VIG, V-VENC y
#    V-FUT, por SQL: ver e2e/plan3/escenario.ts).
# 3. Ejecuta las pruebas automatizadas de la regla de fechas (PA-03) y de concurrencia (CL-04 y PA-08).
# 4. NF-02 y NF-01 sobre otra base recién creada: primero el recorrido de RNF-26 en los tres
#    navegadores (no modifica datos) y después la medición de RNF-25 (deja pagos de medición).
# 5. Completa los resultados, busca secretos en las evidencias y escribe el reporte.
# 6. Deja la base limpia otra vez (docker compose down -v).
#
# Evidencias: docs/pruebas/evidencias-ea3/ (una o más por caso, con su ID). Resumen: docs/pruebas/reporte-ea3.md.
# Después de hacer commit de las evidencias, el Excel se llena con:
#   python3 scripts/plan_pruebas_ea3.py excel <commit-de-las-evidencias> <ruta-del-excel>
set -euo pipefail
cd "$(dirname "$0")/.."
EVIDENCIAS=docs/pruebas/evidencias-ea3

[ -f .env ] || { echo "Falta .env (ver .env.example)"; exit 1; }
if [ -z "${PLAN_PERMITIR_CAMBIOS:-}" ] && [ -n "$(git status --porcelain)" ]; then
  echo "Hay cambios sin confirmar: la evidencia debe corresponder a un commit. (Para una prueba local: PLAN_PERMITIR_CAMBIOS=1)"
  exit 1
fi
export COMMIT_PROBADO; COMMIT_PROBADO="$(git rev-parse --short HEAD)"
hora() { TZ=America/Bogota date '+%Y-%m-%d %H:%M'; }
INICIO="$(hora)"

base_limpia() {
  docker compose --profile plan --profile e2e --profile test down -v --remove-orphans >/dev/null 2>&1 || true
  docker compose up -d --build db backend frontend
  for _ in $(seq 1 90); do curl -sf http://localhost:4200/health >/dev/null && break; sleep 2; done
  curl -sf http://localhost:4200/health >/dev/null || { echo "La API no respondió"; exit 1; }
}

echo "== 1. Base limpia y sistema arriba (commit $COMMIT_PROBADO)"
base_limpia

rm -rf "$EVIDENCIAS" && mkdir -p "$EVIDENCIAS"
echo "== 2. Casos TA, CL, ME, PA, AN, RE y PE (Playwright, Google Chrome)"
docker compose --profile plan run --rm --build plan-pruebas-ea3 || echo "(Playwright terminó con error: se registra en resultados.json)"

echo "== 3. Pruebas automatizadas: regla de fechas (PA-03) y concurrencia (CL-04 y PA-08)"
declare -A PRUEBAS=(
  [PA-03]="tests/test_reglas_pagos.py -k 'fin_de_periodo or encadenados or n_meses or inicio_de_periodo or tope_de_adelanto'"
  [CL-04]="tests/test_clientes_postgres.py::test_dos_registros_simultaneos_del_mismo_documento_dejan_uno"
  [PA-08]="tests/test_pagos_concurrencia_postgres.py::test_dos_pagos_simultaneos_del_mismo_vehiculo_dan_periodos_consecutivos"
)
docker compose build backend-tests >/dev/null
for caso in PA-03 CL-04 PA-08; do
  {
    echo "# $caso · $(hora) (Bogotá) · commit $COMMIT_PROBADO"
    echo "# docker compose run --rm backend-tests ... python -m pytest -v ${PRUEBAS[$caso]}"
    if [ "$caso" = PA-03 ]; then
      echo "# Ejemplos del documento en la parametrización de test_fin_de_periodo (backend/tests/test_reglas_pagos.py):"
      grep -n "ejemplo del documento" backend/tests/test_reglas_pagos.py | sed 's/^/#   /'
    fi
    docker compose run --rm backend-tests sh -c "python -m alembic -c alembic.ini upgrade head >/dev/null && python -m pytest -v -p no:cacheprovider ${PRUEBAS[$caso]}" 2>&1 \
      | sed 's/\x1b\[[0-9;]*m//g; s/[[:space:]]*$//' || true
  } > "$EVIDENCIAS/${caso}_pytest.txt"
  tail -1 "$EVIDENCIAS/${caso}_pytest.txt"
done
docker compose --profile test rm -sf db-test >/dev/null 2>&1 || true

echo "== 4. NF-02 (RNF-26) y NF-01 (RNF-25) sobre otra base recién creada"
base_limpia
docker compose --profile e2e run --rm --build e2e-rnf26 || echo "(el recorrido de RNF-26 terminó con error: se registra en su reporte)"
backend/.venv/bin/python scripts/medir_rnf25.py | tee "$EVIDENCIAS/NF-01_medicion.txt" || echo "(la medición de RNF-25 terminó con error)"

FIN="$(hora)"
printf '{\n  "commit_probado": "%s",\n  "inicio": "%s",\n  "fin": "%s",\n  "entorno": "Docker Compose local: frontend y API en http://localhost:4200 (API a través de nginx); base recreada con docker compose down -v"\n}\n' \
  "$COMMIT_PROBADO" "$INICIO" "$FIN" > "$EVIDENCIAS/ejecucion.json"

echo "== 5. Resultados, búsqueda de secretos y reporte"
python3 scripts/plan_pruebas_ea3.py completar

echo "== 6. Base limpia (docker compose down -v)"
docker compose --profile plan --profile e2e --profile test down -v >/dev/null 2>&1
echo "Listo: $EVIDENCIAS y docs/pruebas/reporte-ea3.md"
