"""Crea cliente y mensualidad; asocia cada vehículo a su cliente y valida placa y modelo.

Revision ID: 0003
Revises: 0002
"""
from alembic import context, op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # cliente_id es obligatorio: si ya existen vehículos sin dueño, detenerse con un
    # mensaje claro en vez de inventar un cliente. (En modo --sql no hay conexión.)
    if not context.is_offline_mode():
        if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM vehiculo)")):
            raise RuntimeError(
                "La tabla vehiculo tiene registros sin cliente. Elimínalos o asígnales un "
                "cliente antes de aplicar la migración 0003."
            )

    op.create_table(
        "cliente",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("documento", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("telefono", sa.Text(), nullable=False),
        sa.Column("correo", sa.Text(), nullable=True),
        sa.UniqueConstraint("documento", name="uq_cliente_documento"),
        sa.CheckConstraint("documento ~ '[^[:space:]]'", name="ck_cliente_documento_no_vacio"),
        sa.CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_cliente_nombre_no_vacio"),
        sa.CheckConstraint("telefono ~ '[^[:space:]]'", name="ck_cliente_telefono_no_vacio"),
        sa.CheckConstraint("correo IS NULL OR correo ~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'",
                           name="ck_cliente_correo_formato"),
    )

    op.add_column("vehiculo", sa.Column("cliente_id", sa.BigInteger(), nullable=False))
    op.create_foreign_key("fk_vehiculo_cliente", "vehiculo", "cliente", ["cliente_id"], ["id"],
                          ondelete="RESTRICT")
    op.create_index("ix_vehiculo_cliente", "vehiculo", ["cliente_id"])
    op.create_check_constraint(
        "ck_vehiculo_placa_formato", "vehiculo",
        "(tipo = 'MOTO' AND placa ~ '^[A-Z]{3}[0-9]{2}[A-Z]$') OR "
        "(tipo <> 'MOTO' AND placa ~ '^[A-Z]{3}[0-9]{3}$')",
    )
    op.create_check_constraint("ck_vehiculo_modelo_minimo", "vehiculo", "modelo >= 1900")

    op.create_table(
        "mensualidad",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("vehiculo_id", sa.BigInteger(), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculo.id"], name="fk_mensualidad_vehiculo",
                                ondelete="RESTRICT"),
        sa.CheckConstraint("fecha_fin > fecha_inicio", name="ck_mensualidad_fechas"),
    )
    op.create_index("ix_mensualidad_vehiculo_fin", "mensualidad", ["vehiculo_id", "fecha_fin"])


def downgrade() -> None:
    # Solo para una reversión deliberada: elimina clientes y mensualidades.
    op.drop_index("ix_mensualidad_vehiculo_fin", table_name="mensualidad")
    op.drop_table("mensualidad")
    op.drop_constraint("ck_vehiculo_modelo_minimo", "vehiculo", type_="check")
    op.drop_constraint("ck_vehiculo_placa_formato", "vehiculo", type_="check")
    op.drop_index("ix_vehiculo_cliente", table_name="vehiculo")
    op.drop_constraint("fk_vehiculo_cliente", "vehiculo", type_="foreignkey")
    op.drop_column("vehiculo", "cliente_id")
    op.drop_table("cliente")
