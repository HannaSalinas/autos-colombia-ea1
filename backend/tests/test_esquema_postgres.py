"""Compara los modelos SQLAlchemy con la base migrada por Alembic (agregado en la Iteración 1)."""

import importlib.util
import os
from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.database import get_engine
from app.models import Base

ALEMBIC_INI = str(Path(__file__).resolve().parents[1] / "alembic.ini")


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")
# Al reflejar el CHECK NOT VALID de celda (0004), SQLAlchemy avisa que no reconoce esa opción
# en la comparación. No afecta el resultado: la comparación sigue viendo tablas, columnas e índices.
@pytest.mark.filterwarnings("ignore:Can't validate argument 'dialect_options'")
def test_modelos_y_migraciones_no_tienen_diferencias():
    # Si alguien cambia un modelo sin crear su migración (o al revés), esta lista no queda vacía.
    with get_engine().connect() as connection:
        diferencias = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}),
                                       Base.metadata)
    assert diferencias == []


def test_0005_crea_las_tablas_igual_que_los_modelos(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/0005_correccion_celda_novedad.py"
    spec = importlib.util.spec_from_file_location("migracion_0005", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = sa.MetaData()
    for name in ("cliente", "vehiculo", "celda", "operador", "estancia"):
        Base.metadata.tables[name].to_metadata(metadata)
    monkeypatch.setattr(migration.op, "create_table", lambda name, *args: sa.Table(name, metadata, *args))
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    migration.upgrade()

    def ddl(table):
        return sorted(line.strip().rstrip(",") for line in
                      str(CreateTable(table).compile(dialect=postgresql.dialect())).splitlines())

    for name in ("correccion_celda", "novedad"):
        assert ddl(metadata.tables[name]) == ddl(Base.metadata.tables[name])


def test_sql_offline_de_0005():
    output = StringIO()
    command.upgrade(Config(ALEMBIC_INI, output_buffer=output), "0004:0005", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE correccion_celda" in sql and "CREATE TABLE novedad" in sql
    assert "CHECK (celda_anterior_id <> celda_nueva_id)" in sql
    assert "char_length(motivo) <= 200" in sql
    assert "CHECK (tipo IN ('RAYON', 'GOLPE', 'OBJETO_OLVIDADO', 'OTRO'))" in sql
    assert sql.count("ON DELETE RESTRICT") == 6
    assert "DROP" not in sql


def test_sql_offline_de_0004():
    output = StringIO()
    command.upgrade(Config(ALEMBIC_INI, output_buffer=output), "0003:0004", sql=True)
    sql = output.getvalue()
    assert "ADD COLUMN disponible_desde TIMESTAMP WITH TIME ZONE" in sql
    assert "CHECK (tipo IN ('MOTO', 'CARRO')) NOT VALID" in sql
    assert "CREATE INDEX ix_celda_tipo_disponible ON celda (tipo, disponible_desde)" in sql
    assert "DROP" not in sql


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
