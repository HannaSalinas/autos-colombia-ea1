"""Las semillas crean los casos de demostración y no duplican al repetirse (con rollback)."""

from sqlalchemy import func, select

from app.domain.reglas import hoy_bogota
from app.seed import VEHICULOS, sembrar
from app.models import Vehiculo


def test_semillas_idempotentes_y_casos_de_mensualidad(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    sembrar(session, hoy)
    total = session.scalar(select(func.count()).select_from(Vehiculo))
    assert sembrar(session, hoy) == {"clientes": 0, "vehiculos": 0, "mensualidades": 0}
    assert session.scalar(select(func.count()).select_from(Vehiculo)) == total
    estado = {v["placa"]: v for v in api.get("/vehiculos?limit=100").json()["items"]}
    esperado = {"vigente": True, "vence_hoy": True, "renovada": True,
                "vencida": False, "sin_mensualidad": False, "empieza_manana": False}
    for placa, *_, caso in VEHICULOS:
        assert estado[placa]["mensualidad_vigente"] is esperado[caso], placa
    assert estado["GHI789"]["mensualidad_hasta"] == hoy.isoformat()
    assert estado["MNO654"]["mensualidad_hasta"] is None
