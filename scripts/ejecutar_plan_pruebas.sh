#!/usr/bin/env bash
# Ejecución automatizada del plan de pruebas de la EA2 (PP-02) contra el sistema real.
#
#   scripts/ejecutar_plan_pruebas.sh
#
# 1. Recrea la base desde cero (docker compose down -v y up --build) y carga la historia de la EA1
#    (app.demo, que solo funciona con la base sin estancias).
# 2. Genera, dentro del backend, un token ya vencido para US-05 (solo vive en memoria).
# 3. Ejecuta los casos US, PE y CE con Playwright (servicio plan-pruebas): pantalla, API y base.
# 4. Ejecuta las pruebas automatizadas de concurrencia (US-13, US-19, CE-13 y CE-17).
# 5. Completa NF-01 y NF-02 desde sus reportes, busca secretos en las evidencias y escribe el reporte.
# 6. Deja la base limpia otra vez (docker compose down -v).
#
# Evidencias: docs/pruebas/evidencias/ (una por caso, con su ID). Resumen: docs/pruebas/reporte.md.
# Después de hacer commit de las evidencias, el Excel se llena con:
#   python3 scripts/plan_pruebas.py excel <commit-de-las-evidencias> <ruta-del-excel>
set -euo pipefail
cd "$(dirname "$0")/.."
EVIDENCIAS=docs/pruebas/evidencias

[ -f .env ] || { echo "Falta .env (ver .env.example)"; exit 1; }
if [ -z "${PLAN_PERMITIR_CAMBIOS:-}" ] && [ -n "$(git status --porcelain)" ]; then
  echo "Hay cambios sin confirmar: la evidencia debe corresponder a un commit. (Para una prueba local: PLAN_PERMITIR_CAMBIOS=1)"
  exit 1
fi
export COMMIT_PROBADO; COMMIT_PROBADO="$(git rev-parse --short HEAD)"
hora() { TZ=America/Bogota date '+%Y-%m-%d %H:%M'; }
INICIO="$(hora)"

echo "== 1. Base limpia y sistema arriba (commit $COMMIT_PROBADO)"
docker compose --profile plan down -v --remove-orphans >/dev/null 2>&1 || true
docker compose up -d --build db backend frontend
for _ in $(seq 1 90); do curl -sf http://localhost:4200/health >/dev/null && break; sleep 2; done
curl -sf http://localhost:4200/health >/dev/null || { echo "La API no respondió"; exit 1; }
echo "== Historia de la EA1 (app.demo)"
docker compose exec -T backend python -m app.demo

echo "== 2. Token vencido para US-05 (generado por el backend, solo en memoria)"
export TOKEN_VENCIDO
TOKEN_VENCIDO="$(docker compose exec -T backend python -c "from datetime import datetime, timedelta, timezone
from app.services.seguridad import crear_token
print(crear_token(1, 0, datetime.now(timezone.utc) - timedelta(hours=9))[0])")"

rm -rf "$EVIDENCIAS" && mkdir -p "$EVIDENCIAS"
echo "== 3. Casos US, PE y CE (Playwright, Google Chrome)"
docker compose --profile plan run --rm --build plan-pruebas || echo "(Playwright terminó con error: se registra en resultados.json)"
unset TOKEN_VENCIDO

echo "== 4. Pruebas automatizadas de concurrencia (base de pruebas desechable)"
declare -A PRUEBAS=(
  [US-13]="tests/test_cuentas_postgres.py::test_dos_creaciones_simultaneas_del_mismo_usuario_dejan_una_cuenta"
  [US-19]="tests/test_cuentas_postgres.py::test_dos_administradores_que_se_desactivan_mutuamente_no_dejan_cero"
  [CE-13]="tests/test_gestion_celdas_postgres.py::test_dos_creaciones_simultaneas_del_mismo_codigo_dejan_una_celda"
  [CE-17]="tests/test_gestion_celdas_postgres.py::test_inhabilitar_espera_a_la_entrada_en_curso_y_ve_la_celda_ocupada tests/test_gestion_celdas_postgres.py::test_la_entrada_salta_la_celda_que_se_esta_inhabilitando"
)
docker compose build backend-tests >/dev/null
for caso in US-13 US-19 CE-13 CE-17; do
  {
    echo "# $caso · $(hora) (Bogotá) · commit $COMMIT_PROBADO"
    echo "# docker compose run --rm backend-tests ... python -m pytest -v ${PRUEBAS[$caso]}"
    docker compose run --rm backend-tests sh -c "python -m alembic -c alembic.ini upgrade head >/dev/null && python -m pytest -v -p no:cacheprovider ${PRUEBAS[$caso]}" 2>&1 \
      | sed 's/\x1b\[[0-9;]*m//g; s/[[:space:]]*$//' || true
  } > "$EVIDENCIAS/${caso}_pytest.txt"
  tail -1 "$EVIDENCIAS/${caso}_pytest.txt"
done
docker compose --profile test rm -sf db-test >/dev/null 2>&1 || true

FIN="$(hora)"
printf '{\n  "commit_probado": "%s",\n  "inicio": "%s",\n  "fin": "%s",\n  "entorno": "Docker Compose local: frontend y API en http://localhost:4200 (API a través de nginx); base recreada con docker compose down -v"\n}\n' \
  "$COMMIT_PROBADO" "$INICIO" "$FIN" > "$EVIDENCIAS/ejecucion.json"

echo "== 5. NF-01 y NF-02, búsqueda de secretos y reporte"
python3 scripts/plan_pruebas.py completar

echo "== 6. Base limpia para el video (docker compose down -v)"
docker compose --profile plan --profile test down -v >/dev/null 2>&1
echo "Listo: $EVIDENCIAS y docs/pruebas/reporte.md"
