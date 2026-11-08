"""Operadores (personas) en autos_colombia, sin DDL y con rollback de todos los datos nuevos.

Iteración 2: la ruta quedó de solo consulta para el Administrador; la prueba conserva su estructura
y sus casos, pero las escrituras ahora deben responder 405.
"""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from conftest import ALEMBIC_HEAD, autenticar
from app.database import get_engine, get_session
from app.main import app
from app.models import Operador

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local."
)


def test_operadores_structure_and_crud():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT current_database()")) == "autos_colombia"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
            inspector = inspect(connection)
            columns = {c["name"]: c for c in inspector.get_columns("operador")}
            assert set(columns) == {"id", "nombre", "telefono"}
            assert str(columns["id"]["type"]) == "BIGINT"
            assert columns["id"]["identity"]["always"] is True
            # Iteración 2 (0006): el teléfono es opcional; el formulario de cuentas no lo pide.
            assert all(not c["nullable"] for n, c in columns.items() if n != "telefono")
            assert columns["telefono"]["nullable"]
            assert str(columns["nombre"]["type"]) == str(columns["telefono"]["type"]) == "TEXT"
            assert inspector.get_pk_constraint("operador")["constrained_columns"] == ["id"]
            assert not inspector.get_unique_constraints("operador")
            assert {c["name"] for c in inspector.get_check_constraints("operador")} == {
                "ck_operador_nombre_no_vacio", "ck_operador_telefono_no_vacio",
                "ck_operador_nombre_longitud",   # Iteración 2 (0006): de 3 a 80 caracteres
            }
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                def override():
                    yield session

                app.dependency_overrides[get_session] = override
                with TestClient(app) as client:
                    # Iteración 2: /operadores es de solo consulta y solo para el Administrador. Las
                    # personas se crean con su cuenta; aquí se preparan directamente en la base.
                    autenticar(client, session)
                    initial = client.get("/operadores").json()
                    assert initial["offset"] == 0 and initial["limit"] == 20
                    name = "TEST-OPERADOR-" + uuid4().hex
                    personas = [Operador(nombre=f" {name} ", telefono=" +57 00123 ") for _ in range(2)]
                    session.add_all(personas)
                    session.flush()
                    item = {"id": personas[0].id, "nombre": name, "telefono": "+57 00123"}
                    duplicate_id = personas[1].id
                    assert type(item["id"]) is int and item["id"] > 0 and duplicate_id != item["id"]
                    path = f"/operadores/{item['id']}"
                    assert client.get(path).json() == item
                    # Nombre y teléfono repetidos están permitidos.
                    page = client.get(f"/operadores?offset={initial['total']}&limit=2")
                    assert page.status_code == 200
                    assert page.json() == {"items": [item, {**item, "id": duplicate_id}],
                                           "total": initial["total"] + 2,
                                           "offset": initial["total"], "limit": 2}
                    for query in ("limit=0", "limit=101", "offset=-1"):
                        assert client.get("/operadores?" + query).status_code == 422
                    for invalid_id in ("0", "-1", "9223372036854775808", "abc"):
                        assert client.get("/operadores/" + invalid_id).status_code == 422
                    # Antes: crear, editar y borrar personas. Ahora esos métodos no existen (405)
                    # y la persona queda igual (D4: nada se borra; D6: no se editan las cuentas).
                    for invalid in ({"nombre": None}, {"telefono": None},
                                    {"nombre": " \t"}, {"telefono": ""}, {"id": 2}, {"telefono": " 00045 "}):
                        assert client.patch(path, json=invalid).status_code == 405
                    assert client.post("/operadores", json={"nombre": name, "telefono": "1"}).status_code == 405
                    for new_id in (item["id"], duplicate_id):
                        assert client.delete(f"/operadores/{new_id}").status_code == 405
                    assert client.get(path).json() == item
                    assert client.get("/operadores").json()["total"] == initial["total"] + 2
                    assert client.get("/operadores/9223372036854775807").status_code == 404
                    assert client.get("/health").json() == {"status": "ok"}
                    assert client.get("/vehiculos?limit=1").status_code == 200
                    assert client.get("/celdas?limit=1").status_code == 200
                    # El Operador no consulta personas.
                    autenticar(client, session, rol="OPERADOR")
                    assert client.get("/operadores").status_code == 403
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
