"""Errores HTTP y rollback sin depender de PostgreSQL.

Iteración 2: /operadores quedó solo de consulta y solo para el Administrador (las personas se crean
con su cuenta, D3; nada se borra, D4). Las pruebas de escritura del proyecto base se conservan con
los mismos casos, pero ahora comprueban que POST, PATCH y DELETE ya no existen (405) y no escriben.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from conftest import sesion_falsa
from app.database import get_session
from app.main import app
from app.models import Operador
from app.routers.dependencias import sesion_actual


@pytest.fixture
def api():
    session = MagicMock()
    session.get.return_value = Operador(id=1, nombre="Prueba", telefono="001")

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[sesion_actual] = lambda: sesion_falsa("ADMINISTRADOR")
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(sesion_actual, None)


def sin_escrituras(session) -> None:
    session.commit.assert_not_called()
    session.add.assert_not_called()
    session.delete.assert_not_called()


@pytest.mark.parametrize("field", ["nombre", "telefono"])
@pytest.mark.parametrize("value", [None, "", " \t\n", 123, True, []])
def test_invalid_fields_are_422_without_writes(api, field, value):
    # Antes: 422 por campo inválido. Ahora no hay POST ni PATCH: 405 con cualquier dato.
    client, session = api
    payload = {"nombre": "Prueba", "telefono": "001", field: value}
    assert client.post("/operadores", json=payload).status_code == 405
    assert client.patch("/operadores/1", json={field: value}).status_code == 405
    sin_escrituras(session)


@pytest.mark.parametrize("payload", [{}, {"nombre": "Prueba"}, {"telefono": "001"},
                                     {"nombre": "Prueba", "telefono": "001", "id": 1}])
def test_creation_requires_fields_and_forbids_id(api, payload):
    # Antes: 422 sin campos obligatorios o con id. Ahora crear personas sueltas no existe: 405.
    client, session = api
    assert client.post("/operadores", json=payload).status_code == 405
    sin_escrituras(session)


def test_patch_forbids_id_and_unknown_fields(api):
    # Antes: 422 con id o campos desconocidos. Ahora editar personas no existe (D6): 405.
    client, session = api
    for payload in ({"id": 2}, {"rol": "admin"}, {"nombre": "Válido"}):
        assert client.patch("/operadores/1", json=payload).status_code == 405
    sin_escrituras(session)


@pytest.mark.parametrize("sqlstate, status", [("23503", 409), ("23502", 422), ("23514", 422)])
def test_database_conflicts_roll_back_and_hide_details(api, sqlstate, status):
    # Antes: DELETE con error de la base respondía 409 o 422 sin detalles. Ahora no hay DELETE (D4):
    # 405, sin tocar la base, aunque la base fuera a fallar.
    client, session = api
    driver_error = Exception("PRIVATE DRIVER DETAILS")
    driver_error.sqlstate = sqlstate
    result = client.delete("/operadores/1")
    assert result.status_code == 405
    assert "PRIVATE" not in result.text
    sin_escrituras(session)
    session.get.assert_not_called()


def test_database_failure_rolls_back_and_is_generic(api):
    client, session = api
    session.get.side_effect = SQLAlchemyError("PRIVATE DRIVER DETAILS")
    result = client.get("/operadores/1")
    assert result.status_code == 503
    assert "PRIVATE" not in result.text
    session.rollback.assert_called_once()


def test_operador_no_consulta_personas(api):
    """Iteración 2: consultar personas es del Administrador; el Operador recibe 403."""
    client, session = api
    app.dependency_overrides[sesion_actual] = lambda: sesion_falsa("OPERADOR")
    assert client.get("/operadores").status_code == 403
    assert client.get("/operadores/1").status_code == 403
    session.get.assert_not_called()
