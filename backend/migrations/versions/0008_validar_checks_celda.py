"""Valida en toda la tabla los CHECK de celda que se crearon NOT VALID, si los datos lo permiten.

ck_celda_tipo (0004) y ck_celda_codigo_formato (0007) se crearon NOT VALID para no romper
bases con celdas antiguas. Esta migración revisa cada uno por separado:

- Si todas las celdas existentes lo cumplen, ejecuta VALIDATE CONSTRAINT: desde ese momento
  PostgreSQL garantiza la regla para TODAS las filas, también las antiguas.
- Si alguna no lo cumple, lo deja NOT VALID (sigue aplicándose a filas nuevas y modificadas) y
  avisa qué códigos fallan, sin detener la migración.

Revision ID: 0008
Revises: 0007
"""
import logging

from alembic import context, op
from sqlalchemy import text

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

aviso = logging.getLogger("alembic.migraciones")

# Nombre del CHECK y su condición (la misma de las migraciones 0004 y 0007).
CHECKS = {
    "ck_celda_tipo": "tipo IN ('MOTO', 'CARRO')",
    "ck_celda_codigo_formato": (
        "(tipo = 'CARRO' AND codigo ~ '^C(0[1-9]|[1-9][0-9])$') OR "
        "(tipo = 'MOTO' AND codigo ~ '^M(0[1-9]|[1-9][0-9])$')"
    ),
}


def celdas_que_fallan(condicion: str) -> list[str]:
    # Igual que en un CHECK, una condición que da NULL cuenta como cumplida: NOT (NULL) no selecciona la fila.
    return list(op.get_bind().execute(text(f"SELECT codigo FROM celda WHERE NOT ({condicion}) ORDER BY codigo"))
                .scalars())


def upgrade() -> None:
    if context.is_offline_mode():
        # Sin conexión no se pueden mirar los datos: la misma decisión se escribe en SQL.
        for nombre, condicion in CHECKS.items():
            op.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM celda WHERE NOT ({condicion})) THEN
                        RAISE WARNING '{nombre} queda NOT VALID: hay celdas que no lo cumplen.';
                    ELSE
                        ALTER TABLE celda VALIDATE CONSTRAINT {nombre};
                    END IF;
                END $$;
            """)
        return
    for nombre, condicion in CHECKS.items():
        fallan = celdas_que_fallan(condicion)
        if fallan:
            aviso.warning("%s queda NOT VALID: %d celda(s) no lo cumplen: %s. Corríjalas y vuelva a validar "
                          "con ALTER TABLE celda VALIDATE CONSTRAINT %s.", nombre, len(fallan), ", ".join(fallan),
                          nombre)
        else:
            op.execute(f"ALTER TABLE celda VALIDATE CONSTRAINT {nombre}")


def downgrade() -> None:
    # PostgreSQL no tiene "des-validar": se vuelve a crear cada CHECK como NOT VALID, igual que antes.
    for nombre, condicion in CHECKS.items():
        op.drop_constraint(nombre, "celda", type_="check")
        op.create_check_constraint(nombre, "celda", condicion, postgresql_not_valid=True)
