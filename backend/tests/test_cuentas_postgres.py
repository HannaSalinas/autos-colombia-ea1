"""Gestión de cuentas de usuario (Iteración 2).

HU-19 Crear cuenta, HU-20 Consultar cuentas, HU-21 Desactivar o reactivar; RF-31 (auditoría) y
RNF-17 (unicidad del usuario ante solicitudes simultáneas).
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from conftest import CLAVE_PRUEBAS, autenticar, crear_cuenta, encabezado
from app.database import get_engine
from app.main import app
from app.models import AuditoriaCuenta, CuentaUsuario, Estancia, Operador
from app.services.seguridad import verificar_contrasena

VALIDA = {"nombre": "Ana Pérez", "nombre_usuario": "ana.perez", "contrasena": "clave123", "rol": "OPERADOR"}


def login(api, usuario: str, contrasena: str = CLAVE_PRUEBAS):
    return api.post("/auth/login", json={"usuario": usuario, "contrasena": contrasena},
                    headers={"Authorization": ""})


# --- HU-19 Crear cuenta de usuario ---

def test_crea_cuenta_activa_sin_mostrar_la_contrasena(api_y_sesion):
    api, session = api_y_sesion
    respuesta = api.post("/cuentas", json={**VALIDA, "nombre": "  Ana Pérez ", "nombre_usuario": " Ana.Perez "})
    assert respuesta.status_code == 201
    cuenta = respuesta.json()
    assert {k: cuenta[k] for k in ("nombre", "nombre_usuario", "rol", "activa")} == {
        "nombre": "Ana Pérez", "nombre_usuario": "ana.perez", "rol": "OPERADOR", "activa": True}
    assert set(cuenta) == {"id", "nombre", "nombre_usuario", "rol", "activa", "creada_en"}
    assert "clave123" not in respuesta.text and "$2b$" not in respuesta.text   # HU-19.4
    guardada = session.get(CuentaUsuario, cuenta["id"])
    assert guardada.hash_contrasena.startswith("$2b$12$")
    assert verificar_contrasena("clave123", guardada.hash_contrasena)
    assert guardada.persona.nombre == "Ana Pérez" and guardada.persona.telefono is None
    # Aparece en el listado y puede ingresar con su rol.
    assert any(c["id"] == cuenta["id"] for c in api.get("/cuentas", params={"buscar": "ana.perez"}).json()["items"])
    session.commit()
    ingreso = login(api, "ana.perez", "clave123")
    assert ingreso.status_code == 200 and ingreso.json()["cuenta"]["rol"] == "OPERADOR"


def test_crear_queda_en_la_auditoria_con_quien_y_cuando(api_y_sesion):
    """RF-31."""
    api, session = api_y_sesion
    admin = autenticar(api, session)
    antes = datetime.now(timezone.utc)
    cuenta = api.post("/cuentas", json={**VALIDA, "rol": "ADMINISTRADOR"}).json()
    detalle = api.get(f"/cuentas/{cuenta['id']}").json()
    assert len(detalle["auditoria"]) == 1
    evento = detalle["auditoria"][0]
    assert evento["accion"] == "CREAR" and evento["detalle"] == "Rol administrador."
    assert evento["actor"] == f"{admin.persona.nombre} ({admin.nombre_usuario})"
    assert antes <= datetime.fromisoformat(evento["fecha"]) <= datetime.now(timezone.utc)


@pytest.mark.parametrize("campo,valor", [
    ("nombre_usuario", "abcd"), ("nombre_usuario", "a" * 30), ("nombre", "Ana"), ("nombre", "n" * 80),
    ("contrasena", "clave123"), ("contrasena", "a1" * 32), ("rol", "ADMINISTRADOR"),
])
def test_valores_validos_en_el_limite(api_y_sesion, campo, valor):
    api, _ = api_y_sesion
    assert api.post("/cuentas", json={**VALIDA, campo: valor}).status_code == 201


@pytest.mark.parametrize("campo,valor", [
    ("nombre_usuario", "abc"), ("nombre_usuario", "a" * 31), ("nombre_usuario", "ana perez"),
    ("nombre_usuario", "ana-perez"), ("nombre_usuario", "   "),
    ("nombre", "Al"), ("nombre", "n" * 81), ("nombre", "    "),
    ("contrasena", "clave12"), ("contrasena", "a1" * 32 + "b"), ("contrasena", "contraseña"),
    ("contrasena", "12345678"), ("contrasena", "ñ" * 40 + "1" * 24),          # 64 caracteres, 104 bytes
    ("rol", "SUPERVISOR"), ("rol", None), ("nombre", None),
])
def test_valores_invalidos_en_el_limite(api_y_sesion, campo, valor):
    api, session = api_y_sesion
    antes = session.scalar(select(func.count()).select_from(CuentaUsuario))
    assert api.post("/cuentas", json={**VALIDA, campo: valor}).status_code == 422
    assert session.scalar(select(func.count()).select_from(CuentaUsuario)) == antes


@pytest.mark.parametrize("extra", [{"activa": False}, {"id": 1}, {"hash_contrasena": "x"}, {"telefono": "300"}])
def test_no_acepta_campos_extra(api_y_sesion, extra):
    api, _ = api_y_sesion
    assert api.post("/cuentas", json={**VALIDA, **extra}).status_code == 422


@pytest.mark.parametrize("repetido", ["ana.perez", "ANA.PEREZ", " Ana.Perez ", "\tana.PEREZ\n"])
def test_usuario_repetido_sin_importar_mayusculas_ni_espacios(api_y_sesion, repetido):
    """HU-19.3: se normaliza antes de validar, así que es el mismo usuario: 409 (no 422)."""
    api, _ = api_y_sesion
    assert api.post("/cuentas", json=VALIDA).status_code == 201
    respuesta = api.post("/cuentas", json={**VALIDA, "nombre": "Otra Persona", "nombre_usuario": repetido})
    assert respuesta.status_code == 409
    assert respuesta.json() == {"detail": "Ese nombre de usuario ya está en uso."}


# --- HU-20 Consultar cuentas ---

def test_listado_busqueda_y_filtros(api_y_sesion):
    api, session = api_y_sesion
    for nombre, usuario, rol in (("Zulma Quintero", "zulma.q", "OPERADOR"), ("Zoe Quiroga", "zoe.adm", "ADMINISTRADOR"),
                                 ("Ximena Zapata", "xime.zz", "OPERADOR")):
        assert api.post("/cuentas", json={**VALIDA, "nombre": nombre, "nombre_usuario": usuario, "rol": rol}
                        ).status_code == 201
    zoe = session.scalar(select(CuentaUsuario.id).where(CuentaUsuario.nombre_usuario == "zoe.adm"))
    session.execute(CuentaUsuario.__table__.update().where(CuentaUsuario.id == zoe).values(activa=False))

    def usuarios(**params):
        respuesta = api.get("/cuentas", params={"limit": 100, **params})
        assert respuesta.status_code == 200
        return {c["nombre_usuario"] for c in respuesta.json()["items"]}

    assert {"zulma.q", "zoe.adm", "xime.zz"} <= usuarios()
    assert usuarios(buscar="QUI") >= {"zulma.q", "zoe.adm"} and "xime.zz" not in usuarios(buscar="QUI")
    assert usuarios(buscar="xime.z") == {"xime.zz"}                      # por usuario
    assert "zoe.adm" in usuarios(buscar="zo", rol="ADMINISTRADOR", estado="INACTIVA")
    assert "zulma.q" not in usuarios(rol="ADMINISTRADOR")
    assert "zoe.adm" not in usuarios(estado="ACTIVA")
    # % y _ se buscan como texto, no como comodines.
    assert usuarios(buscar="%") == set() and "xime.zz" not in usuarios(buscar="e_z")
    vacio = api.get("/cuentas", params={"buscar": "no-existe-nadie"}).json()
    assert vacio["items"] == [] and vacio["total"] == 0
    fila = next(c for c in api.get("/cuentas", params={"buscar": "zulma"}).json()["items"])
    assert set(fila) == {"id", "nombre", "nombre_usuario", "rol", "activa", "creada_en"}   # HU-20.1
    for malo in ({"rol": "OTRO"}, {"estado": "BORRADA"}, {"limit": 0}, {"buscar": "x" * 81}):
        assert api.get("/cuentas", params=malo).status_code == 422


def test_detalle_de_cuenta_inexistente(api_y_sesion):
    api, _ = api_y_sesion
    assert api.get("/cuentas/9223372036854775807").status_code == 404
    assert api.post("/cuentas/9223372036854775807/desactivar").status_code == 404


# --- HU-21 Desactivar o reactivar ---

def test_desactivar_impide_ingresar_y_revoca_la_sesion_abierta(api_y_sesion):
    api, session = api_y_sesion
    otra = crear_cuenta(session, rol="OPERADOR", usuario="hu21.operador")
    sesion_abierta = encabezado(otra)
    assert api.get("/reportes/ocupacion", headers=sesion_abierta).status_code == 200
    respuesta = api.post(f"/cuentas/{otra.id}/desactivar")
    assert respuesta.status_code == 200 and respuesta.json()["activa"] is False
    # HU-21.2: la sesión abierta deja de valer en la siguiente solicitud, y no puede ingresar.
    assert api.get("/reportes/ocupacion", headers=sesion_abierta).status_code == 401
    assert login(api, "hu21.operador").status_code == 403
    assert api.post(f"/cuentas/{otra.id}/desactivar").status_code == 409
    # HU-21.4: reactivada vuelve a ingresar, pero el token viejo sigue sin valer.
    reactivada = api.post(f"/cuentas/{otra.id}/reactivar")
    assert reactivada.status_code == 200 and reactivada.json()["activa"] is True
    assert login(api, "hu21.operador").status_code == 200
    assert api.get("/reportes/ocupacion", headers=sesion_abierta).status_code == 401
    assert api.post(f"/cuentas/{otra.id}/reactivar").status_code == 409
    acciones = [e["accion"] for e in api.get(f"/cuentas/{otra.id}").json()["auditoria"]]
    assert acciones == ["DESACTIVAR", "REACTIVAR"]       # creada en la prueba, sin auditoría de creación


def test_no_puede_desactivar_su_propia_cuenta(api_y_sesion):
    api, session = api_y_sesion
    yo = autenticar(api, session)
    respuesta = api.post(f"/cuentas/{yo.id}/desactivar")
    assert respuesta.status_code == 409 and respuesta.json() == {"detail": "No puedes desactivar tu propia cuenta."}
    assert session.get(CuentaUsuario, yo.id).activa


def test_con_dos_administradores_se_desactiva_al_otro_y_el_que_queda_no_puede(api_y_sesion):
    """HU-21.3 (valores límite): con 2 administradores activos se puede desactivar al otro; el que
    queda es el último y no puede desactivarse. El caso de dos administradores que se desactivan
    al mismo tiempo está en test_dos_administradores_que_se_desactivan_mutuamente_no_dejan_cero."""
    api, session = api_y_sesion
    session.execute(CuentaUsuario.__table__.update().where(CuentaUsuario.rol == "ADMINISTRADOR")
                    .values(activa=False))
    a = autenticar(api, session)
    b = crear_cuenta(session, rol="ADMINISTRADOR")
    assert api.post(f"/cuentas/{b.id}/desactivar").status_code == 200
    assert session.scalar(select(func.count()).select_from(CuentaUsuario).where(
        CuentaUsuario.rol == "ADMINISTRADOR", CuentaUsuario.activa.is_(True))) == 1
    # El Operador no puede intentarlo (403) y el último administrador no puede consigo mismo (409).
    autenticar(api, session, rol="OPERADOR")
    assert api.post(f"/cuentas/{a.id}/desactivar").status_code == 403
    api.headers.update(encabezado(a))
    respuesta = api.post(f"/cuentas/{a.id}/desactivar")
    assert respuesta.status_code == 409 and respuesta.json()["detail"] == "No puedes desactivar tu propia cuenta."
    assert session.get(CuentaUsuario, a.id).activa


def test_desactivada_conserva_a_su_nombre_los_movimientos(api_y_sesion):
    """HU-21.5: el historial sigue mostrando al responsable."""
    api, session = api_y_sesion
    cuenta = crear_cuenta(session, rol="OPERADOR")
    nombre = cuenta.persona.nombre
    estancias = session.scalar(select(func.count()).select_from(Estancia)
                               .where(Estancia.operador_entrada_id == cuenta.operador_id))
    assert api.post(f"/cuentas/{cuenta.id}/desactivar").status_code == 200
    session.commit()
    assert session.get(Operador, cuenta.operador_id).nombre == nombre       # la persona sigue igual
    assert session.scalar(select(func.count()).select_from(Estancia)
                          .where(Estancia.operador_entrada_id == cuenta.operador_id)) == estancias
    assert api.get(f"/cuentas/{cuenta.id}").json()["nombre"] == nombre


# --- RNF-17: concurrencia (datos confirmados, limpieza por id) ---

con_postgres = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


def en_paralelo(solicitudes, marca):
    """Envía dos solicitudes a la vez; ambas esperan juntas justo antes de la sentencia marcada."""
    barrera = Barrier(2, timeout=15)
    local = threading.local()

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        if marca(statement) and not getattr(local, "listo", False):
            local.listo = True
            barrera.wait()

    def enviar(item):
        metodo, url, cuerpo, encab = item
        with TestClient(app, headers=encab) as cliente:
            return cliente.request(metodo, url, json=cuerpo)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(enviar, solicitudes))
    finally:
        event.remove(engine, "before_cursor_execute", sincronizar)


@pytest.fixture
def admins_confirmados():
    """Dos administradores confirmados en la base (se borran por id al terminar)."""
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Activa RUN_POSTGRES_TESTS=1 para probar con PostgreSQL.")
    engine = get_engine()
    with Session(engine) as s, s.begin():
        if s.scalar(select(func.count()).select_from(CuentaUsuario).where(
                CuentaUsuario.rol == "ADMINISTRADOR", CuentaUsuario.activa.is_(True))):
            pytest.skip("Requiere la base de pruebas sin administradores (docker compose run --rm backend-tests).")
        cuentas = [crear_cuenta(s, rol="ADMINISTRADOR") for _ in range(2)]
        datos = {"ids": [c.id for c in cuentas], "personas": [c.operador_id for c in cuentas],
                 "auth": [encabezado(c) for c in cuentas]}
    creados: list[str] = []
    datos["creados"] = creados
    try:
        yield datos
    finally:
        with Session(engine) as s, s.begin():
            nuevas = list(s.scalars(select(CuentaUsuario).where(CuentaUsuario.nombre_usuario.in_(creados))))
            ids = datos["ids"] + [c.id for c in nuevas]
            personas = datos["personas"] + [c.operador_id for c in nuevas]
            s.execute(delete(AuditoriaCuenta).where(AuditoriaCuenta.cuenta_id.in_(ids)))
            s.execute(delete(AuditoriaCuenta).where(AuditoriaCuenta.actor_cuenta_id.in_(ids)))
            s.execute(delete(CuentaUsuario).where(CuentaUsuario.id.in_(ids)))
            s.execute(delete(Operador).where(Operador.id.in_(personas)))


@con_postgres
def test_dos_creaciones_simultaneas_del_mismo_usuario_dejan_una_cuenta(admins_confirmados):
    """HU-19.3 y RNF-17: las dos pasan la revisión previa a la vez; el índice único decide."""
    d = admins_confirmados
    d["creados"].append("pedro.simultaneo")
    cuerpos = [{**VALIDA, "nombre": "Pedro Uno", "nombre_usuario": "pedro.simultaneo"},
               {**VALIDA, "nombre": "Pedro Dos", "nombre_usuario": "PEDRO.Simultaneo"}]
    respuestas = en_paralelo([("POST", "/cuentas", cuerpos[0], d["auth"][0]),
                              ("POST", "/cuentas", cuerpos[1], d["auth"][1])],
                             lambda st: st.startswith("INSERT INTO operador"))
    assert sorted(r.status_code for r in respuestas) == [201, 409]
    assert next(r.json() for r in respuestas if r.status_code == 409) == {"detail": "Ese nombre de usuario ya está en uso."}
    with Session(get_engine()) as s:
        assert s.scalar(select(func.count()).select_from(CuentaUsuario).where(
            func.lower(CuentaUsuario.nombre_usuario) == "pedro.simultaneo")) == 1
        # La persona de la solicitud rechazada tampoco quedó (todo o nada).
        assert s.scalar(select(func.count()).select_from(Operador).where(
            Operador.nombre.in_(["Pedro Uno", "Pedro Dos"]))) == 1


@con_postgres
def test_dos_administradores_que_se_desactivan_mutuamente_no_dejan_cero(admins_confirmados):
    """HU-21.3 bajo concurrencia: A desactiva a B y B desactiva a A en el mismo instante."""
    d = admins_confirmados
    a, b = d["ids"]
    respuestas = en_paralelo([("POST", f"/cuentas/{b}/desactivar", None, d["auth"][0]),
                              ("POST", f"/cuentas/{a}/desactivar", None, d["auth"][1])],
                             lambda st: "FROM cuenta_usuario" in st and "FOR UPDATE" in st)
    # El primero gana; el segundo espera el bloqueo y, al continuar, ve que solo queda un
    # administrador activo. Nunca responden los dos 200.
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    assert next(r.json() for r in respuestas if r.status_code == 409) == {
        "detail": "No se puede desactivar al último administrador activo."}
    with Session(get_engine()) as s:
        assert s.scalar(select(func.count()).select_from(CuentaUsuario).where(
            CuentaUsuario.id.in_([a, b]), CuentaUsuario.activa.is_(True))) == 1
