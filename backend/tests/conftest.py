"""Utilidades compartidas por las pruebas (agregado en la Iteración 1)."""

import random
import string
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

# Revisión más reciente de las migraciones: las pruebas con PostgreSQL exigen la base al día.
ALEMBIC_HEAD = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
).get_current_head()


def placa_aleatoria(tipo: str = "AUTOMOVIL") -> str:
    """Placa válida al azar para no chocar con datos existentes (ABC123 o ABC12D)."""
    letras = "".join(random.choices(string.ascii_uppercase, k=3))
    if tipo == "MOTO":
        return letras + "".join(random.choices(string.digits, k=2)) + random.choice(string.ascii_uppercase)
    return letras + "".join(random.choices(string.digits, k=3))


# --- Fixture con PostgreSQL real y rollback (mismo patrón de test_vehiculos_postgres.py) ---
import os  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import get_engine, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def api_y_sesion():
    """TestClient + la misma sesión que usa la API, dentro de una transacción que se revierte.

    La sesión permite preparar datos (clientes, mensualidades, estancias) sin endpoints de escritura.
    """
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Activa RUN_POSTGRES_TESTS=1 para probar con PostgreSQL.")
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
            # expire_on_commit=False: tras session.commit() (que aquí solo libera un savepoint)
            # los objetos preparados se pueden leer sin abrir otra transacción en la sesión.
            with Session(bind=connection, join_transaction_mode="create_savepoint",
                         expire_on_commit=False) as session:
                def override_session():
                    yield session
                app.dependency_overrides[get_session] = override_session
                try:
                    with TestClient(app) as api:
                        yield api, session
                finally:
                    app.dependency_overrides.pop(get_session, None)
        finally:
            transaction.rollback()
