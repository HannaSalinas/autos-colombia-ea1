"""Valida en toda la tabla los CHECK de cliente que la 0009 creó NOT VALID, si los datos lo permiten.

Mismo criterio que la 0008 con las celdas. Revisa cada CHECK por separado:

- Si todos los clientes existentes lo cumplen, ejecuta VALIDATE CONSTRAINT: desde ese momento
  PostgreSQL garantiza la regla para TODAS las filas, también las antiguas.
- Si alguno no lo cumple, lo deja NOT VALID (sigue aplicándose a clientes nuevos y modificados) y
  avisa cuántos fallan y sus ids, sin modificarlos ni detener la migración. Se informan los ids y no
  los documentos, para no escribir datos personales en los registros.

Revision ID: 0011
Revises: 0010
"""
import logging

from alembic import context, op
from sqlalchemy import text

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

aviso = logging.getLogger("alembic.migraciones")

# Nombre del CHECK y su condición (la misma de la migración 0009).
CHECKS = {
    "ck_cliente_documento_formato": "documento ~ '^[A-Z0-9]{5,15}$'",
    "ck_cliente_nombre_longitud": "char_length(nombre) BETWEEN 3 AND 80 AND nombre !~ '^[[:space:]]|[[:space:]]$'",
    "ck_cliente_telefono_formato": "telefono ~ '^[0-9]{10}$'",
}


def clientes_que_fallan(condicion: str) -> list[int]:
    # Igual que en un CHECK, una condición que da NULL cuenta como cumplida: NOT (NULL) no selecciona la fila.
    return list(op.get_bind().execute(text(f"SELECT id FROM cliente WHERE NOT ({condicion}) ORDER BY id")).scalars())


def upgrade() -> None:
    if context.is_offline_mode():
        # Sin conexión no se pueden mirar los datos: la misma decisión se escribe en SQL.
        for nombre, condicion in CHECKS.items():
            op.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM cliente WHERE NOT ({condicion})) THEN
                        RAISE WARNING '{nombre} queda NOT VALID: hay clientes que no lo cumplen.';
                    ELSE
                        ALTER TABLE cliente VALIDATE CONSTRAINT {nombre};
                    END IF;
                END $$;
            """)
        return
    for nombre, condicion in CHECKS.items():
        fallan = clientes_que_fallan(condicion)
        if fallan:
            aviso.warning("%s queda NOT VALID: %d cliente(s) no lo cumplen (ids %s). Corríjalos y vuelva a validar "
                          "con ALTER TABLE cliente VALIDATE CONSTRAINT %s.", nombre, len(fallan),
                          ", ".join(map(str, fallan)), nombre)
        else:
            op.execute(f"ALTER TABLE cliente VALIDATE CONSTRAINT {nombre}")


def downgrade() -> None:
    # PostgreSQL no tiene "des-validar": se vuelve a crear cada CHECK como NOT VALID, igual que antes.
    for nombre, condicion in CHECKS.items():
        op.drop_constraint(nombre, "cliente", type_="check")
        op.create_check_constraint(nombre, "cliente", condicion, postgresql_not_valid=True)
