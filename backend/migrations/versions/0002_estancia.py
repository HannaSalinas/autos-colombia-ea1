"""Crea estancia con historial y exclusividad de estancias abiertas.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estancia",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("vehiculo_id", sa.BigInteger(), nullable=False),
        sa.Column("celda_id", sa.BigInteger(), nullable=False),
        sa.Column("entrada", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("salida", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operador_entrada_id", sa.BigInteger(), nullable=False),
        sa.Column("operador_salida_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculo.id"], name="fk_estancia_vehiculo", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["celda_id"], ["celda.id"], name="fk_estancia_celda", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operador_entrada_id"], ["operador.id"], name="fk_estancia_operador_entrada", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operador_salida_id"], ["operador.id"], name="fk_estancia_operador_salida", ondelete="RESTRICT"),
        sa.CheckConstraint("salida >= entrada", name="ck_estancia_orden_fechas"),
        sa.CheckConstraint("(salida IS NULL) = (operador_salida_id IS NULL)", name="ck_estancia_cierre_completo"),
    )
    op.create_index("uq_estancia_vehiculo_abierta", "estancia", ["vehiculo_id"], unique=True,
                    postgresql_where=sa.text("salida IS NULL"))
    op.create_index("uq_estancia_celda_abierta", "estancia", ["celda_id"], unique=True,
                    postgresql_where=sa.text("salida IS NULL"))
    op.create_index("ix_estancia_vehiculo_entrada", "estancia", ["vehiculo_id", "entrada"])


def downgrade() -> None:
    # Solo para una reversión deliberada: eliminaría todo el historial de estancias.
    op.drop_index("ix_estancia_vehiculo_entrada", table_name="estancia")
    op.drop_index("uq_estancia_celda_abierta", table_name="estancia")
    op.drop_index("uq_estancia_vehiculo_abierta", table_name="estancia")
    op.drop_table("estancia")
