"""Iteración 3: pagos de mensualidad, vínculo 1 a 1 con el periodo que generan e inmutabilidad.

Se puede aplicar sobre una base con datos de las iteraciones 1 y 2: los periodos existentes quedan
sin pago (pago_id NULL) y siguen siendo válidos (D10). No se modifica ningún dato.

Cómo se impide la superposición de periodos (RNF-23):
- Una restricción de exclusión sobre TODOS los periodos no es posible: PostgreSQL no admite NOT
  VALID en una restricción EXCLUDE (la revisa completa al crearla) y algunos periodos antiguos ya se
  tocan (en las semillas, los dos de JKL321 comparten un día).
- Por eso la exclusión es PARCIAL: solo entre periodos pagados y no anulados. Entre un periodo
  pagado y uno antiguo lo garantiza el servicio, bloqueando la fila del vehículo.
- Esta migración avisa (sin modificarlas) las superposiciones antiguas que encuentre.

Inmutabilidad (RNF-24): triggers que rechazan, aunque se intente directamente en la base, borrar o
vaciar pagos, editarlos salvo el paso único de VALIDO a ANULADO, y cambiar o borrar un periodo pagado.

Revision ID: 0010
Revises: 0009
"""
import logging

from alembic import context, op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

aviso = logging.getLogger("alembic.migraciones")

# Columnas del pago que nunca cambian. Al anular solo cambian estado y los datos de anulación.
FIJAS = ("id", "comprobante", "meses", "tarifa_id", "tipo_vehiculo", "valor_mensual", "monto", "metodo",
         "referencia", "fecha", "registrado_por_cuenta_id")

FUNCION_PAGO = f"""
CREATE FUNCTION pago_solo_anular() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.estado = 'VALIDO' AND NEW.estado = 'ANULADO'
           AND ({", ".join("NEW." + c for c in FIJAS)})
               IS NOT DISTINCT FROM ({", ".join("OLD." + c for c in FIJAS)}) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'Un pago no se edita ni se elimina: solo puede pasar una vez de VALIDO a ANULADO, con sus datos de anulación.'
        USING ERRCODE = '23001';
END;
$$;
"""

FUNCION_MENSUALIDAD = """
CREATE FUNCTION mensualidad_pagada_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.pago_id IS NOT NULL THEN
            RAISE EXCEPTION 'Un periodo pagado no se elimina: para dejarlo sin efecto se anula su pago.'
                USING ERRCODE = '23001';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.pago_id IS NULL AND NEW.pago_id IS NOT NULL THEN
        RAISE EXCEPTION 'Un periodo existente no se puede vincular a un pago: cada pago genera su propio periodo.'
            USING ERRCODE = '23001';
    END IF;
    -- Lo único que cambia en un periodo pagado es la copia del estado de su pago (ON UPDATE CASCADE).
    IF OLD.pago_id IS NOT NULL
       AND (NEW.vehiculo_id, NEW.fecha_inicio, NEW.fecha_fin, NEW.pago_id)
           IS DISTINCT FROM (OLD.vehiculo_id, OLD.fecha_inicio, OLD.fecha_fin, OLD.pago_id) THEN
        RAISE EXCEPTION 'Un periodo pagado no se edita: para corregirlo se anula su pago y se registra otro.'
            USING ERRCODE = '23001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION mensualidad_sin_vaciar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM mensualidad WHERE pago_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Un periodo pagado no se elimina: para dejarlo sin efecto se anula su pago.'
            USING ERRCODE = '23001';
    END IF;
    RETURN NULL;
END;
$$;
"""

SUPERPOSICIONES = """
SELECT v.placa, a.fecha_inicio, a.fecha_fin, b.fecha_inicio AS inicio_b, b.fecha_fin AS fin_b
FROM mensualidad a
JOIN mensualidad b ON b.vehiculo_id = a.vehiculo_id AND b.id > a.id
     AND daterange(a.fecha_inicio, a.fecha_fin, '[]') && daterange(b.fecha_inicio, b.fecha_fin, '[]')
JOIN vehiculo v ON v.id = a.vehiculo_id
ORDER BY v.placa, a.fecha_inicio
"""


def upgrade() -> None:
    # btree_gist permite combinar "mismo vehículo" (=) con "rangos que se cruzan" (&&) en un índice
    # GiST. Viene con PostgreSQL y es "trusted" desde la versión 13: el dueño de la base puede crearla.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # Comprobante RC-000001 ... RC-999999. Si se revierte una transacción queda un hueco en la
    # numeración: es aceptable porque no es una factura (D17). MAXVALUE: al agotarse, falla en vez
    # de repetir números.
    op.execute("CREATE SEQUENCE pago_comprobante_seq MINVALUE 1 MAXVALUE 999999 NO CYCLE")
    op.create_table(
        "pago",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("comprobante", sa.Text(), nullable=False,
                  server_default=sa.text("('RC-'::text || lpad((nextval('pago_comprobante_seq'::regclass))::text, "
                                         "6, '0'::text))")),
        sa.Column("meses", sa.SmallInteger(), nullable=False),
        # Copia de la tarifa con la que se cobró (D11): la FK compuesta garantiza que es una tarifa real.
        sa.Column("tarifa_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo_vehiculo", sa.Text(), nullable=False),
        sa.Column("valor_mensual", sa.Integer(), nullable=False),
        sa.Column("monto", sa.Integer(), nullable=False),      # pesos enteros (RNF-22)
        sa.Column("metodo", sa.Text(), nullable=False),
        sa.Column("referencia", sa.Text(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("registrado_por_cuenta_id", sa.BigInteger(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="VALIDO", nullable=False),
        sa.Column("anulado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulado_por_cuenta_id", sa.BigInteger(), nullable=True),
        sa.Column("motivo_anulacion", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tarifa_id", "tipo_vehiculo", "valor_mensual"],
                                ["tarifa.id", "tarifa.tipo_vehiculo", "tarifa.valor"],
                                name="fk_pago_tarifa", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["registrado_por_cuenta_id"], ["cuenta_usuario.id"], name="fk_pago_registrado_por",
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["anulado_por_cuenta_id"], ["cuenta_usuario.id"], name="fk_pago_anulado_por",
                                ondelete="RESTRICT"),
        sa.UniqueConstraint("comprobante", name="uq_pago_comprobante"),
        # Destino de la FK compuesta de mensualidad: la copia del estado la mantiene la base.
        sa.UniqueConstraint("id", "estado", name="uq_pago_id_estado"),
        sa.CheckConstraint("comprobante ~ '^RC-[0-9]{6}$'", name="ck_pago_comprobante_formato"),
        sa.CheckConstraint("meses BETWEEN 1 AND 6", name="ck_pago_meses"),
        sa.CheckConstraint("monto = valor_mensual * meses", name="ck_pago_monto"),
        sa.CheckConstraint("metodo IN ('EFECTIVO', 'TRANSFERENCIA', 'TARJETA')", name="ck_pago_metodo"),
        # Ojo: NULL ~ patrón da NULL y un CHECK con NULL pasa; por eso el IS NOT NULL explícito.
        sa.CheckConstraint("(metodo = 'EFECTIVO' AND referencia IS NULL) OR "
                           "(metodo <> 'EFECTIVO' AND referencia IS NOT NULL AND referencia ~ '^[A-Za-z0-9-]{4,30}$')",
                           name="ck_pago_referencia"),
        sa.CheckConstraint("estado IN ('VALIDO', 'ANULADO')", name="ck_pago_estado"),
        sa.CheckConstraint(
            "(estado = 'VALIDO' AND anulado_en IS NULL AND anulado_por_cuenta_id IS NULL AND motivo_anulacion IS NULL) "
            "OR (estado = 'ANULADO' AND anulado_en IS NOT NULL AND anulado_por_cuenta_id IS NOT NULL "
            "AND motivo_anulacion IS NOT NULL AND char_length(motivo_anulacion) BETWEEN 10 AND 200 "
            "AND motivo_anulacion !~ '^[[:space:]]|[[:space:]]$' AND anulado_en >= fecha)",
            name="ck_pago_anulacion"),
    )
    op.execute("ALTER SEQUENCE pago_comprobante_seq OWNED BY pago.comprobante")
    op.create_index("ix_pago_fecha", "pago", ["fecha"])

    # --- mensualidad: vínculo 1 a 1 con su pago. NULL en los periodos existentes (D10). ---
    op.add_column("mensualidad", sa.Column("pago_id", sa.BigInteger(), nullable=True))
    op.add_column("mensualidad", sa.Column("pago_estado", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_mensualidad_pago", "mensualidad", ["pago_id"])
    # Copia del estado del pago que mantiene la propia base: al anular el pago, ON UPDATE CASCADE
    # actualiza la mensualidad en la misma sentencia. Así la regla de entrada solo lee mensualidad.
    op.create_foreign_key("fk_mensualidad_pago", "mensualidad", "pago", ["pago_id", "pago_estado"],
                          ["id", "estado"], onupdate="CASCADE", ondelete="RESTRICT")
    op.create_check_constraint("ck_mensualidad_pago", "mensualidad", "(pago_id IS NULL) = (pago_estado IS NULL)")
    # Mismo vehículo (=) y rangos de fechas con ambos extremos incluidos ('[]') que se cruzan (&&),
    # solo entre periodos pagados y no anulados.
    op.execute("ALTER TABLE mensualidad ADD CONSTRAINT ex_mensualidad_pagada_sin_superposicion "
               "EXCLUDE USING gist (vehiculo_id WITH =, daterange(fecha_inicio, fecha_fin, '[]') WITH &&) "
               "WHERE (pago_estado = 'VALIDO')")

    op.execute(FUNCION_PAGO)
    op.execute("CREATE TRIGGER pago_sin_cambios BEFORE UPDATE OR DELETE ON pago "
               "FOR EACH ROW EXECUTE FUNCTION pago_solo_anular()")
    op.execute("CREATE TRIGGER pago_sin_vaciar BEFORE TRUNCATE ON pago "
               "FOR EACH STATEMENT EXECUTE FUNCTION pago_solo_anular()")
    op.execute(FUNCION_MENSUALIDAD)
    op.execute("CREATE TRIGGER mensualidad_pagada_sin_cambios BEFORE UPDATE OR DELETE ON mensualidad "
               "FOR EACH ROW EXECUTE FUNCTION mensualidad_pagada_inmutable()")
    op.execute("CREATE TRIGGER mensualidad_pagada_sin_vaciar BEFORE TRUNCATE ON mensualidad "
               "FOR EACH STATEMENT EXECUTE FUNCTION mensualidad_sin_vaciar()")

    avisar_superposiciones_antiguas()


def avisar_superposiciones_antiguas() -> None:
    """Informa, sin modificarlos, los periodos antiguos que se superponen (la exclusión no los cubre)."""
    if context.is_offline_mode():
        op.execute(f"""
            DO $$
            DECLARE total integer;
            BEGIN
                SELECT count(*) INTO total FROM ({SUPERPOSICIONES}) s;
                IF total > 0 THEN
                    RAISE WARNING 'Hay % pares de periodos antiguos que se superponen: no se modifican (D10).', total;
                END IF;
            END $$;
        """)
        return
    filas = op.get_bind().execute(sa.text(SUPERPOSICIONES)).all()
    if filas:
        detalle = "; ".join(f"{f.placa} {f.fecha_inicio}..{f.fecha_fin} con {f.inicio_b}..{f.fin_b}" for f in filas)
        aviso.warning("Hay %d par(es) de periodos antiguos que se superponen; no se modifican (D10) y la "
                      "exclusión de la 0010 no los cubre: %s", len(filas), detalle)


def downgrade() -> None:
    # Solo para una reversión deliberada: elimina los pagos y deja los periodos que generaron
    # como periodos sin pago (aún habilitan la entrada si no estaban anulados; los anulados se borran).
    op.execute("DROP TRIGGER mensualidad_pagada_sin_vaciar ON mensualidad")
    op.execute("DROP TRIGGER mensualidad_pagada_sin_cambios ON mensualidad")
    op.execute("DROP FUNCTION mensualidad_sin_vaciar()")
    op.execute("DROP FUNCTION mensualidad_pagada_inmutable()")
    op.execute("DROP TRIGGER pago_sin_vaciar ON pago")
    op.execute("DROP TRIGGER pago_sin_cambios ON pago")
    op.execute("DROP FUNCTION pago_solo_anular()")
    op.execute("DELETE FROM mensualidad WHERE pago_estado = 'ANULADO'")
    op.execute("ALTER TABLE mensualidad DROP CONSTRAINT ex_mensualidad_pagada_sin_superposicion")
    op.drop_constraint("ck_mensualidad_pago", "mensualidad", type_="check")
    op.drop_constraint("fk_mensualidad_pago", "mensualidad", type_="foreignkey")
    op.drop_constraint("uq_mensualidad_pago", "mensualidad", type_="unique")
    op.drop_column("mensualidad", "pago_estado")
    op.drop_column("mensualidad", "pago_id")
    op.drop_index("ix_pago_fecha", table_name="pago")
    op.drop_table("pago")   # también elimina la secuencia, que le pertenece (OWNED BY)
    # btree_gist se deja instalada: otra base u objeto podría usarla.
