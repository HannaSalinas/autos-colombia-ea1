"""Gestión de celdas: ubicación, habilitación, formato del código, índices de historial y auditoría.

Se puede aplicar sobre una base con datos de la EA1: las celdas existentes quedan habilitadas y
sin ubicación, y el formato del código es NOT VALID (no revisa celdas antiguas, sí las nuevas).

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("celda", sa.Column("ubicacion", sa.Text(), nullable=True))
    # Las celdas que ya existen quedan habilitadas.
    op.add_column("celda", sa.Column("habilitada", sa.Boolean(), server_default=sa.true(), nullable=False))
    # Columna nueva (todas NULL): este CHECK se valida completo.
    op.create_check_constraint(
        "ck_celda_ubicacion", "celda",
        "ubicacion IS NULL OR (char_length(ubicacion) BETWEEN 1 AND 60 "
        "AND ubicacion !~ '^[[:space:]]|[[:space:]]$')",
    )
    # C (carro) o M (moto) + dos dígitos del 01 al 99, con el prefijo de su tipo.
    op.create_check_constraint(
        "ck_celda_codigo_formato", "celda",
        "(tipo = 'CARRO' AND codigo ~ '^C(0[1-9]|[1-9][0-9])$') OR "
        "(tipo = 'MOTO' AND codigo ~ '^M(0[1-9]|[1-9][0-9])$')",
        postgresql_not_valid=True,
    )
    # Único sin distinguir mayúsculas (RNF-17). Complementa uq_celda_codigo de la 0001.
    op.create_index("uq_celda_codigo_ci", "celda", [sa.text("upper(codigo)")], unique=True)
    # Para saber rápido si una celda "tiene historial" (D8): estancias y correcciones que la nombran.
    op.create_index("ix_estancia_celda", "estancia", ["celda_id"])
    op.create_index("ix_correccion_celda_anterior", "correccion_celda", ["celda_anterior_id"])
    op.create_index("ix_correccion_celda_nueva", "correccion_celda", ["celda_nueva_id"])

    op.create_table(
        "auditoria_celda",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("celda_id", sa.BigInteger(), nullable=False),
        # NULL = lo hizo el sistema (semillas), no una persona.
        sa.Column("actor_cuenta_id", sa.BigInteger(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["celda_id"], ["celda.id"], name="fk_auditoria_celda_celda", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_cuenta_id"], ["cuenta_usuario.id"], name="fk_auditoria_celda_actor",
                                ondelete="RESTRICT"),
        sa.CheckConstraint("accion IN ('CREAR', 'EDITAR', 'INHABILITAR', 'REHABILITAR')",
                           name="ck_auditoria_celda_accion"),
        sa.CheckConstraint("detalle IS NULL OR char_length(detalle) <= 500", name="ck_auditoria_celda_detalle"),
    )
    op.create_index("ix_auditoria_celda_celda", "auditoria_celda", ["celda_id", "fecha"])


def downgrade() -> None:
    op.drop_index("ix_auditoria_celda_celda", table_name="auditoria_celda")
    op.drop_table("auditoria_celda")
    op.drop_index("ix_correccion_celda_nueva", table_name="correccion_celda")
    op.drop_index("ix_correccion_celda_anterior", table_name="correccion_celda")
    op.drop_index("ix_estancia_celda", table_name="estancia")
    op.drop_index("uq_celda_codigo_ci", table_name="celda")
    op.drop_constraint("ck_celda_codigo_formato", "celda", type_="check")
    op.drop_constraint("ck_celda_ubicacion", "celda", type_="check")
    op.drop_column("celda", "habilitada")
    op.drop_column("celda", "ubicacion")
