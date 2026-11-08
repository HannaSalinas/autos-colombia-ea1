"""Migración 0008: valida los CHECK de celda solo si todas las filas existentes los cumplen.

Las pruebas con PostgreSQL bajan y suben migraciones, así que solo corren sobre la base de pruebas
desechable (sin celdas). Al terminar, la base queda en la última revisión con los CHECK validados.
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
CHECKS = ("ck_celda_tipo", "ck_celda_codigo_formato")


def validados(connection) -> dict[str, bool]:
    filas = connection.execute(text("SELECT conname, convalidated FROM pg_constraint WHERE conname = ANY(:n)"),
                               {"n": list(CHECKS)}).all()
    return dict(filas)


def test_sql_offline_de_0008_decide_segun_los_datos():
    output = StringIO()
    command.upgrade(Config(ALEMBIC_INI, output_buffer=output), "0007:0008", sql=True)
    sql = output.getvalue()
    for nombre in CHECKS:
        assert f"ALTER TABLE celda VALIDATE CONSTRAINT {nombre};" in sql
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


def test_si_todas_las_celdas_cumplen_los_check_quedan_validados(base_de_pruebas_vacia):
    config = base_de_pruebas_vacia
    command.downgrade(config, "0007")
    with get_engine().connect() as c:
        assert validados(c) == {"ck_celda_tipo": False, "ck_celda_codigo_formato": False}
    command.upgrade(config, "head")
    with get_engine().connect() as c:
        assert validados(c) == {"ck_celda_tipo": True, "ck_celda_codigo_formato": True}
        # Validado o no, el CHECK sigue rechazando celdas nuevas que no cumplen.
        with pytest.raises(IntegrityError) as error:
            c.execute(text("INSERT INTO celda (codigo, tipo) VALUES ('ZONA-B', 'CARRO')"))
        assert error.value.orig.diag.constraint_name == "ck_celda_codigo_formato"


def test_si_alguna_celda_no_cumple_queda_not_valid_y_avisa(base_de_pruebas_vacia, caplog):
    config = base_de_pruebas_vacia
    engine = get_engine()
    command.downgrade(config, "0006")       # antes del CHECK de formato: se puede guardar 'ZONA-A'
    celda = None
    try:
        with engine.begin() as c:
            celda = c.scalar(text("INSERT INTO celda (codigo, tipo) VALUES ('ZONA-A', 'CARRO') RETURNING id"))
        with caplog.at_level(logging.WARNING, logger="alembic.migraciones"):
            command.upgrade(config, "head")             # no se detiene
        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
            # Cada CHECK se decide por separado: el tipo CARRO cumple; el código 'ZONA-A', no.
            assert validados(c) == {"ck_celda_tipo": True, "ck_celda_codigo_formato": False}
            assert c.scalar(text("SELECT codigo FROM celda WHERE id = :i"), {"i": celda}) == "ZONA-A"
        avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("ck_celda_codigo_formato queda NOT VALID" in a and "ZONA-A" in a for a in avisos)
        assert not any("ck_celda_tipo" in a for a in avisos)
    finally:
        with engine.begin() as c:
            if celda is not None:
                c.execute(text("DELETE FROM celda WHERE id = :i"), {"i": celda})
        command.upgrade(config, "head")
        # Sin la celda mala, volver a pasar por la 0008 deja los dos CHECK validados.
        command.downgrade(config, "0007")
        command.upgrade(config, "head")
        with engine.connect() as c:
            assert validados(c) == {"ck_celda_tipo": True, "ck_celda_codigo_formato": True}
