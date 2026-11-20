"""Migración 0011: valida los CHECK de cliente solo si todos los clientes existentes los cumplen.

Mismo criterio que la 0008 con las celdas. Las pruebas con PostgreSQL bajan y suben migraciones,
así que solo corren sobre la base de pruebas desechable. Al terminar, la base queda en la última
revisión con los CHECK validados.
"""

import logging
import os
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from conftest import ALEMBIC_HEAD
from app.database import get_engine

ALEMBIC_INI = str(Path(__file__).resolve().parents[1] / "alembic.ini")
CHECKS = ("ck_cliente_documento_formato", "ck_cliente_nombre_longitud", "ck_cliente_telefono_formato")


def validados(connection) -> dict[str, bool]:
    return dict(connection.execute(text("SELECT conname, convalidated FROM pg_constraint WHERE conname = ANY(:n)"),
                                   {"n": list(CHECKS)}).all())


def test_sql_offline_de_0011_decide_segun_los_datos():
    output = StringIO()
    command.upgrade(Config(ALEMBIC_INI, output_buffer=output), "0010:0011", sql=True)
    sql = output.getvalue()
    for nombre in CHECKS:
        assert f"ALTER TABLE cliente VALIDATE CONSTRAINT {nombre};" in sql
        assert f"RAISE WARNING '{nombre} queda NOT VALID" in sql
    assert "DROP" not in sql


@pytest.fixture
def base_de_pruebas_vacia():
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Activa RUN_POSTGRES_TESTS=1 para probar con PostgreSQL.")
    with get_engine().connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
        if c.scalar(text("SELECT count(*) FROM celda")):
            pytest.skip("Baja y sube migraciones: requiere la base de pruebas vacía "
                        "(docker compose run --rm backend-tests).")
    config = Config(ALEMBIC_INI)
    yield config
    command.upgrade(config, "head")


def test_si_todos_los_clientes_cumplen_los_check_quedan_validados(base_de_pruebas_vacia):
    config = base_de_pruebas_vacia
    command.downgrade(config, "0010")
    cliente = None
    try:
        with get_engine().begin() as c:
            assert validados(c) == dict.fromkeys(CHECKS, False)
            # Un cliente antiguo que sí cumple las reglas nuevas no impide validar.
            cliente = c.scalar(text("INSERT INTO cliente (tipo_documento, documento, nombre, telefono) "
                                    "VALUES ('CC', '1099000111', 'Cliente que cumple', '3001112233') RETURNING id"))
        command.upgrade(config, "head")
        with get_engine().connect() as c:
            assert validados(c) == dict.fromkeys(CHECKS, True)
            # Validado, el CHECK sigue rechazando clientes nuevos que no cumplen.
            with pytest.raises(IntegrityError) as error:
                c.execute(text("INSERT INTO cliente (tipo_documento, documento, nombre, telefono) "
                               "VALUES ('CC', '1099000222', 'Ana', '300')"))
            assert error.value.orig.diag.constraint_name == "ck_cliente_telefono_formato"
    finally:
        with get_engine().begin() as c:
            if cliente is not None:
                c.execute(text("DELETE FROM cliente WHERE id = :i"), {"i": cliente})


def test_si_algun_cliente_no_cumple_ese_check_queda_not_valid_y_avisa(base_de_pruebas_vacia, caplog):
    config = base_de_pruebas_vacia
    engine = get_engine()
    command.downgrade(config, "0010")      # los CHECK están NOT VALID: se puede guardar un cliente antiguo
    cliente = None
    try:
        with engine.begin() as c:
            # Solo el teléfono incumple (como un cliente de la EA1 con un teléfono corto). Para guardarlo se
            # simula un dato antiguo: el CHECK NOT VALID se quita un momento y se vuelve a crear igual.
            c.execute(text("ALTER TABLE cliente DROP CONSTRAINT ck_cliente_telefono_formato"))
            cliente = c.scalar(text("INSERT INTO cliente (tipo_documento, documento, nombre, telefono) "
                                    "VALUES ('CC', '1099000333', 'Cliente de la EA1', '300') RETURNING id"))
            c.execute(text("ALTER TABLE cliente ADD CONSTRAINT ck_cliente_telefono_formato "
                           "CHECK (telefono ~ '^[0-9]{10}$') NOT VALID"))
        with caplog.at_level(logging.WARNING, logger="alembic.migraciones"):
            command.upgrade(config, "head")             # no se detiene
        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
            # Cada CHECK se decide por separado: documento y nombre cumplen; el teléfono, no.
            assert validados(c) == {"ck_cliente_documento_formato": True, "ck_cliente_nombre_longitud": True,
                                    "ck_cliente_telefono_formato": False}
            assert c.scalar(text("SELECT telefono FROM cliente WHERE id = :i"), {"i": cliente}) == "300"
        avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("ck_cliente_telefono_formato queda NOT VALID" in a and f"ids {cliente}" in a for a in avisos)
        assert not any("ck_cliente_documento_formato" in a or "ck_cliente_nombre_longitud" in a for a in avisos)
        # El aviso usa ids, nunca el documento (dato personal).
        assert not any("1099000333" in a for a in avisos)
    finally:
        with engine.begin() as c:
            if cliente is not None:
                c.execute(text("DELETE FROM cliente WHERE id = :i"), {"i": cliente})
        # Sin el cliente que no cumple, volver a pasar por la 0011 deja los tres CHECK validados.
        command.downgrade(config, "0010")
        command.upgrade(config, "head")
        with engine.connect() as c:
            assert validados(c) == dict.fromkeys(CHECKS, True)
