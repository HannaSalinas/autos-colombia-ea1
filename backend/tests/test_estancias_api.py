from fastapi.testclient import TestClient
import pytest

from app.main import app


def test_openapi_y_salud():
    with TestClient(app) as client:
        schema = client.get('/openapi.json').json()
        for path, method in [('/estancias/entrada', 'post'), ('/estancias/salida', 'post'),
                             ('/estancias/vehiculo/{placa}', 'get')]:
            assert method in schema['paths'][path]
        assert client.get('/health').json() == {'status': 'ok'}


# Iteración 1: la entrada recibe solo placa y operador; la celda la asigna el sistema.
# Iteración 2: tampoco recibe operador (el responsable sale de la sesión, D7): enviarlo da 422.
# Se conservan los casos de la Iteración 1 y se agrega uno con placa válida y operador.
@pytest.mark.parametrize('payload', [
    {}, {'placa': ' ', 'operador_id': 1}, {'placa': ' - ', 'operador_id': 1},
    {'placa': ' '}, {'placa': 'ABC123', 'operador_id': 1},
    {'placa': None, 'operador_id': 1},
    {'placa': 'TEST', 'operador_id': 0},
    {'placa': 'TEST', 'operador_id': True},
    {'placa': 'TEST', 'operador_id': '1'},
    {'placa': 'TEST', 'operador_id': None},
    {'placa': 'TEST', 'operador_id': 9223372036854775808},
    {'placa': 'TEST', 'operador_id': 1, 'entrada': '2026-01-01'},
    {'placa': 'TEST', 'operador_id': 1, 'celda_id': 1},
])
def test_entrada_invalida(payload, sin_autenticacion_real):
    with TestClient(app) as client:
        assert client.post('/estancias/entrada', json=payload).status_code == 422


def test_salida_no_admite_celda_ni_fecha(sin_autenticacion_real):
    with TestClient(app) as client:
        # Iteración 2: tampoco admite operador_id.
        for extra in ({'celda_id': 1}, {'salida': '2026-01-01'}, {'id': 1}, {'operador_id': 1}):
            assert client.post('/estancias/salida', json={'placa': 'TEST', **extra}).status_code == 422
        assert client.get('/estancias/vehiculo/%20%20').status_code == 422
