"""Cuentas de usuario (credenciales, rol y estado) separadas de la persona, y su auditoría.

La persona sigue siendo la fila de `operador` (EA1): estancias, correcciones y novedades
conservan su responsable. Cada cuenta pertenece a una sola persona (operador_id único).
Se puede aplicar sobre una base con datos de la EA1: no exige tablas vacías.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # El formulario de cuentas no pide teléfono: la persona puede no tenerlo.
    op.alter_column("operador", "telefono", existing_type=sa.Text(), nullable=True)
    # Nombre completo de 3 a 80 caracteres, sin espacios exteriores. NOT VALID: no revisa
    # operadores antiguos (la EA1 aceptaba cualquier nombre no vacío), sí los nuevos.
    op.create_check_constraint(
        "ck_operador_nombre_longitud", "operador",
        "char_length(nombre) BETWEEN 3 AND 80 AND nombre !~ '^[[:space:]]|[[:space:]]$'",
        postgresql_not_valid=True,
    )

    op.create_table(
        "cuenta_usuario",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre_usuario", sa.Text(), nullable=False),
        sa.Column("hash_contrasena", sa.Text(), nullable=False),
        sa.Column("rol", sa.Text(), nullable=False),
        sa.Column("activa", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version_sesion", sa.Integer(), server_default="0", nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["operador_id"], ["operador.id"], name="fk_cuenta_usuario_operador",
                                ondelete="RESTRICT"),
        sa.UniqueConstraint("operador_id", name="uq_cuenta_usuario_operador"),
        sa.CheckConstraint("nombre_usuario ~ '^[a-z0-9._]{4,30}$'", name="ck_cuenta_usuario_nombre_formato"),
        sa.CheckConstraint("rol IN ('ADMINISTRADOR', 'OPERADOR')", name="ck_cuenta_usuario_rol"),
        # Solo hashes bcrypt con costo de 12 a 39: nunca una contraseña en texto plano.
        sa.CheckConstraint(r"hash_contrasena ~ '^\$2[aby]\$(1[2-9]|[23][0-9])\$[./A-Za-z0-9]{53}$'",
                           name="ck_cuenta_usuario_hash_bcrypt"),
        sa.CheckConstraint("version_sesion >= 0", name="ck_cuenta_usuario_version_sesion"),
    )
    # Único sin distinguir mayúsculas: 'Marta' y 'marta' son el mismo usuario.
    op.create_index("uq_cuenta_usuario_nombre", "cuenta_usuario", [sa.text("lower(nombre_usuario)")], unique=True)

    op.create_table(
        "auditoria_cuenta",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("cuenta_id", sa.BigInteger(), nullable=False),
        # NULL = lo hizo el sistema (semillas), no una persona.
        sa.Column("actor_cuenta_id", sa.BigInteger(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cuenta_id"], ["cuenta_usuario.id"], name="fk_auditoria_cuenta_cuenta",
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_cuenta_id"], ["cuenta_usuario.id"], name="fk_auditoria_cuenta_actor",
                                ondelete="RESTRICT"),
        sa.CheckConstraint("accion IN ('CREAR', 'DESACTIVAR', 'REACTIVAR')", name="ck_auditoria_cuenta_accion"),
        sa.CheckConstraint("detalle IS NULL OR char_length(detalle) <= 500", name="ck_auditoria_cuenta_detalle"),
    )
    op.create_index("ix_auditoria_cuenta_cuenta", "auditoria_cuenta", ["cuenta_id", "fecha"])


def downgrade() -> None:
    op.drop_index("ix_auditoria_cuenta_cuenta", table_name="auditoria_cuenta")
    op.drop_table("auditoria_cuenta")
    op.drop_index("uq_cuenta_usuario_nombre", table_name="cuenta_usuario")
    op.drop_table("cuenta_usuario")
    op.drop_constraint("ck_operador_nombre_longitud", "operador", type_="check")
    # Volver a exigir el teléfono falla si hay personas sin él: se detiene con un mensaje claro
    # en vez de inventar teléfonos.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM operador WHERE telefono IS NULL) THEN
                RAISE EXCEPTION 'Hay personas sin teléfono: complételo antes de volver a la migración 0005.';
            END IF;
        END $$;
    """)
    op.alter_column("operador", "telefono", existing_type=sa.Text(), nullable=False)
