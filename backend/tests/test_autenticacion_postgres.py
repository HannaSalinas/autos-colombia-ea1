"""Inicio de sesión, permisos por rol, cierre de sesión y responsable automático (Iteración 2).

HU-15 Iniciar sesión, HU-16 Ver solo lo que mi rol permite, HU-17 Cerrar sesión,
HU-18 Quedar registrado como responsable; RF-21 (toda operación exige sesión) y RNF-15 (401/403).
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from conftest import CLAVE_PRUEBAS, autenticar, codigos_celda_libres, crear_cuenta, encabezado
from app.domain.permisos import PERMISOS_OPERADOR
from app.main import app
from app.models import Celda, CuentaUsuario
from app.services.seguridad import crear_token

CREDENCIALES_INVALIDAS = {"detail": "Usuario o contraseña inválidos."}


def login(api, usuario: str, contrasena: str = CLAVE_PRUEBAS):
    # Sin el encabezado de la cuenta con la que viene autenticado el fixture.
    return api.post("/auth/login", json={"usuario": usuario, "contrasena": contrasena}, headers={"Authorization": ""})


# --- HU-15 Iniciar sesión ---

def test_login_valido_devuelve_token_rol_y_permisos(api_y_sesion):
    api, session = api_y_sesion
    cuenta = crear_cuenta(session, rol="OPERADOR", usuario="hu15.operador")
    respuesta = login(api, "hu15.operador")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "bearer" and cuerpo["token"].count(".") == 2
    expira = datetime.fromisoformat(cuerpo["expira_en"])
    assert timedelta(hours=7, minutes=59) < expira - datetime.now(timezone.utc) <= timedelta(hours=8)
    assert cuerpo["cuenta"] == {"id": cuenta.id, "nombre_usuario": "hu15.operador",
                                "nombre": cuenta.persona.nombre, "rol": "OPERADOR",
                                "permisos": sorted(PERMISOS_OPERADOR)}
    # La contraseña y su hash nunca aparecen en la respuesta (RNF-13).
    assert "$2b$" not in respuesta.text and CLAVE_PRUEBAS not in respuesta.text
    yo = api.get("/auth/yo", headers={"Authorization": f"Bearer {cuerpo['token']}"})
    assert yo.status_code == 200 and yo.json() == cuerpo["cuenta"]


def test_usuario_se_normaliza_al_ingresar(api_y_sesion):
    api, session = api_y_sesion
    crear_cuenta(session, usuario="marta.prueba")
    assert login(api, "  Marta.Prueba ").status_code == 200


def test_contrasena_incorrecta_y_usuario_inexistente_dan_la_misma_respuesta(api_y_sesion):
    """D5: el mismo 401 y el mismo mensaje; nunca se dice cuál de los dos datos falló."""
    api, session = api_y_sesion
    crear_cuenta(session, usuario="hu15.existe")
    incorrecta = login(api, "hu15.existe", "otra-clave-9")
    inexistente = login(api, "hu15.no.existe", "otra-clave-9")
    for respuesta in (incorrecta, inexistente):
        assert respuesta.status_code == 401
        assert respuesta.json() == CREDENCIALES_INVALIDAS
        assert respuesta.headers["www-authenticate"] == "Bearer"
    # Una contraseña larguísima tampoco produce un error técnico.
    assert login(api, "hu15.existe", "ñ" * 100).json() == CREDENCIALES_INVALIDAS


@pytest.mark.parametrize("cuerpo", [
    {}, {"usuario": "admin"}, {"contrasena": "clave123"}, {"usuario": "", "contrasena": "clave123"},
    {"usuario": "admin", "contrasena": "   "}, {"usuario": None, "contrasena": "clave123"},
    {"usuario": "admin", "contrasena": "clave123", "rol": "ADMINISTRADOR"},   # el rol nunca se elige (D1)
    {"usuario": "a" * 101, "contrasena": "clave123"}, {"usuario": "admin", "contrasena": "a" * 201},
])
def test_login_con_datos_faltantes_o_extra_se_rechaza(api_y_sesion, cuerpo):
    api, _ = api_y_sesion
    respuesta = api.post("/auth/login", json=cuerpo, headers={"Authorization": ""})
    assert respuesta.status_code == 422
    assert "token" not in respuesta.json()


def test_cuenta_desactivada_no_ingresa(api_y_sesion):
    """HU-15.4: con la contraseña correcta se avisa que está desactivada (403); con una incorrecta,
    el mensaje genérico (401), para no confirmar que la cuenta existe."""
    api, session = api_y_sesion
    crear_cuenta(session, usuario="hu15.inactiva", activa=False)
    correcta = login(api, "hu15.inactiva")
    assert correcta.status_code == 403
    assert correcta.json() == {"detail": "Tu cuenta está desactivada. Contacta al administrador."}
    assert login(api, "hu15.inactiva", "otra-clave-9").json() == CREDENCIALES_INVALIDAS


# --- HU-16 Ver solo lo que mi rol permite / RF-21 ---

PUBLICAS = {("POST", "/auth/login"), ("GET", "/health")}
# Lo que solo puede hacer el Administrador (RF-20, D2). Todo lo demás es operativo: ambos roles.
ADMINISTRATIVAS = {
    ("POST", "/vehiculos"), ("PATCH", "/vehiculos/{id}"), ("DELETE", "/vehiculos/{id}"),
    ("POST", "/celdas"), ("PATCH", "/celdas/{id}"), ("DELETE", "/celdas/{id}"),
    ("GET", "/operadores"), ("GET", "/operadores/{id}"),
}


def rutas() -> list[tuple[str, str]]:
    """(método, ruta) de toda la API, tomados del esquema OpenAPI (incluye cualquier ruta nueva)."""
    esquema = app.openapi()["paths"]
    return sorted((metodo.upper(), ruta) for ruta, metodos in esquema.items() for metodo in metodos)


def url_de(ruta: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda m: "ABC123" if m.group() == "{placa}" else "1", ruta)


def test_todas_las_rutas_salvo_login_y_salud_exigen_sesion(api_y_sesion):
    api, _ = api_y_sesion
    revisadas = 0
    for metodo, ruta in rutas():
        if (metodo, ruta) in PUBLICAS:
            continue
        respuesta = api.request(metodo, url_de(ruta), json={}, headers={"Authorization": ""})
        assert respuesta.status_code == 401, (metodo, ruta)
        assert respuesta.headers["www-authenticate"] == "Bearer"
        revisadas += 1
    assert revisadas >= 25


def test_las_rutas_administrativas_existen():
    assert ADMINISTRATIVAS <= set(rutas())


@pytest.mark.parametrize("rol", ["OPERADOR", "ADMINISTRADOR"])
def test_403_exactamente_en_lo_que_el_rol_no_puede_hacer(api_y_sesion, rol):
    """El Operador recibe 403 en las operaciones de administración y en ninguna otra; el
    Administrador no recibe 403 en ninguna (D2: el rol superior contiene al inferior)."""
    api, session = api_y_sesion
    autenticar(api, session, rol=rol)
    for metodo, ruta in rutas():
        if (metodo, ruta) in PUBLICAS or ruta == "/auth/cerrar-sesion":   # cerrar sesión revocaría el token
            continue
        respuesta = api.request(metodo, url_de(ruta), json={})
        prohibida = rol == "OPERADOR" and (metodo, ruta) in ADMINISTRATIVAS
        assert (respuesta.status_code == 403) is prohibida, (rol, metodo, ruta, respuesta.status_code)


def test_operador_que_llama_a_la_api_de_administracion_no_cambia_nada(api_y_sesion):
    """HU-16.3."""
    api, session = api_y_sesion
    autenticar(api, session, rol="OPERADOR")
    antes = session.scalar(select(func.count()).select_from(Celda))
    respuesta = api.post("/celdas", json={"codigo": codigos_celda_libres(session, "CARRO")[0], "tipo": "CARRO"})
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": "No tienes permiso para esta operación."}
    assert session.scalar(select(func.count()).select_from(Celda)) == antes


def test_ambos_roles_hacen_las_operaciones_operativas(api_y_sesion):
    """D2: el Administrador también puede cubrir la portería."""
    api, session = api_y_sesion
    for rol in ("OPERADOR", "ADMINISTRADOR"):
        autenticar(api, session, rol=rol)
        for url in ("/celdas?limit=1", "/vehiculos?limit=1", "/clientes?limit=1", "/reportes/ocupacion",
                    "/reportes/historial?limit=1"):
            assert api.get(url).status_code == 200, (rol, url)


def test_sesion_vencida_manipulada_o_revocada_da_401(api_y_sesion):
    """HU-16.4 y RNF-14: firma, vencimiento, cuenta activa y versión de sesión, en cada solicitud."""
    api, session = api_y_sesion
    cuenta = crear_cuenta(session, rol="OPERADOR")
    valido = encabezado(cuenta)
    assert api.get("/celdas?limit=1", headers=valido).status_code == 200
    vencido, _ = crear_token(cuenta.id, 0, datetime.now(timezone.utc) - timedelta(hours=9))
    for encab in ({"Authorization": f"Bearer {vencido}"}, {"Authorization": valido["Authorization"] + "x"},
                  {"Authorization": "Basic YWRtaW46Y2xhdmU="}, {"Authorization": "Bearer"},
                  {"Authorization": f"Bearer {crear_token(9223372036854775807, 0)[0]}"}):
        respuesta = api.get("/celdas?limit=1", headers=encab)
        assert respuesta.status_code == 401
        assert respuesta.json()["detail"] in {"Tu sesión venció o fue cerrada. Ingresa de nuevo.",
                                              "Debes iniciar sesión para continuar."}
    # Cuenta desactivada: su token deja de valer en la siguiente solicitud (RF-26).
    session.execute(update(CuentaUsuario).where(CuentaUsuario.id == cuenta.id).values(activa=False))
    assert api.get("/celdas?limit=1", headers=valido).status_code == 401
    # Reactivada pero con la versión de sesión ya incrementada: el token viejo sigue sin valer.
    session.execute(update(CuentaUsuario).where(CuentaUsuario.id == cuenta.id)
                    .values(activa=True, version_sesion=CuentaUsuario.version_sesion + 1))
    assert api.get("/celdas?limit=1", headers=valido).status_code == 401
    assert api.get("/celdas?limit=1", headers={"Authorization": f"Bearer {crear_token(cuenta.id, 1)[0]}"}
                   ).status_code == 200


# --- HU-17 Cerrar sesión ---

def test_cerrar_sesion_invalida_el_token(api_y_sesion):
    api, session = api_y_sesion
    crear_cuenta(session, usuario="hu17.cuenta")
    token = login(api, "hu17.cuenta").json()["token"]
    encab = {"Authorization": f"Bearer {token}"}
    assert api.get("/auth/yo", headers=encab).status_code == 200
    assert api.post("/auth/cerrar-sesion", headers=encab).status_code == 204
    assert api.get("/auth/yo", headers=encab).status_code == 401
    assert api.get("/reportes/ocupacion", headers=encab).status_code == 401
    assert api.post("/auth/cerrar-sesion", headers=encab).status_code == 401
    # Puede volver a ingresar.
    nuevo = login(api, "hu17.cuenta").json()["token"]
    assert api.get("/auth/yo", headers={"Authorization": f"Bearer {nuevo}"}).status_code == 200
