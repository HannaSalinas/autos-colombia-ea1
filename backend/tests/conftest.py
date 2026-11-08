"""Utilidades compartidas por las pruebas (agregado en la Iteración 1)."""

import os
import random
import string
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory

# Revisión más reciente de las migraciones: las pruebas con PostgreSQL exigen la base al día.
ALEMBIC_HEAD = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
).get_current_head()


def codigos_celda_libres(sesion, tipo: str, cantidad: int = 1) -> list[str]:
    """Códigos de celda válidos (C01–C99 o M01–M99, migración 0007) que aún no existen, en orden.

    Se toman los más altos para no chocar con las 80 celdas sembradas (C01–C70, M01–M10).
    `sesion` puede ser una Session o una Connection de SQLAlchemy.
    """
    from sqlalchemy import text as sql
    prefijo = {"CARRO": "C", "MOTO": "M"}[tipo]
    usados = set(sesion.execute(sql("SELECT codigo FROM celda")).scalars())
    libres = [c for c in (f"{prefijo}{n:02d}" for n in range(1, 100)) if c not in usados]
    if len(libres) < cantidad:
        import pytest
        pytest.skip(f"No quedan {cantidad} códigos libres de tipo {tipo} en esta base.")
    return libres[-cantidad:]


def placa_aleatoria(tipo: str = "AUTOMOVIL") -> str:
    """Placa válida al azar para no chocar con datos existentes (ABC123 o ABC12D)."""
    letras = "".join(random.choices(string.ascii_uppercase, k=3))
    if tipo == "MOTO":
        return letras + "".join(random.choices(string.digits, k=2)) + random.choice(string.ascii_uppercase)
    return letras + "".join(random.choices(string.digits, k=3))


# Iteración 2: los tokens se firman con JWT_SECRETO. Si la prueba corre sin .env (por ejemplo,
# solo las pruebas sin base de datos), se usa una clave de prueba; nunca es la del sistema real.
os.environ.setdefault("JWT_SECRETO", "clave-de-firma-solo-para-pruebas-automatizadas")

# --- Fixture con PostgreSQL real y rollback (mismo patrón de test_vehiculos_postgres.py) ---
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import get_engine, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CuentaUsuario, Operador  # noqa: E402
from app.routers.dependencias import sesion_actual  # noqa: E402
from app.services.autenticacion import SesionActual  # noqa: E402
from app.services.seguridad import crear_token, hash_contrasena  # noqa: E402

# --- Iteración 2: cuentas y sesiones para las pruebas ---

CLAVE_PRUEBAS = "clave-de-prueba-1"


@lru_cache
def hash_pruebas() -> str:
    """bcrypt de costo 12 tarda ~0,5 s: se calcula una sola vez para todas las pruebas."""
    return hash_contrasena(CLAVE_PRUEBAS)


def crear_cuenta(sesion, rol: str = "ADMINISTRADOR", operador_id: int | None = None,
                 usuario: str | None = None, activa: bool = True) -> CuentaUsuario:
    """Crea (con flush, sin commit) una cuenta con la contraseña CLAVE_PRUEBAS. Si no se indica la
    persona, crea una nueva."""
    if operador_id is None:
        persona = Operador(nombre=f"Persona {uuid4().hex[:8]}")
        sesion.add(persona)
        sesion.flush()
        operador_id = persona.id
    cuenta = CuentaUsuario(operador_id=operador_id, nombre_usuario=usuario or f"prueba.{uuid4().hex[:12]}",
                           hash_contrasena=hash_pruebas(), rol=rol, activa=activa, version_sesion=0)
    sesion.add(cuenta)
    sesion.flush()
    return cuenta


def encabezado(cuenta: CuentaUsuario) -> dict[str, str]:
    """Encabezado Authorization con un token válido para esa cuenta."""
    token, _ = crear_token(cuenta.id, cuenta.version_sesion)
    return {"Authorization": f"Bearer {token}"}


def autenticar(api, sesion, rol: str = "ADMINISTRADOR", operador_id: int | None = None) -> CuentaUsuario:
    """Cambia la cuenta con la que el TestClient hace las solicitudes."""
    cuenta = crear_cuenta(sesion, rol=rol, operador_id=operador_id)
    api.headers.update(encabezado(cuenta))
    return cuenta


def sesion_falsa(rol: str = "ADMINISTRADOR", operador_id: int = 1) -> SesionActual:
    """Para pruebas sin base de datos: reemplaza la dependencia de sesión (app.dependency_overrides)."""
    return SesionActual(cuenta_id=1, operador_id=operador_id, nombre_usuario="prueba", nombre="Prueba", rol=rol,
                        version_sesion=0)


@pytest.fixture
def sin_autenticacion_real():
    """Pruebas sin PostgreSQL: la API responde como si hubiera iniciado sesión un Administrador."""
    app.dependency_overrides[sesion_actual] = lambda: sesion_falsa()
    try:
        yield
    finally:
        app.dependency_overrides.pop(sesion_actual, None)


@pytest.fixture
def api_y_sesion():
    """TestClient + la misma sesión que usa la API, dentro de una transacción que se revierte.

    La sesión permite preparar datos (clientes, mensualidades, estancias) sin endpoints de escritura.
    Iteración 2: el cliente ya viene autenticado como Administrador; para actuar como otra cuenta
    se usa autenticar(api, session, rol=..., operador_id=...).
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
                        autenticar(api, session)
                        yield api, session
                finally:
                    app.dependency_overrides.pop(get_session, None)
        finally:
            transaction.rollback()
