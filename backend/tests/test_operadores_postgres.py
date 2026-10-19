"""CRUD en autos_colombia, sin DDL y con rollback de todos los datos nuevos."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import get_engine, get_session
from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local."
)


def test_operadores_structure_and_crud():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT current_database()")) == "autos_colombia"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) in {"0001", "0002"}
            inspector = inspect(connection)
            columns = {c["name"]: c for c in inspector.get_columns("operador")}
            assert set(columns) == {"id", "nombre", "telefono"}
            assert str(columns["id"]["type"]) == "BIGINT"
            assert columns["id"]["identity"]["always"] is True
            assert all(not c["nullable"] for c in columns.values())
            assert str(columns["nombre"]["type"]) == str(columns["telefono"]["type"]) == "TEXT"
            assert inspector.get_pk_constraint("operador")["constrained_columns"] == ["id"]
            assert not inspector.get_unique_constraints("operador")
            assert {c["name"] for c in inspector.get_check_constraints("operador")} == {
                "ck_operador_nombre_no_vacio", "ck_operador_telefono_no_vacio"
            }
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                def override():
                    yield session

                app.dependency_overrides[get_session] = override
                with TestClient(app) as client:
                    initial = client.get("/operadores").json()
                    assert initial["offset"] == 0 and initial["limit"] == 20
                    name = "TEST-OPERADOR-" + uuid4().hex
                    payload = {"nombre": f" {name} ", "telefono": " +57 00123 "}
                    created = client.post("/operadores", json=payload)
                    assert created.status_code == 201
                    item = created.json()
                    assert item == {"id": item["id"], "nombre": name, "telefono": "+57 00123"}
                    assert type(item["id"]) is int and item["id"] > 0
                    path = f"/operadores/{item['id']}"
                    assert client.get(path).json() == item
                    # Nombre y teléfono repetidos están permitidos.
                    duplicate = client.post("/operadores", json=payload)
                    assert duplicate.status_code == 201
                    duplicate_id = duplicate.json()["id"]
                    assert duplicate_id != item["id"]
                    page = client.get(f"/operadores?offset={initial['total']}&limit=2")
                    assert page.status_code == 200
                    assert page.json() == {"items": [item, duplicate.json()],
                                           "total": initial["total"] + 2,
                                           "offset": initial["total"], "limit": 2}
                    for query in ("limit=0", "limit=101", "offset=-1"):
                        assert client.get("/operadores?" + query).status_code == 422
                    for invalid_id in ("0", "-1", "9223372036854775808", "abc"):
                        assert client.get("/operadores/" + invalid_id).status_code == 422
                    for invalid in ({"nombre": None}, {"telefono": None},
                                    {"nombre": " \t"}, {"telefono": ""}, {"id": 2}):
                        assert client.patch(path, json=invalid).status_code == 422
                    assert client.post("/operadores", json={}).status_code == 422
                    assert client.patch(path, json={}).json() == item
                    changed = client.patch(path, json={"telefono": " 00045 "})
                    assert changed.status_code == 200
                    item["telefono"] = "00045"
                    assert changed.json() == item
                    changed = client.patch(path, json={"nombre": " " + name + " editado "})
                    assert changed.status_code == 200
                    item["nombre"] = name + " editado"
                    assert changed.json() == item
                    assert client.get(path).json() == item
                    for new_id in (item["id"], duplicate_id):
                        deleted = client.delete(f"/operadores/{new_id}")
                        assert deleted.status_code == 204 and deleted.content == b""
                    assert client.get(path).status_code == 404
                    assert client.patch(path, json={"nombre": name}).status_code == 404
                    assert client.delete(path).status_code == 404
                    assert client.get("/operadores").json()["total"] == initial["total"]
                    assert client.get("/health").json() == {"status": "ok"}
                    assert client.get("/vehiculos?limit=1").status_code == 200
                    assert client.get("/celdas?limit=1").status_code == 200
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
