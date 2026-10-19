"""Crea vehiculo, celda y operador. No modifica estructuras preexistentes.

Revision ID: 0001
Revises: None
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehiculo",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("placa", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("modelo", sa.Integer(), nullable=False),
        sa.Column("marca", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.UniqueConstraint("placa", name="uq_vehiculo_placa"),
        sa.CheckConstraint("placa ~ '[^[:space:]]'", name="ck_vehiculo_placa_no_vacia"),
        sa.CheckConstraint("placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_vehiculo_placa_normalizada"),
        sa.CheckConstraint("color ~ '[^[:space:]]'", name="ck_vehiculo_color_no_vacio"),
        sa.CheckConstraint("marca ~ '[^[:space:]]'", name="ck_vehiculo_marca_no_vacia"),
        sa.CheckConstraint("modelo BETWEEN 1 AND 9999", name="ck_vehiculo_modelo_anio"),
        sa.CheckConstraint("tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')", name="ck_vehiculo_tipo"),
    )
    op.create_table(
        "celda",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.UniqueConstraint("codigo", name="uq_celda_codigo"),
        sa.CheckConstraint("codigo ~ '[^[:space:]]'", name="ck_celda_codigo_no_vacio"),
        sa.CheckConstraint("codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_celda_codigo_normalizado"),
        sa.CheckConstraint("tipo ~ '[^[:space:]]'", name="ck_celda_tipo_no_vacio"),
    )
    op.create_table(
        "operador",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("telefono", sa.Text(), nullable=False),
        sa.CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_operador_nombre_no_vacio"),
        sa.CheckConstraint("telefono ~ '[^[:space:]]'", name="ck_operador_telefono_no_vacio"),
    )


def downgrade() -> None:
    op.drop_table("operador")
    op.drop_table("celda")
    op.drop_table("vehiculo")
