"""Compara los modelos SQLAlchemy con la base migrada por Alembic (agregado en la Iteración 1)."""

import os
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.database import get_engine
from app.models import Base

ALEMBIC_INI = str(Path(__file__).resolve().parents[1] / "alembic.ini")


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")
def test_modelos_y_migraciones_no_tienen_diferencias():
    # Si alguien cambia un modelo sin crear su migración (o al revés), esta lista no queda vacía.
    with get_engine().connect() as connection:
        diferencias = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}),
                                       Base.metadata)
    assert diferencias == []


def test_sql_offline_de_0003():
    output = StringIO()
    command.upgrade(Config(ALEMBIC_INI, output_buffer=output), "0002:0003", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE cliente" in sql and "CREATE TABLE mensualidad" in sql
    assert "ALTER TABLE vehiculo ADD COLUMN cliente_id BIGINT NOT NULL" in sql
    assert "CONSTRAINT uq_cliente_documento UNIQUE (documento)" in sql
    assert "CHECK (fecha_fin > fecha_inicio)" in sql
    assert "CHECK (modelo >= 1900)" in sql
    assert sql.count("ON DELETE RESTRICT") == 2
    assert "DROP" not in sql
