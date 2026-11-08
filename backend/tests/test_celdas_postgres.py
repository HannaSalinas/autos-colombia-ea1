"""Integración optativa sin DDL; todos los datos nuevos se revierten."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conftest import autenticar, codigos_celda_libres
from app.database import get_engine, get_session
from app.main import app

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


@pytest.fixture
def connection():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT current_database()")) == "autos_colombia"
            yield connection
        finally:
            transaction.rollback()


def test_celda_schema_and_constraints(connection):
    inspector = inspect(connection)
    columns = {c['name']: c for c in inspector.get_columns('celda')}
    # disponible_desde (0004); ubicacion y habilitada (0007).
    assert set(columns) == {'id', 'codigo', 'tipo', 'disponible_desde', 'ubicacion', 'habilitada'}
    assert str(columns['id']['type']) == 'BIGINT'
    assert columns['id']['identity']['always']
    assert all(not c['nullable'] for n, c in columns.items() if n not in {'disponible_desde', 'ubicacion'})
    assert inspector.get_pk_constraint('celda')['constrained_columns'] == ['id']
    assert any(c['column_names'] == ['codigo'] for c in inspector.get_unique_constraints('celda'))
    # Iteración 2: el código debe ser C01–C99 (carro) o M01–M99 (moto), CHECK de la migración 0007.
    code, other = codigos_celda_libres(connection, 'CARRO', 2)
    moto = codigos_celda_libres(connection, 'MOTO')[0]
    connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code,'type':'CARRO'})
    # Iteración 1: el tipo debe ser MOTO o CARRO (CHECK ck_celda_tipo de la migración 0004).
    for code_value, kind, state in [(code,'CARRO','23505'), (' lowercase ','CARRO','23514'),
                                    (' \t','CARRO','23514'), (moto,' \t','23514'),
                                    (moto,'Libre','23514'),
                                    (None,'CARRO','23502'), (other,None,'23502'),
                                    # Iteración 2: formato y prefijo según el tipo (0007).
                                    (code.lower(),'CARRO','23514'), ('C00','CARRO','23514'),
                                    ('C100','CARRO','23514'), (moto,'CARRO','23514'), (other,'MOTO','23514')]:
        with pytest.raises(IntegrityError) as error:
            with connection.begin_nested():
                connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code_value,'type':kind})
        assert error.value.orig.sqlstate == state


def test_crud_celdas(connection):
    with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
        def override():
            yield session
        app.dependency_overrides[get_session] = override
        try:
            with TestClient(app) as client:
                autenticar(client, session)   # Iteración 2: con sesión de Administrador
                code = codigos_celda_libres(session, 'CARRO')[0]   # Iteración 2: formato C01–C99
                payload = {'codigo': f' {code.lower()} ', 'tipo': ' carro '}
                result = client.post('/celdas', json=payload)
                assert result.status_code == 201
                item = result.json()
                assert item['codigo'] == code and item['tipo'] == 'CARRO'
                path = f"/celdas/{item['id']}"
                assert client.get(path).json() == item
                assert client.post('/celdas', json=payload).status_code == 409
                page = client.get('/celdas?offset=0&limit=1')
                assert page.status_code == 200 and len(page.json()['items']) == 1
                assert client.get('/celdas?limit=0').status_code == 422
                for invalid in ({'id':1}, {'codigo':None}, {'tipo':' \t'}, {'tipo':None}, {'tipo':'Libre'}):
                    assert client.patch(path, json=invalid).status_code == 422
                assert client.post('/celdas', json={}).status_code == 422
                # Iteración 2: el código debe empezar por la letra del tipo, así que cambian juntos.
                moto = codigos_celda_libres(session, 'MOTO')[0]
                changed = client.patch(path, json={'codigo': moto, 'tipo':'moto'})
                assert changed.status_code == 200 and changed.json()['tipo'] == 'MOTO'
                deleted = client.delete(path)
                assert deleted.status_code == 204 and deleted.content == b''
                assert client.get(path).status_code == 404
                assert client.patch(path, json={'tipo':'CARRO'}).status_code == 404
                assert client.delete(path).status_code == 404
                assert client.get('/health').json() == {'status':'ok'}
        finally:
            app.dependency_overrides.pop(get_session, None)
