"""Integración Fase 3: corrección de celda y novedades (PostgreSQL real, con rollback)."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from conftest import placa_aleatoria
from app.domain.reglas import MOTIVO_MAXIMO, fin_de_mensualidad, hoy_bogota
from app.models import Celda, Cliente, CorreccionCelda, Estancia, Mensualidad, Operador, Vehiculo


@pytest.fixture
def escena(api_y_sesion):
    """Un automóvil dentro en la celda X; celdas de carro Y (libre) y Z (ocupada por otro); celda de moto M."""
    api, session = api_y_sesion
    token = uuid4().hex[:8].upper()
    cliente = Cliente(documento=f"TEST-{token}", nombre="Prueba", telefono="001")
    session.add(cliente)
    session.flush()
    carro, otro = (Vehiculo(placa=placa_aleatoria(), color="Rojo", modelo=2024, marca="M", tipo="AUTOMOVIL",
                            cliente_id=cliente.id) for _ in range(2))
    celdas = {k: Celda(codigo=f"T{token}-{k}", tipo="MOTO" if k == "M" else "CARRO") for k in "XYZM"}
    operador = Operador(nombre=f"TEST-{token}", telefono="001")
    session.add_all([carro, otro, operador, *celdas.values()])
    session.flush()
    inicio = hoy_bogota() - timedelta(days=2)
    session.add(Mensualidad(vehiculo_id=carro.id, fecha_inicio=inicio, fecha_fin=fin_de_mensualidad(inicio)))
    estancia = Estancia(vehiculo_id=carro.id, celda_id=celdas["X"].id, operador_entrada_id=operador.id)
    session.add_all([estancia, Estancia(vehiculo_id=otro.id, celda_id=celdas["Z"].id, operador_entrada_id=operador.id)])
    # El servicio de estancias abre su propia transacción (session.begin()): se cierra la de la
    # preparación. Con join_transaction_mode="create_savepoint" esto solo libera un savepoint;
    # todo se revierte igual al final de la prueba. Se devuelven ids y códigos (no objetos del
    # ORM) porque leer un objeto expirado abriría otra transacción en la misma sesión.
    session.commit()
    ids = SimpleNamespace(
        estancia=estancia.id, operador=operador.id, placa=carro.placa,
        celda={k: SimpleNamespace(id=c.id, codigo=c.codigo) for k, c in celdas.items()},
    )
    return api, session, ids


def corregir(api, d, destino, motivo="Parqueó en otra celda"):
    return api.post(f"/estancias/{d.estancia}/correccion-celda",
                    json={"celda_id": d.celda[destino].id, "operador_id": d.operador, "motivo": motivo})


def test_celdas_disponibles_solo_libres_y_compatibles(escena):
    api, _, d = escena
    respuesta = api.get(f"/estancias/{d.estancia}/celdas-disponibles")
    assert respuesta.status_code == 200
    codigos = {c["codigo"] for c in respuesta.json()}
    assert d.celda["Y"].codigo in codigos
    assert not codigos & {d.celda[k].codigo for k in "XZM"}
    assert api.get("/estancias/9223372036854775807/celdas-disponibles").status_code == 404


def test_corrige_la_celda_y_deja_registro(escena):
    api, session, d = escena
    respuesta = corregir(api, d, "Y", motivo="  El conductor   parqueó en Y ")
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["celda_anterior"]["codigo"] == d.celda["X"].codigo
    assert cuerpo["celda_nueva"]["codigo"] == d.celda["Y"].codigo
    assert cuerpo["motivo"] == "El conductor parqueó en Y" and cuerpo["operador_id"] == d.operador
    estado = api.get(f"/estancias/vehiculo/{d.placa}").json()
    assert estado["estancia"]["celda"]["codigo"] == d.celda["Y"].codigo
    # La celda anterior queda libre (y al final de la fila de asignación).
    assert session.scalar(select(Celda.disponible_desde).where(Celda.id == d.celda["X"].id)) is not None
    session.commit()  # cierra la lectura antes de volver a llamar al servicio
    disponibles = {c["codigo"] for c in api.get(f"/estancias/{d.estancia}/celdas-disponibles").json()}
    assert d.celda["X"].codigo in disponibles and d.celda["Y"].codigo not in disponibles
    historial = api.get(f"/estancias/{d.estancia}/correcciones").json()
    assert [(c["celda_anterior"]["codigo"], c["celda_nueva"]["codigo"]) for c in historial] == [
        (d.celda["X"].codigo, d.celda["Y"].codigo)]
    # Se puede corregir otra vez (por ejemplo, de vuelta a X): queda una segunda línea.
    assert corregir(api, d, "X").status_code == 201
    assert len(api.get(f"/estancias/{d.estancia}/correcciones").json()) == 2


@pytest.mark.parametrize("destino,mensaje", [("M", "necesita celda de carro"), ("Z", "ocupada"), ("X", "ya está registrado")])
def test_corregir_rechaza_celdas_no_validas(escena, destino, mensaje):
    api, _, d = escena
    respuesta = corregir(api, d, destino)
    assert respuesta.status_code == 409 and mensaje in respuesta.json()["detail"]
    assert api.get(f"/estancias/{d.estancia}/correcciones").json() == []


@pytest.mark.parametrize("cambios,estado", [
    ({"motivo": "   "}, 422), ({"motivo": "a" * (MOTIVO_MAXIMO + 1)}, 422), ({"motivo": None}, 422),
    ({"celda_id": 9223372036854775807}, 404), ({"operador_id": 9223372036854775807}, 404),
    ({"fecha": "2026-01-01"}, 422),
])
def test_corregir_valida_datos(escena, cambios, estado):
    api, _, d = escena
    payload = {"celda_id": d.celda["Y"].id, "operador_id": d.operador, "motivo": "Motivo", **cambios}
    assert api.post(f"/estancias/{d.estancia}/correccion-celda", json=payload).status_code == estado


def test_novedades(escena):
    api, _, d = escena
    url = f"/estancias/{d.estancia}/novedades"
    assert api.get(url).json() == []
    for tipo, descripcion in [("RAYON", "Rayón en la puerta derecha"), ("OBJETO_OLVIDADO", " Celular  en la silla ")]:
        creada = api.post(url, json={"tipo": tipo, "descripcion": descripcion, "operador_id": d.operador})
        assert creada.status_code == 201 and creada.json()["tipo"] == tipo
    lista = api.get(url).json()
    assert [n["descripcion"] for n in lista] == ["Rayón en la puerta derecha", "Celular en la silla"]
    for invalido in ({"tipo": "CAMION"}, {"descripcion": " "}, {"descripcion": "a" * 501}, {"operador_id": 0}):
        payload = {"tipo": "GOLPE", "descripcion": "Golpe", "operador_id": d.operador, **invalido}
        assert api.post(url, json=payload).status_code == 422
    assert api.post("/estancias/9223372036854775807/novedades",
                    json={"tipo": "GOLPE", "descripcion": "x", "operador_id": d.operador}).status_code == 404


def test_estancia_cerrada_no_se_modifica_pero_conserva_historial(escena):
    api, _, d = escena
    url = f"/estancias/{d.estancia}/novedades"
    assert api.post(url, json={"tipo": "GOLPE", "descripcion": "Golpe leve", "operador_id": d.operador}).status_code == 201
    assert api.post("/estancias/salida", json={"placa": d.placa, "operador_id": d.operador}).status_code == 200
    assert corregir(api, d, "Y").json()["detail"].startswith("La estancia ya está cerrada")
    cerrada = api.post(url, json={"tipo": "OTRO", "descripcion": "Tarde", "operador_id": d.operador})
    assert cerrada.status_code == 409
    assert len(api.get(url).json()) == 1
    assert api.get(f"/estancias/{d.estancia}/celdas-disponibles").status_code == 409


@pytest.mark.parametrize("sql", [
    "INSERT INTO correccion_celda (estancia_id, celda_anterior_id, celda_nueva_id, operador_id, motivo) "
    "VALUES (:e, :x, :x, :o, 'misma celda')",
    "INSERT INTO correccion_celda (estancia_id, celda_anterior_id, celda_nueva_id, operador_id, motivo) "
    "VALUES (:e, :x, :y, :o, '  ')",
    "INSERT INTO novedad (estancia_id, operador_id, tipo, descripcion) VALUES (:e, :o, 'CAMION', 'x')",
    "INSERT INTO novedad (estancia_id, operador_id, tipo, descripcion) VALUES (:e, :o, 'GOLPE', ' ')",
    "DELETE FROM estancia WHERE id = :e",   # con novedades o correcciones el historial no se borra
])
def test_restricciones_de_la_base(escena, sql):
    _, session, d = escena
    session.add(CorreccionCelda(estancia_id=d.estancia, celda_anterior_id=d.celda["X"].id,
                                celda_nueva_id=d.celda["Y"].id, operador_id=d.operador, motivo="Previa"))
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(text(sql), {"e": d.estancia, "x": d.celda["X"].id, "y": d.celda["Y"].id, "o": d.operador})


def test_no_cambia_el_tipo_de_una_celda_ocupada(escena):
    """Fase 4: la celda X tiene un automóvil dentro; su tipo no puede pasar a MOTO."""
    api, _, d = escena
    ocupada = api.patch(f"/celdas/{d.celda['X'].id}", json={"tipo": "MOTO"})
    assert ocupada.status_code == 409 and "ocupada" in ocupada.json()["detail"]
    assert api.get(f"/celdas/{d.celda['X'].id}").json()["tipo"] == "CARRO"
    # El código sí se puede corregir, y la celda libre Y sí puede cambiar de tipo.
    assert api.patch(f"/celdas/{d.celda['X'].id}", json={"tipo": "CARRO"}).status_code == 200
    assert api.patch(f"/celdas/{d.celda['Y'].id}", json={"tipo": "MOTO"}).json()["tipo"] == "MOTO"
