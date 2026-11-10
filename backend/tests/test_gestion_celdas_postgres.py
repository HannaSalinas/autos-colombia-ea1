"""Gestión de celdas (Iteración 2).

HU-22 Consultar celdas, HU-23 Registrar celda, HU-24 Editar celda, HU-25 Inhabilitar o rehabilitar;
RF-31 (auditoría), RNF-17 (bloqueos y unicidad bajo concurrencia) y RNF-18 (sin borrado).
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from conftest import autenticar, codigos_celda_libres, crear_cuenta, encabezado, placa_aleatoria
from app.database import get_engine
from app.domain.reglas import fin_de_mensualidad, hoy_bogota
from app.main import app
from app.models import (
    AuditoriaCelda, Celda, Cliente, CorreccionCelda, CuentaUsuario, Estancia, Mensualidad, Operador, Vehiculo,
)


# --- Ayudantes (todo dentro de la transacción que se revierte) ---

def nueva_celda(session, tipo="CARRO", **campos) -> Celda:
    celda = Celda(codigo=codigos_celda_libres(session, tipo)[0], tipo=tipo, **campos)
    session.add(celda)
    session.flush()
    return celda


def vehiculo_vigente(session, tipo="AUTOMOVIL") -> Vehiculo:
    cliente = Cliente(documento=f"TEST-{placa_aleatoria()}{time.time_ns()}", nombre="Prueba", telefono="001")
    session.add(cliente)
    session.flush()
    vehiculo = Vehiculo(placa=placa_aleatoria(tipo), color="Rojo", modelo=2024, marca="M", tipo=tipo,
                        cliente_id=cliente.id)
    session.add(vehiculo)
    session.flush()
    inicio = hoy_bogota() - timedelta(days=2)
    session.add(Mensualidad(vehiculo_id=vehiculo.id, fecha_inicio=inicio, fecha_fin=fin_de_mensualidad(inicio)))
    session.flush()
    return vehiculo


def estancia(session, celda: Celda, cerrada: bool = False) -> Estancia:
    persona = Operador(nombre="Persona de portería")
    session.add(persona)
    session.flush()
    ahora = datetime.now(timezone.utc)
    e = Estancia(vehiculo_id=vehiculo_vigente(session).id, celda_id=celda.id, operador_entrada_id=persona.id,
                 entrada=ahora - timedelta(hours=2),
                 salida=ahora - timedelta(hours=1) if cerrada else None,
                 operador_salida_id=persona.id if cerrada else None)
    session.add(e)
    session.flush()
    return e


def sin_otras_celdas_libres(session, tipo: str) -> None:
    """La asignación elige entre todas las celdas libres: algunas pruebas necesitan que no haya otras."""
    libres = session.scalar(select(func.count()).select_from(Celda).where(
        Celda.tipo == tipo, Celda.habilitada.is_(True),
        ~select(Estancia.id).where(Estancia.celda_id == Celda.id, Estancia.salida.is_(None)).exists()))
    if libres:
        pytest.skip("Requiere la base de pruebas vacía: docker compose run --rm backend-tests")


# --- HU-22 Consultar celdas ---

def test_listado_con_estado_ubicacion_y_placa(api_y_sesion):
    api, session = api_y_sesion
    libre = nueva_celda(session, ubicacion="Sótano 1")
    ocupada = nueva_celda(session)
    dentro = estancia(session, ocupada)
    inhabilitada = nueva_celda(session, habilitada=False)
    placa = session.get(Vehiculo, dentro.vehiculo_id).placa
    autenticar(api, session, rol="OPERADOR")   # HU-22: el Operador también consulta
    items = {c["codigo"]: c for c in api.get("/celdas", params={"limit": 100}).json()["items"]}
    assert {k: items[libre.codigo][k] for k in ("tipo", "ubicacion", "estado", "placa", "habilitada")} == {
        "tipo": "CARRO", "ubicacion": "Sótano 1", "estado": "LIBRE", "placa": None, "habilitada": True}
    assert items[ocupada.codigo]["estado"] == "OCUPADA" and items[ocupada.codigo]["placa"] == placa
    assert items[inhabilitada.codigo]["estado"] == "INHABILITADA"
    assert items[ocupada.codigo]["tiene_historial"] and not items[libre.codigo]["tiene_historial"]


def test_busqueda_por_codigo_y_filtros(api_y_sesion):
    api, session = api_y_sesion
    carro = nueva_celda(session)
    moto = nueva_celda(session, tipo="MOTO", habilitada=False)

    def codigos(**params):
        respuesta = api.get("/celdas", params={"limit": 100, **params})
        assert respuesta.status_code == 200
        return {c["codigo"] for c in respuesta.json()["items"]}

    assert codigos(buscar=carro.codigo.lower()) == {carro.codigo}
    assert moto.codigo in codigos(tipo="MOTO") and carro.codigo not in codigos(tipo="MOTO")
    assert moto.codigo in codigos(estado="INHABILITADA") and carro.codigo not in codigos(estado="INHABILITADA")
    assert carro.codigo in codigos(estado="LIBRE", tipo="CARRO")
    assert codigos(buscar="%") == set()
    for malo in ({"tipo": "CAMION"}, {"estado": "BORRADA"}, {"buscar": "x" * 11}):
        assert api.get("/celdas", params=malo).status_code == 422


# --- HU-23 Registrar celda ---

@pytest.mark.parametrize("codigo,tipo", [("C01", "CARRO"), ("C99", "CARRO"), ("M01", "MOTO"), ("M99", "MOTO")])
def test_crea_celda_en_el_limite_libre_y_auditada(api_y_sesion, codigo, tipo):
    api, session = api_y_sesion
    if session.scalar(select(Celda.id).where(Celda.codigo == codigo)):
        pytest.skip(f"{codigo} ya existe en esta base.")
    admin = autenticar(api, session)
    respuesta = api.post("/celdas", json={"codigo": f" {codigo.lower()} ", "tipo": tipo, "ubicacion": " Piso 2 "})
    assert respuesta.status_code == 201
    celda = respuesta.json()
    assert {k: celda[k] for k in ("codigo", "tipo", "ubicacion", "estado", "habilitada", "disponible_desde")} == {
        "codigo": codigo, "tipo": tipo, "ubicacion": "Piso 2", "estado": "LIBRE", "habilitada": True,
        "disponible_desde": None}                       # NULL = nunca usada: se asigna primero
    auditoria = api.get(f"/celdas/{celda['id']}").json()["auditoria"]
    assert [(a["accion"], a["actor"]) for a in auditoria] == [
        ("CREAR", f"{admin.persona.nombre} ({admin.nombre_usuario})")]


@pytest.mark.parametrize("cuerpo", [
    {"codigo": "C00", "tipo": "CARRO"}, {"codigo": "C100", "tipo": "CARRO"}, {"codigo": "M05", "tipo": "CARRO"},
    {"codigo": "C05", "tipo": "MOTO"}, {"codigo": "X05", "tipo": "CARRO"}, {"codigo": "   ", "tipo": "CARRO"},
    {"codigo": "C05", "tipo": "CAMION"}, {"codigo": "C05", "tipo": "CARRO", "ubicacion": "a" * 61},
    {"codigo": "C05", "tipo": "CARRO", "habilitada": False}, {"codigo": "C05", "tipo": "CARRO", "id": 1},
])
def test_rechaza_codigos_y_datos_fuera_de_regla(api_y_sesion, cuerpo):
    api, session = api_y_sesion
    antes = session.scalar(select(func.count()).select_from(Celda))
    assert api.post("/celdas", json=cuerpo).status_code == 422
    assert session.scalar(select(func.count()).select_from(Celda)) == antes


def test_codigo_existente_aun_con_otras_mayusculas_o_espacios(api_y_sesion):
    api, session = api_y_sesion
    existente = nueva_celda(session)
    for variante in (existente.codigo, f" {existente.codigo.lower()} "):
        respuesta = api.post("/celdas", json={"codigo": variante, "tipo": "CARRO"})
        assert respuesta.status_code == 409 and respuesta.json() == {"detail": "Ya existe una celda con ese código."}


def test_ubicacion_vacia_o_de_60(api_y_sesion):
    api, session = api_y_sesion
    a, b = codigos_celda_libres(session, "MOTO", 2)
    assert api.post("/celdas", json={"codigo": a, "tipo": "MOTO", "ubicacion": "   "}).json()["ubicacion"] is None
    assert api.post("/celdas", json={"codigo": b, "tipo": "MOTO", "ubicacion": "u" * 60}).json()["ubicacion"] == "u" * 60


def test_celda_nueva_queda_disponible_para_la_asignacion(api_y_sesion):
    """HU-23.1."""
    api, session = api_y_sesion
    sin_otras_celdas_libres(session, "MOTO")
    codigo = api.post("/celdas", json={"codigo": codigos_celda_libres(session, "MOTO")[0], "tipo": "MOTO"}).json()["codigo"]
    moto = vehiculo_vigente(session, "MOTO")
    session.commit()
    entrada = api.post("/estancias/entrada", json={"placa": moto.placa})
    assert entrada.status_code == 201 and entrada.json()["celda"]["codigo"] == codigo


# --- HU-24 Editar celda ---

def test_ubicacion_de_cualquier_celda_se_puede_editar(api_y_sesion):
    api, session = api_y_sesion
    ocupada = nueva_celda(session)
    estancia(session, ocupada)
    respuesta = api.patch(f"/celdas/{ocupada.id}", json={"ubicacion": " Zona norte "})
    assert respuesta.status_code == 200 and respuesta.json()["ubicacion"] == "Zona norte"
    assert api.patch(f"/celdas/{ocupada.id}", json={"ubicacion": ""}).json()["ubicacion"] is None
    assert api.patch(f"/celdas/{ocupada.id}", json={"ubicacion": "a" * 61}).status_code == 422
    auditoria = api.get(f"/celdas/{ocupada.id}").json()["auditoria"]
    assert [(a["accion"], a["detalle"]) for a in auditoria] == [
        ("EDITAR", "ubicación: — → Zona norte"), ("EDITAR", "ubicación: Zona norte → —")]
    # Enviar los mismos valores no es un cambio: no se audita.
    assert api.patch(f"/celdas/{ocupada.id}", json={"ubicacion": None, "codigo": ocupada.codigo}).status_code == 200
    assert len(api.get(f"/celdas/{ocupada.id}").json()["auditoria"]) == 2


def test_codigo_y_tipo_de_una_celda_nueva_se_pueden_cambiar(api_y_sesion):
    api, session = api_y_sesion
    celda = nueva_celda(session)
    moto = codigos_celda_libres(session, "MOTO")[0]
    respuesta = api.patch(f"/celdas/{celda.id}", json={"codigo": f" {moto.lower()} ", "tipo": "moto"})
    assert respuesta.status_code == 200 and (respuesta.json()["codigo"], respuesta.json()["tipo"]) == (moto, "MOTO")
    # Mismas validaciones del registro: un cambio parcial que deja código y tipo incompatibles se rechaza.
    assert api.patch(f"/celdas/{celda.id}", json={"tipo": "CARRO"}).status_code == 422
    assert api.patch(f"/celdas/{celda.id}", json={"codigo": "C00"}).status_code == 422
    otra = nueva_celda(session, tipo="MOTO")
    assert api.patch(f"/celdas/{celda.id}", json={"codigo": otra.codigo}).status_code == 409


@pytest.mark.parametrize("situacion", ["ocupada", "historial_estancia", "historial_correccion"])
def test_codigo_y_tipo_fijos_si_esta_ocupada_o_tiene_historial(api_y_sesion, situacion):
    """D8 y HU-24.3. La celda que solo aparece como 'celda anterior' de una corrección también
    tiene historial, aunque ninguna estancia la nombre ya."""
    api, session = api_y_sesion
    celda = nueva_celda(session)
    if situacion == "ocupada":
        estancia(session, celda)
    elif situacion == "historial_estancia":
        estancia(session, celda, cerrada=True)
    else:
        destino = nueva_celda(session)
        e = estancia(session, celda)
        session.add(CorreccionCelda(estancia_id=e.id, celda_anterior_id=celda.id, celda_nueva_id=destino.id,
                                    operador_id=e.operador_entrada_id, motivo="Parqueó en otra"))
        e.celda_id = destino.id
        session.flush()
    otro = codigos_celda_libres(session, "CARRO")[0]
    for cambio in ({"codigo": otro}, {"codigo": codigos_celda_libres(session, "MOTO")[0], "tipo": "MOTO"}):
        respuesta = api.patch(f"/celdas/{celda.id}", json=cambio)
        assert respuesta.status_code == 409
        assert ("ocupada" if situacion == "ocupada" else "ya tuvo movimientos") in respuesta.json()["detail"]
    assert session.get(Celda, celda.id).codigo == celda.codigo
    assert api.patch(f"/celdas/{celda.id}", json={"ubicacion": "Sigue editable"}).status_code == 200


# --- HU-25 Inhabilitar o rehabilitar ---

@pytest.mark.parametrize("con_historial", [False, True])
def test_inhabilita_una_celda_libre_con_o_sin_historial(api_y_sesion, con_historial):
    api, session = api_y_sesion
    celda = nueva_celda(session)
    if con_historial:
        estancia(session, celda, cerrada=True)
    respuesta = api.post(f"/celdas/{celda.id}/inhabilitar")
    assert respuesta.status_code == 200
    assert (respuesta.json()["estado"], respuesta.json()["habilitada"]) == ("INHABILITADA", False)
    assert api.post(f"/celdas/{celda.id}/inhabilitar").status_code == 409
    # HU-25.5: su historial sigue consultable.
    assert api.get(f"/celdas/{celda.id}").status_code == 200


def test_celda_ocupada_no_se_inhabilita(api_y_sesion):
    api, session = api_y_sesion
    celda = nueva_celda(session)
    estancia(session, celda)
    respuesta = api.post(f"/celdas/{celda.id}/inhabilitar")
    assert respuesta.status_code == 409
    assert respuesta.json() == {"detail": f"La celda {celda.codigo} está ocupada: primero debe salir el vehículo."}
    assert session.get(Celda, celda.id).habilitada


def test_inhabilitada_no_se_asigna_ni_se_ofrece_para_corregir(api_y_sesion):
    api, session = api_y_sesion
    sin_otras_celdas_libres(session, "CARRO")
    celda = nueva_celda(session)
    dentro = estancia(session, nueva_celda(session))       # otro carro ya dentro, para la corrección
    assert api.post(f"/celdas/{celda.id}/inhabilitar").status_code == 200
    carro = vehiculo_vigente(session)
    session.commit()
    entrada = api.post("/estancias/entrada", json={"placa": carro.placa})
    assert entrada.status_code == 409 and "No hay celdas disponibles para carros" in entrada.json()["detail"]
    disponibles = {c["codigo"] for c in api.get(f"/estancias/{dentro.id}/celdas-disponibles").json()}
    assert celda.codigo not in disponibles
    correccion = api.post(f"/estancias/{dentro.id}/correccion-celda", json={"celda_id": celda.id, "motivo": "Prueba"})
    assert correccion.status_code == 409 and "inhabilitada" in correccion.json()["detail"]
    # El reporte de ocupación no la cuenta como libre.
    carros = next(c for c in api.get("/reportes/ocupacion").json()["celdas"] if c["tipo"] == "CARRO")
    assert carros["inhabilitadas"] >= 1 and carros["libres"] == carros["total"] - carros["ocupadas"] - carros["inhabilitadas"]


def test_rehabilitar_la_vuelve_disponible_con_tiempo_libre_desde_ahora(api_y_sesion):
    api, session = api_y_sesion
    sin_otras_celdas_libres(session, "MOTO")
    celda = nueva_celda(session, tipo="MOTO")
    assert api.post(f"/celdas/{celda.id}/inhabilitar").status_code == 200
    antes = datetime.now(timezone.utc)
    respuesta = api.post(f"/celdas/{celda.id}/rehabilitar")
    assert respuesta.status_code == 200 and respuesta.json()["estado"] == "LIBRE"
    assert antes <= datetime.fromisoformat(respuesta.json()["disponible_desde"]) <= datetime.now(timezone.utc)
    assert api.post(f"/celdas/{celda.id}/rehabilitar").status_code == 409
    moto = vehiculo_vigente(session, "MOTO")
    session.commit()
    assert api.post("/estancias/entrada", json={"placa": moto.placa}).json()["celda"]["codigo"] == celda.codigo
    acciones = [a["accion"] for a in api.get(f"/celdas/{celda.id}").json()["auditoria"]]
    assert acciones == ["INHABILITAR", "REHABILITAR"]


def test_operador_solo_consulta_y_no_hay_borrado(api_y_sesion):
    """HU-22.3 y RNF-18."""
    api, session = api_y_sesion
    celda = nueva_celda(session)
    autenticar(api, session, rol="OPERADOR")
    assert api.get(f"/celdas/{celda.id}").status_code == 200
    for metodo, url in (("POST", "/celdas"), ("PATCH", f"/celdas/{celda.id}"),
                        ("POST", f"/celdas/{celda.id}/inhabilitar"), ("POST", f"/celdas/{celda.id}/rehabilitar")):
        assert api.request(metodo, url, json={}).status_code == 403
    autenticar(api, session)
    assert api.delete(f"/celdas/{celda.id}").status_code == 405
    assert session.get(Celda, celda.id) is not None


# --- RNF-17: concurrencia con datos confirmados (limpieza por id) ---

@pytest.fixture
def escena_confirmada():
    """Una celda de moto libre, una moto con mensualidad vigente, un operador y un administrador,
    confirmados en la base de pruebas vacía. Al final se borra todo por id."""
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Activa RUN_POSTGRES_TESTS=1 para probar con PostgreSQL.")
    engine = get_engine()
    with Session(engine) as s, s.begin():
        if s.scalar(select(func.count()).select_from(Celda)):
            pytest.skip("Requiere la base de pruebas vacía: docker compose run --rm backend-tests")
        celdas = [Celda(codigo=c, tipo="MOTO") for c in codigos_celda_libres(s, "MOTO", 2)]
        s.add_all(celdas)
        moto = vehiculo_vigente(s, "MOTO")
        operador, admin = crear_cuenta(s, rol="OPERADOR"), crear_cuenta(s, rol="ADMINISTRADOR")
        s.flush()
        d = {"celdas": [c.id for c in celdas], "codigos": [c.codigo for c in celdas], "placa": moto.placa,
             "vehiculo": moto.id, "cliente": moto.cliente_id, "cuentas": [operador.id, admin.id],
             "personas": [operador.operador_id, admin.operador_id],
             "operador": encabezado(operador), "admin": encabezado(admin), "creadas": []}
    try:
        yield d
    finally:
        with Session(engine) as s, s.begin():
            nuevas = list(s.scalars(select(Celda.id).where(Celda.codigo.in_(d["creadas"]))))
            todas = d["celdas"] + nuevas
            s.execute(delete(AuditoriaCelda).where(AuditoriaCelda.celda_id.in_(todas)))
            s.execute(delete(Estancia).where(Estancia.vehiculo_id == d["vehiculo"]))
            s.execute(delete(Mensualidad).where(Mensualidad.vehiculo_id == d["vehiculo"]))
            s.execute(delete(Vehiculo).where(Vehiculo.id == d["vehiculo"]))
            s.execute(delete(Cliente).where(Cliente.id == d["cliente"]))
            s.execute(delete(Celda).where(Celda.id.in_(todas)))
            s.execute(delete(CuentaUsuario).where(CuentaUsuario.id.in_(d["cuentas"])))
            s.execute(delete(Operador).where(Operador.id.in_(d["personas"])))


def bloquear_celda_en_otra_transaccion(celda_id: int):
    """Simula a la otra portería a mitad de una entrada (o a otro administrador a mitad de inhabilitar):
    abre una transacción que bloquea la fila de la celda y la mantiene así."""
    conexion = get_engine().connect()
    transaccion = conexion.begin()
    conexion.execute(text("SELECT id FROM celda WHERE id = :i FOR UPDATE"), {"i": celda_id})
    return conexion, transaccion


def test_inhabilitar_espera_a_la_entrada_en_curso_y_ve_la_celda_ocupada(escena_confirmada):
    d = escena_confirmada
    celda = d["celdas"][0]
    conexion, transaccion = bloquear_celda_en_otra_transaccion(celda)
    # La otra portería registra la entrada en esa celda, sin confirmar todavía.
    persona = d["personas"][0]
    conexion.execute(text("INSERT INTO estancia (vehiculo_id, celda_id, operador_entrada_id) VALUES (:v, :c, :o)"),
                     {"v": d["vehiculo"], "c": celda, "o": persona})
    with ThreadPoolExecutor(max_workers=1) as pool:
        def inhabilitar():
            with TestClient(app, headers=d["admin"]) as cliente:
                return cliente.post(f"/celdas/{celda}/inhabilitar")
        futuro = pool.submit(inhabilitar)
        time.sleep(1.0)
        assert not futuro.done()            # FOR UPDATE: inhabilitar está esperando el bloqueo
        transaccion.commit()                 # la entrada se confirma
        conexion.close()
        respuesta = futuro.result(timeout=15)
    assert respuesta.status_code == 409 and "ocupada" in respuesta.json()["detail"]
    with Session(get_engine()) as s:
        assert s.get(Celda, celda).habilitada


def test_la_entrada_salta_la_celda_que_se_esta_inhabilitando(escena_confirmada):
    d = escena_confirmada
    bloqueada, otra = d["celdas"]
    conexion, transaccion = bloquear_celda_en_otra_transaccion(bloqueada)
    conexion.execute(text("UPDATE celda SET habilitada = false WHERE id = :i"), {"i": bloqueada})
    try:
        inicio = time.monotonic()
        with TestClient(app, headers=d["operador"]) as cliente:
            entrada = cliente.post("/estancias/entrada", json={"placa": d["placa"]})
        # SKIP LOCKED: no espera; toma la otra celda libre.
        assert time.monotonic() - inicio < 5
        assert entrada.status_code == 201 and entrada.json()["celda"]["id"] == otra
    finally:
        transaccion.commit()
        conexion.close()
    with Session(get_engine()) as s:
        assert not s.get(Celda, bloqueada).habilitada
        assert s.scalar(select(func.count()).select_from(Estancia).where(Estancia.celda_id == bloqueada)) == 0


def test_dos_creaciones_simultaneas_del_mismo_codigo_dejan_una_celda(escena_confirmada):
    """HU-23.3 y RNF-17: el índice único decide."""
    d = escena_confirmada
    with Session(get_engine()) as s:
        codigo = codigos_celda_libres(s, "CARRO")[0]
    d["creadas"].append(codigo)
    barrera = Barrier(2, timeout=15)
    local = threading.local()

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO celda") and not getattr(local, "listo", False):
            local.listo = True
            barrera.wait()

    def crear(cuerpo):
        with TestClient(app, headers=d["admin"]) as cliente:
            return cliente.post("/celdas", json=cuerpo)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            respuestas = list(pool.map(crear, [{"codigo": codigo, "tipo": "CARRO"},
                                               {"codigo": f" {codigo.lower()} ", "tipo": "CARRO"}]))
    finally:
        event.remove(engine, "before_cursor_execute", sincronizar)
    assert sorted(r.status_code for r in respuestas) == [201, 409]
    assert next(r.json() for r in respuestas if r.status_code == 409) == {"detail": "Ya existe una celda con ese código."}
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Celda).where(Celda.codigo == codigo)) == 1
