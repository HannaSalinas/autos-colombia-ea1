"""El script de datos de demostración respeta las reglas del negocio (con rollback)."""

from collections import Counter
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.demo import ABIERTAS, generar
from app.domain.reglas import ZONA_BOGOTA, mensualidad_vigente, tipo_celda_para
from app.models import Celda, CorreccionCelda, Estancia, Mensualidad, Novedad, Vehiculo
from app.seed import sembrar


def test_datos_de_demostracion(api_y_sesion):
    api, session = api_y_sesion
    if session.scalar(select(func.count()).select_from(Estancia)):
        pytest.skip("La base ya tiene estancias: el script solo corre sobre una base sin estancias.")
    ahora = datetime.now(timezone.utc)
    sembrar(session, ahora.astimezone(ZONA_BOGOTA).date())
    creados = generar(session, ahora)
    assert creados["estancias_abiertas"] == len(ABIERTAS) == 5
    assert creados["estancias_cerradas"] >= 15 and creados["correcciones"] >= 2 and creados["novedades"] >= 2
    estancias = list(session.scalars(select(Estancia)))
    vehiculos = {v.id: v for v in session.scalars(select(Vehiculo))}
    mensualidades = list(session.scalars(select(Mensualidad)))
    # Varias estancias por placa y reglas respetadas en cada una.
    assert max(Counter(e.vehiculo_id for e in estancias).values()) >= 3
    for e in estancias:
        vehiculo = vehiculos[e.vehiculo_id]
        dia = e.entrada.astimezone(ZONA_BOGOTA).date()
        assert any(mensualidad_vigente(m.fecha_inicio, m.fecha_fin, dia)
                   for m in mensualidades if m.vehiculo_id == vehiculo.id), vehiculo.placa
        assert session.get(Celda, e.celda_id).tipo == tipo_celda_para(vehiculo.tipo)
        assert e.salida is None or e.salida > e.entrada
    # Nunca dos vehículos en la misma celda al mismo tiempo (teniendo en cuenta las correcciones).
    tramos: dict[int, list[tuple[datetime, datetime]]] = {}
    for e in estancias:
        fin = e.salida or ahora
        cambios = sorted(session.scalars(select(CorreccionCelda).where(CorreccionCelda.estancia_id == e.id)),
                         key=lambda c: c.fecha)
        inicio = e.entrada
        for c in cambios:
            tramos.setdefault(c.celda_anterior_id, []).append((inicio, c.fecha))
            inicio = c.fecha
        tramos.setdefault(e.celda_id, []).append((inicio, fin))
    for celda_id, lista in tramos.items():
        lista.sort()
        for (_, fin_a), (inicio_b, _) in zip(lista, lista[1:]):
            assert fin_a <= inicio_b, f"Celda {celda_id} ocupada por dos estancias a la vez"
    assert session.scalar(select(func.count()).select_from(CorreccionCelda)) == creados["correcciones"]
    assert session.scalar(select(func.count()).select_from(Novedad)) == creados["novedades"]
    session.commit()   # cierra la lectura antes de llamar a la API
    reporte = api.get("/reportes/ocupacion").json()
    assert sorted(v["placa"] for v in reporte["dentro"]) == sorted(ABIERTAS)
    assert sum(c["ocupadas"] for c in reporte["celdas"]) == 5
    assert api.get("/reportes/historial", params={"placa": "ABC123"}).json()["total"] >= 2
    with pytest.raises(RuntimeError, match="ya tiene estancias"):
        generar(session, ahora)
