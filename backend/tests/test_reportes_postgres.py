"""Integración Fase 4: reporte de ocupación e historial (PostgreSQL real, con rollback)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from conftest import placa_aleatoria
from app.domain.reglas import ZONA_BOGOTA
from app.models import Celda, Cliente, CorreccionCelda, Estancia, Novedad, Operador, Vehiculo


def bogota(*args) -> datetime:
    return datetime(*args, tzinfo=ZONA_BOGOTA)


@pytest.fixture
def datos(api_y_sesion):
    """Una moto con tres estancias: dos cerradas en los bordes del día y una abierta ahora."""
    api, session = api_y_sesion
    token = uuid4().hex[:8].upper()
    cliente = Cliente(documento=f"TEST-{token}", nombre="Prueba", telefono="001")
    session.add(cliente)
    session.flush()
    moto = Vehiculo(placa=placa_aleatoria("MOTO"), color="Azul", modelo=2024, marca="M", tipo="MOTO",
                    cliente_id=cliente.id)
    celdas = [Celda(codigo=f"T{token}-{n}", tipo="MOTO") for n in range(2)]
    entrada_op = Operador(nombre=f"Entrada {token}", telefono="1")
    salida_op = Operador(nombre=f"Salida {token}", telefono="2")
    session.add_all([moto, entrada_op, salida_op, *celdas])
    session.flush()
    a = Estancia(vehiculo_id=moto.id, celda_id=celdas[0].id, operador_entrada_id=entrada_op.id,
                 entrada=bogota(2026, 10, 20, 23, 30), salida=bogota(2026, 10, 21, 1, 45),
                 operador_salida_id=salida_op.id)
    b = Estancia(vehiculo_id=moto.id, celda_id=celdas[1].id, operador_entrada_id=entrada_op.id,
                 entrada=bogota(2026, 10, 21, 0, 0), salida=bogota(2026, 10, 21, 8, 5),
                 operador_salida_id=salida_op.id)
    c = Estancia(vehiculo_id=moto.id, celda_id=celdas[0].id, operador_entrada_id=entrada_op.id,
                 entrada=datetime.now(timezone.utc) - timedelta(hours=2, minutes=5))
    session.add_all([a, b, c])
    session.flush()
    session.add_all([
        Novedad(estancia_id=b.id, operador_id=entrada_op.id, tipo="RAYON", descripcion="Rayón"),
        Novedad(estancia_id=b.id, operador_id=salida_op.id, tipo="GOLPE", descripcion="Golpe"),
        CorreccionCelda(estancia_id=b.id, celda_anterior_id=celdas[0].id, celda_nueva_id=celdas[1].id,
                        operador_id=entrada_op.id, motivo="Parqueó al lado"),
    ])
    session.commit()  # libera el savepoint de preparación; todo se revierte al final
    return api, SimpleNamespace(placa=moto.placa, ids=[a.id, b.id, c.id], token=token,
                                celdas=[x.codigo for x in celdas])


def historial(api, **params):
    return api.get("/reportes/historial", params=params)


def test_historial_por_placa_ordenado_y_con_detalle(datos):
    api, d = datos
    respuesta = historial(api, placa=f"{d.placa[:3].lower()}-{d.placa[3:]}")
    assert respuesta.status_code == 200
    pagina = respuesta.json()
    assert pagina["total"] == 3
    assert [e["id"] for e in pagina["items"]] == list(reversed(d.ids))   # más reciente primero
    abierta, b, a = pagina["items"]
    assert abierta["abierta"] and abierta["salida"] is None and abierta["permanencia"] is None
    assert a["permanencia"] == "2 h 15 min" and a["duracion_segundos"] == 8100
    assert b["permanencia"] == "8 h 05 min" and b["celda"] == d.celdas[1]
    assert b["novedades"] == 2 and b["correcciones"] == 1 and a["novedades"] == 0
    assert a["operador_entrada"] == f"Entrada {d.token}" and a["operador_salida"] == f"Salida {d.token}"
    assert a["tipo_vehiculo"] == "MOTO"


@pytest.mark.parametrize("desde,hasta,esperados", [
    ("2026-10-20", "2026-10-20", [0]),        # 23:30 del 20 sigue siendo el 20 en Bogotá
    ("2026-10-21", "2026-10-21", [1]),        # 00:00 del 21 ya es el 21
    ("2026-10-20", "2026-10-21", [1, 0]),
    ("2026-10-22", None, [2]),                # desde: solo la abierta de hoy
    (None, "2026-10-20", [0]),
])
def test_historial_por_rango_de_fechas_de_bogota(datos, desde, hasta, esperados):
    api, d = datos
    params = {"placa": d.placa, **({"desde": desde} if desde else {}), **({"hasta": hasta} if hasta else {})}
    assert [e["id"] for e in historial(api, **params).json()["items"]] == [d.ids[i] for i in esperados]


def test_historial_paginado_y_validaciones(datos):
    api, d = datos
    segunda = historial(api, placa=d.placa, limit=1, offset=1).json()
    assert segunda["total"] == 3 and [e["id"] for e in segunda["items"]] == [d.ids[1]]
    assert historial(api, placa="ZZZ999").json() == {"items": [], "total": 0, "offset": 0, "limit": 20}
    rango = historial(api, desde="2026-10-22", hasta="2026-10-21")
    assert rango.status_code == 422 and "posterior" in rango.json()["detail"]
    for params in ({"desde": "22-10-2026"}, {"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert historial(api, **params).status_code == 422
    # Sin filtros devuelve todo el historial (al menos estas tres).
    assert historial(api, limit=100).json()["total"] >= 3


def test_ocupacion(datos):
    api, d = datos
    reporte = api.get("/reportes/ocupacion")
    assert reporte.status_code == 200
    cuerpo = reporte.json()
    motos = next(c for c in cuerpo["celdas"] if c["tipo"] == "MOTO")
    carros = next(c for c in cuerpo["celdas"] if c["tipo"] == "CARRO")
    assert motos["libres"] == motos["total"] - motos["ocupadas"] and motos["ocupadas"] >= 1
    assert carros["libres"] == carros["total"] - carros["ocupadas"]
    dentro = next(v for v in cuerpo["dentro"] if v["placa"] == d.placa)
    assert dentro["celda"] == d.celdas[0] and dentro["tipo_vehiculo"] == "MOTO"
    assert dentro["estancia_id"] == d.ids[2] and dentro["tiempo"] == "2 h 05 min"
    assert dentro["operador_entrada"] == f"Entrada {d.token}"
    # Las estancias cerradas no aparecen dentro.
    assert sum(v["placa"] == d.placa for v in cuerpo["dentro"]) == 1
