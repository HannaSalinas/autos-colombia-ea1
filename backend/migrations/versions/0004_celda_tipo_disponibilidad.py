"""Celdas de tipo MOTO o CARRO y fecha desde la que están libres (para repartir el uso).

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("celda", sa.Column("disponible_desde", sa.DateTime(timezone=True), nullable=True))
    # NOT VALID: las celdas que ya existan con otro tipo se conservan (no se borra historial),
    # pero toda celda nueva o editada debe ser MOTO o CARRO.
    op.create_check_constraint("ck_celda_tipo", "celda", "tipo IN ('MOTO', 'CARRO')",
                               postgresql_not_valid=True)
    op.create_index("ix_celda_tipo_disponible", "celda", ["tipo", "disponible_desde"])


def downgrade() -> None:
    op.drop_index("ix_celda_tipo_disponible", table_name="celda")
    op.drop_constraint("ck_celda_tipo", "celda", type_="check")
    op.drop_column("celda", "disponible_desde")
