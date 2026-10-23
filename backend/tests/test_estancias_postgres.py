"""Concurrencia real: datos nuevos confirmados, limpieza exclusiva por sus ids.

Basado en las pruebas del profesor; reescrito en la Iteración 1 porque la entrada ya no
recibe celda_id: el sistema asigna la celda libre del tipo correcto que lleva más tiempo libre.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import threading
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from conftest import ALEMBIC_HEAD, placa_aleatoria
from app.database import get_engine
from app.domain.reglas import fin_de_mensualidad, hoy_bogota
from app.main import app
from app.models import Celda, Cliente, CorreccionCelda, Estancia, Mensualidad, Novedad, Operador, Vehiculo

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requiere PostgreSQL local.')


@pytest.fixture
def datos(request):
    """Vehículos 0 y 1: motos con mensualidad vigente. 2: moto con mensualidad vencida.
    3: automóvil vigente (no hay celdas de carro). Celdas de moto: 2, o las indicadas en param."""
    cantidad_celdas = getattr(request, 'param', 2)
    engine = get_engine()
    with engine.connect() as c:
        assert c.scalar(text('SELECT current_database()')) == 'autos_colombia'
        assert c.scalar(text('SELECT version_num FROM alembic_version')) == ALEMBIC_HEAD
        if c.scalar(text('SELECT count(*) FROM celda')):
            # La asignación elige entre TODAS las celdas libres: hace falta la base de pruebas vacía.
            pytest.skip('Requiere la base de pruebas vacía: docker compose run --rm backend-tests')
    token = 'TEST-EST-' + uuid4().hex.upper()
    hoy = hoy_bogota()
    with Session(engine) as s, s.begin():
        owner = Cliente(documento=token, nombre='Prueba', telefono='001')
        s.add(owner)
        s.flush()
        tipos = ['MOTO', 'MOTO', 'MOTO', 'AUTOMOVIL']
        vehicles = [Vehiculo(placa=placa_aleatoria(t), color='Prueba', modelo=2026, marca='Prueba',
                             tipo=t, cliente_id=owner.id) for t in tipos]
        # Códigos ordenados (A, B, ...): sin uso previo se asigna primero por código.
        cells = [Celda(codigo=f'{token}-{chr(65 + n)}', tipo='MOTO') for n in range(cantidad_celdas)]
        operators = [Operador(nombre=f'{token}-{n}', telefono='001') for n in range(2)]
        s.add_all(vehicles + cells + operators)
        s.flush()
        vigente = (hoy - timedelta(days=3), fin_de_mensualidad(hoy - timedelta(days=3)))
        vencida = (hoy - timedelta(days=40), hoy - timedelta(days=10))
        for vehicle, (inicio, fin) in zip(vehicles, [vigente, vigente, vencida, vigente]):
            s.add(Mensualidad(vehiculo_id=vehicle.id, fecha_inicio=inicio, fecha_fin=fin))
        data = {'v': [v.id for v in vehicles], 'placas': [v.placa for v in vehicles],
                'c': [c.id for c in cells], 'codigos': [c.codigo for c in cells],
                'o': [o.id for o in operators], 'cliente': owner.id}
    try:
        yield data
    finally:
        with Session(engine) as s, s.begin():
            estancias = select(Estancia.id).where(Estancia.vehiculo_id.in_(data['v']))
            s.execute(delete(CorreccionCelda).where(CorreccionCelda.estancia_id.in_(estancias)))
            s.execute(delete(Novedad).where(Novedad.estancia_id.in_(estancias)))
            s.execute(delete(Estancia).where(Estancia.vehiculo_id.in_(data['v'])))
            s.execute(delete(Mensualidad).where(Mensualidad.vehiculo_id.in_(data['v'])))
            s.execute(delete(Vehiculo).where(Vehiculo.id.in_(data['v'])))
            s.execute(delete(Celda).where(Celda.id.in_(data['c'])))
            s.execute(delete(Operador).where(Operador.id.in_(data['o'])))
            s.execute(delete(Cliente).where(Cliente.id == data['cliente']))
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(Estancia).where(Estancia.vehiculo_id.in_(data['v']))) == 0


def entrada(d, v=0, o=0):
    return {'placa': d['placas'][v], 'operador_id': d['o'][o]}


def cantidad(d):
    with Session(get_engine()) as s:
        return s.scalar(select(func.count()).select_from(Estancia).where(Estancia.vehiculo_id.in_(d['v'])))


def disponible_desde(codigo):
    with Session(get_engine()) as s:
        return s.scalar(select(Celda.disponible_desde).where(Celda.codigo == codigo))


def test_recorrido_asignacion_reglas_y_permanencia(datos):
    d = datos
    A, B = d['codigos']
    with TestClient(app) as client:
        url = '/estancias/vehiculo/' + d['placas'][0]
        outside = client.get(url)
        assert outside.status_code == 200
        assert outside.json()['estancia'] is None and not outside.json()['esta_dentro']
        # Referencias inexistentes: 404 sin cambios.
        assert client.post('/estancias/entrada', json={**entrada(d), 'placa': 'ZZZ999'}).status_code in {404}
        assert client.post('/estancias/entrada', json={**entrada(d), 'operador_id': 9223372036854775807}).status_code == 404
        # Mensualidad vencida: no entra.
        vencida = client.post('/estancias/entrada', json=entrada(d, v=2))
        assert vencida.status_code == 409 and 'mensualidad' in vencida.json()['detail']
        # Automóvil: necesita celda de CARRO y no hay ninguna libre.
        sin_carro = client.post('/estancias/entrada', json=entrada(d, v=3))
        assert sin_carro.status_code == 409 and 'carros' in sin_carro.json()['detail']
        assert cantidad(d) == 0

        placa = d['placas'][0]
        before = datetime.now(timezone.utc)
        result = client.post('/estancias/entrada', json={**entrada(d), 'placa': f' {placa[:3].lower()}-{placa[3:]} '})
        assert result.status_code == 201
        opened = result.json()
        assert opened['placa'] == placa
        assert opened['celda']['codigo'] == A and opened['celda']['tipo'] == 'MOTO'   # nunca usada, primer código
        assert before <= datetime.fromisoformat(opened['entrada']) <= datetime.now(timezone.utc)
        assert opened['salida'] is None and opened['duracion_segundos'] is None
        inside = client.get(url).json()
        assert inside['esta_dentro'] and inside['estancia']['celda']['codigo'] == A
        repetida = client.post('/estancias/entrada', json=entrada(d, o=1))
        assert repetida.status_code == 409 and 'dentro' in repetida.json()['detail']
        assert client.post('/estancias/entrada', json=entrada(d, v=1)).json()['celda']['codigo'] == B
        assert cantidad(d) == 2

        closed = client.post('/estancias/salida', json={'placa': placa, 'operador_id': d['o'][1]})
        assert closed.status_code == 200
        body = closed.json()
        assert body['operador_salida_id'] == d['o'][1] and body['celda']['codigo'] == A
        assert body['duracion_segundos'] >= 0 and body['permanencia'].endswith('min')
        assert disponible_desde(A) == datetime.fromisoformat(body['salida'])   # liberada al salir
        assert client.post('/estancias/salida', json={'placa': placa, 'operador_id': d['o'][0]}).status_code == 409
        assert client.get(url).json()['estancia'] is None
        assert client.post('/estancias/salida', json={'placa': d['placas'][1], 'operador_id': d['o'][0]}).status_code == 200
        assert disponible_desde(A) < disponible_desde(B)
        # Las dos están libres: se asigna A, que lleva más tiempo libre.
        assert client.post('/estancias/entrada', json=entrada(d, v=1)).json()['celda']['codigo'] == A
        assert cantidad(d) == 3
        for route in ('/health', '/vehiculos?limit=1', '/celdas?limit=1', '/operadores?limit=1'):
            assert client.get(route).status_code == 200


def carrera(path, payloads, marca):
    """Envía dos solicitudes a la vez; ambas esperan juntas justo antes de la sentencia marcada."""
    barrier = Barrier(2, timeout=15)
    esperado = threading.local()

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        if marca(statement) and not getattr(esperado, 'listo', False):
            esperado.listo = True
            barrier.wait()

    def enviar(payload):
        with TestClient(app) as client:
            return client.post(path, json=payload)

    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(enviar, payloads))
    finally:
        event.remove(engine, 'before_cursor_execute', sincronizar)


def asignacion_de_celda(statement):
    return 'FROM celda' in statement and 'SKIP LOCKED' in statement


def test_concurrencia_mismo_vehiculo_en_dos_porterias(datos):
    d = datos
    responses = carrera('/estancias/entrada', [entrada(d, o=0), entrada(d, o=1)], asignacion_de_celda)
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert 'dentro' in next(r.json()['detail'] for r in responses if r.status_code == 409)
    assert cantidad(d) == 1


def test_concurrencia_dos_vehiculos_reciben_celdas_distintas(datos):
    d = datos
    responses = carrera('/estancias/entrada', [entrada(d, v=0, o=0), entrada(d, v=1, o=1)], asignacion_de_celda)
    assert [r.status_code for r in responses] == [201, 201]
    assert {r.json()['celda']['codigo'] for r in responses} == set(d['codigos'])
    assert cantidad(d) == 2


@pytest.mark.parametrize('datos', [1], indirect=True)
def test_concurrencia_una_sola_celda_libre(datos):
    d = datos
    responses = carrera('/estancias/entrada', [entrada(d, v=0, o=0), entrada(d, v=1, o=1)], asignacion_de_celda)
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert 'No hay celdas disponibles para motos' in next(r.json()['detail'] for r in responses if r.status_code == 409)
    assert cantidad(d) == 1


def test_concurrencia_dos_salidas(datos):
    d = datos
    with TestClient(app) as client:
        assert client.post('/estancias/entrada', json=entrada(d)).status_code == 201
    payloads = [{'placa': d['placas'][0], 'operador_id': o} for o in d['o']]
    responses = carrera('/estancias/salida', payloads,
                        lambda st: 'FROM estancia' in st and 'FOR UPDATE' in st)
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(r.json() for r in responses if r.status_code == 200)
    assert 'abierta' in next(r.json()['detail'] for r in responses if r.status_code == 409)
    with Session(get_engine()) as s:
        saved = s.get(Estancia, winner['id'])
        assert saved.operador_salida_id == winner['operador_salida_id']
        assert saved.salida == datetime.fromisoformat(winner['salida'])


@pytest.mark.parametrize('datos', [3], indirect=True)
def test_concurrencia_dos_correcciones_hacia_la_misma_celda(datos):
    """Fase 3: dos operadores corrigen a la vez dos estancias hacia la única celda libre (C)."""
    d = datos
    with TestClient(app) as client:
        ids = [client.post('/estancias/entrada', json=entrada(d, v=v)).json()['id'] for v in (0, 1)]
    libre = d['c'][2]
    payloads = [(i, {'celda_id': libre, 'operador_id': d['o'][n], 'motivo': 'Parqueó en C'}) for n, i in enumerate(ids)]
    barrier = Barrier(2, timeout=15)
    esperado = threading.local()

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        if ('FROM celda' in statement and 'FOR UPDATE' in statement and 'SKIP LOCKED' not in statement
                and not getattr(esperado, 'listo', False)):
            esperado.listo = True
            barrier.wait()

    def enviar(item):
        estancia_id, payload = item
        with TestClient(app) as client:
            return client.post(f'/estancias/{estancia_id}/correccion-celda', json=payload)

    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(enviar, payloads))
    finally:
        event.remove(engine, 'before_cursor_execute', sincronizar)
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert 'ocupada' in next(r.json()['detail'] for r in responses if r.status_code == 409)
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Estancia).where(
            Estancia.celda_id == libre, Estancia.salida.is_(None))) == 1
        assert s.scalar(select(func.count()).select_from(CorreccionCelda).where(
            CorreccionCelda.estancia_id.in_(ids))) == 1
