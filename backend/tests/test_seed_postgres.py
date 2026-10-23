"""Las semillas crean los casos de demostración y no duplican al repetirse (con rollback)."""

from datetime import timedelta

from sqlalchemy import func, select

from app.domain.reglas import hoy_bogota
from app.seed import VEHICULOS, sembrar
from app.models import Celda, Vehiculo


def test_semillas_idempotentes_y_casos_de_mensualidad(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    sembrar(session, hoy)
    total = session.scalar(select(func.count()).select_from(Vehiculo))
    assert set(sembrar(session, hoy).values()) == {0}
    assert session.scalar(select(func.count()).select_from(Vehiculo)) == total
    estado = {v["placa"]: v for v in api.get("/vehiculos?limit=100").json()["items"]}
    esperado = {"vigente": True, "vence_hoy": True, "renovada": True,
                "vencida": False, "sin_mensualidad": False, "empieza_manana": False}
    for placa, *_, caso in VEHICULOS:
        assert estado[placa]["mensualidad_vigente"] is esperado[caso], placa
    assert estado["GHI789"]["mensualidad_hasta"] == hoy.isoformat()
    assert estado["MNO654"]["mensualidad_hasta"] is None
    # Mensualidad futura: la pantalla muestra "Empieza el ...".
    assert estado["PQR98B"]["mensualidad_proxima"] == (hoy + timedelta(days=1)).isoformat()


def test_semillas_crean_80_celdas_por_tipo(api_y_sesion):
    _, session = api_y_sesion
    sembrar(session, hoy_bogota())
    codigos = {c.codigo: c.tipo for c in session.scalars(select(Celda).where(Celda.codigo.regexp_match("^[CM][0-9]{2}$")))}
    assert sum(t == "CARRO" for t in codigos.values()) == 70 and codigos["C70"] == "CARRO"
    assert sum(t == "MOTO" for t in codigos.values()) == 10 and codigos["M10"] == "MOTO"
