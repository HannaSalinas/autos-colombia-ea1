"""Iteración 3: tipo de documento y registro del cliente; tabla de tarifas inmutable.

Se puede aplicar sobre una base con datos de las iteraciones 1 y 2:
- Los clientes existentes quedan con tipo de documento CC (D15) y sin "registrado por" (NULL =
  anterior a la Iteración 3 o semilla). Los CHECK nuevos de cliente son NOT VALID: no revisan los
  clientes antiguos, sí los nuevos y los modificados.
- El documento pasa a ser único por tipo y número, sin distinguir mayúsculas (RF-34).
- Una tarifa nunca se edita ni se borra (D12, RNF-24): lo impide un trigger, aunque se intente
  directamente en la base.

Revision ID: 0009
Revises: 0008
"""
from alembic import context, op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

TIPOS_VEHICULO = "('MOTO', 'AUTOMOVIL', 'CAMIONETA')"

# Mensaje y código de error comunes de los triggers de inmutabilidad. 23001 = restrict_violation:
# es una violación de integridad, igual que una FK con RESTRICT.
FUNCION_TARIFA = """
CREATE FUNCTION tarifa_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Las tarifas no se editan ni se eliminan: para cambiar el valor se crea una tarifa nueva.'
        USING ERRCODE = '23001';
END;
$$;
"""


def upgrade() -> None:
    # El índice único nuevo no distingue mayúsculas: si ya hay documentos que solo difieren en
    # mayúsculas, detenerse con un mensaje claro en vez de elegir uno. (En modo --sql no hay conexión.)
    if not context.is_offline_mode():
        repetidos = op.get_bind().execute(sa.text(
            "SELECT upper(documento) FROM cliente GROUP BY upper(documento) HAVING count(*) > 1"
        )).scalars().all()
        if repetidos:
            raise RuntimeError(
                "Hay clientes cuyo documento solo difiere en mayúsculas: " + ", ".join(repetidos)
                + ". Corrígelos antes de aplicar la migración 0009."
            )

    # --- cliente ---
    # El DEFAULT 'CC' solo sirve para llenar las filas existentes (D15); después se quita, para que
    # todo cliente nuevo tenga que indicar su tipo de documento.
    op.add_column("cliente", sa.Column("tipo_documento", sa.Text(), server_default="CC", nullable=False))
    op.alter_column("cliente", "tipo_documento", server_default=None)
    op.create_check_constraint("ck_cliente_tipo_documento", "cliente", "tipo_documento IN ('CC', 'CE', 'PA')")
    # NULL = anterior a la Iteración 3 o creado por las semillas (D18: el registro guarda quién y cuándo).
    op.add_column("cliente", sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cliente", sa.Column("registrado_por_cuenta_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_cliente_registrado_por", "cliente", "cuenta_usuario", ["registrado_por_cuenta_id"],
                          ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_cliente_registro", "cliente",
                               "registrado_por_cuenta_id IS NULL OR registrado_en IS NOT NULL")
    # Reglas de la tabla de reglas de la EA3. NOT VALID: los clientes antiguos no se revisan.
    op.create_check_constraint("ck_cliente_documento_formato", "cliente", "documento ~ '^[A-Z0-9]{5,15}$'",
                               postgresql_not_valid=True)
    op.create_check_constraint("ck_cliente_nombre_longitud", "cliente",
                               "char_length(nombre) BETWEEN 3 AND 80 AND nombre !~ '^[[:space:]]|[[:space:]]$'",
                               postgresql_not_valid=True)
    op.create_check_constraint("ck_cliente_telefono_formato", "cliente", "telefono ~ '^[0-9]{10}$'",
                               postgresql_not_valid=True)
    # Único por tipo y número, sin distinguir mayúsculas. Reemplaza al único por número de la 0003.
    op.drop_constraint("uq_cliente_documento", "cliente", type_="unique")
    op.create_index("uq_cliente_tipo_documento", "cliente", ["tipo_documento", sa.text("upper(documento)")],
                    unique=True)

    # --- tarifa ---
    op.create_table(
        "tarifa",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("tipo_vehiculo", sa.Text(), nullable=False),
        # Pesos enteros: integer es un tipo exacto (RNF-22). Nunca punto flotante.
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.Column("vigente_desde", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # NULL = la definieron las semillas.
        sa.Column("definida_por_cuenta_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["definida_por_cuenta_id"], ["cuenta_usuario.id"], name="fk_tarifa_definida_por",
                                ondelete="RESTRICT"),
        sa.CheckConstraint(f"tipo_vehiculo IN {TIPOS_VEHICULO}", name="ck_tarifa_tipo_vehiculo"),
        sa.CheckConstraint("valor BETWEEN 1000 AND 2000000", name="ck_tarifa_valor"),
        sa.UniqueConstraint("tipo_vehiculo", "vigente_desde", name="uq_tarifa_tipo_desde"),
        # Destino de la FK compuesta del pago (0010): garantiza que el pago copia tipo y valor reales.
        sa.UniqueConstraint("id", "tipo_vehiculo", "valor", name="uq_tarifa_id_tipo_valor"),
    )
    op.execute(FUNCION_TARIFA)
    op.execute("CREATE TRIGGER tarifa_sin_cambios BEFORE UPDATE OR DELETE ON tarifa "
               "FOR EACH ROW EXECUTE FUNCTION tarifa_inmutable()")
    op.execute("CREATE TRIGGER tarifa_sin_vaciar BEFORE TRUNCATE ON tarifa "
               "FOR EACH STATEMENT EXECUTE FUNCTION tarifa_inmutable()")


def downgrade() -> None:
    # Solo para una reversión deliberada: elimina las tarifas y los datos nuevos de cliente.
    op.execute("DROP TRIGGER tarifa_sin_vaciar ON tarifa")
    op.execute("DROP TRIGGER tarifa_sin_cambios ON tarifa")
    op.execute("DROP FUNCTION tarifa_inmutable()")
    op.drop_table("tarifa")
    if not context.is_offline_mode():
        repetidos = op.get_bind().execute(sa.text(
            "SELECT documento FROM cliente GROUP BY documento HAVING count(*) > 1"
        )).scalars().all()
        if repetidos:
            raise RuntimeError("No se puede volver a la 0008: hay documentos repetidos con distinto tipo: "
                               + ", ".join(repetidos) + ".")
    op.drop_index("uq_cliente_tipo_documento", table_name="cliente")
    op.create_unique_constraint("uq_cliente_documento", "cliente", ["documento"])
    op.drop_constraint("ck_cliente_telefono_formato", "cliente", type_="check")
    op.drop_constraint("ck_cliente_nombre_longitud", "cliente", type_="check")
    op.drop_constraint("ck_cliente_documento_formato", "cliente", type_="check")
    op.drop_constraint("ck_cliente_registro", "cliente", type_="check")
    op.drop_constraint("fk_cliente_registrado_por", "cliente", type_="foreignkey")
    op.drop_column("cliente", "registrado_por_cuenta_id")
    op.drop_column("cliente", "registrado_en")
    op.drop_constraint("ck_cliente_tipo_documento", "cliente", type_="check")
    op.drop_column("cliente", "tipo_documento")
