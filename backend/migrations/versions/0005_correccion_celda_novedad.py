"""Registro de correcciones de celda y novedades de las estancias.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "correccion_celda",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("estancia_id", sa.BigInteger(), nullable=False),
        sa.Column("celda_anterior_id", sa.BigInteger(), nullable=False),
        sa.Column("celda_nueva_id", sa.BigInteger(), nullable=False),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["estancia_id"], ["estancia.id"], name="fk_correccion_celda_estancia", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["celda_anterior_id"], ["celda.id"], name="fk_correccion_celda_anterior", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["celda_nueva_id"], ["celda.id"], name="fk_correccion_celda_nueva", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operador_id"], ["operador.id"], name="fk_correccion_celda_operador", ondelete="RESTRICT"),
        sa.CheckConstraint("celda_anterior_id <> celda_nueva_id", name="ck_correccion_celda_distinta"),
        sa.CheckConstraint("motivo ~ '[^[:space:]]' AND char_length(motivo) <= 200", name="ck_correccion_celda_motivo"),
    )
    op.create_index("ix_correccion_celda_estancia", "correccion_celda", ["estancia_id"])

    op.create_table(
        "novedad",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("estancia_id", sa.BigInteger(), nullable=False),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["estancia_id"], ["estancia.id"], name="fk_novedad_estancia", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operador_id"], ["operador.id"], name="fk_novedad_operador", ondelete="RESTRICT"),
        sa.CheckConstraint("tipo IN ('RAYON', 'GOLPE', 'OBJETO_OLVIDADO', 'OTRO')", name="ck_novedad_tipo"),
        sa.CheckConstraint("descripcion ~ '[^[:space:]]' AND char_length(descripcion) <= 500", name="ck_novedad_descripcion"),
    )
    op.create_index("ix_novedad_estancia", "novedad", ["estancia_id"])


def downgrade() -> None:
    # Solo para una reversión deliberada: borra el registro de correcciones y novedades.
    op.drop_index("ix_novedad_estancia", table_name="novedad")
    op.drop_table("novedad")
    op.drop_index("ix_correccion_celda_estancia", table_name="correccion_celda")
    op.drop_table("correccion_celda")
