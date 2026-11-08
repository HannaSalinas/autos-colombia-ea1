"""Hash bcrypt, token firmado, mapa de permisos y configuración de la Iteración 2 (sin base de datos)."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from conftest import CLAVE_PRUEBAS, hash_pruebas
from app.config import ConfigurationError, load_auth_settings, load_seed_credentials
from app.domain import permisos
from app.services.seguridad import (
    DURACION_SESION, TokenInvalido, crear_token, hash_de_relleno, leer_token, secreto, verificar_contrasena,
)


# --- bcrypt (RNF-13) ---

def test_hash_bcrypt_de_costo_12_con_sal():
    h = hash_pruebas()
    assert h.startswith("$2b$12$") and len(h) == 60
    assert CLAVE_PRUEBAS not in h
    assert verificar_contrasena(CLAVE_PRUEBAS, h)


@pytest.mark.parametrize("intento", ["clave-de-prueba-2", "CLAVE-DE-PRUEBA-1", "", "clave-de-prueba-1 "])
def test_contrasena_distinta_no_coincide(intento):
    assert not verificar_contrasena(intento, hash_pruebas())


def test_mas_de_72_bytes_o_hash_danado_no_es_error():
    assert not verificar_contrasena("ñ" * 40, hash_pruebas())        # 80 bytes: bcrypt lo rechazaría
    assert not verificar_contrasena(CLAVE_PRUEBAS, "no-es-un-hash")


def test_hash_de_relleno_no_coincide_con_nada_comun():
    assert hash_de_relleno().startswith("$2b$12$")
    assert not verificar_contrasena("", hash_de_relleno())


# --- Token de sesión (RNF-14) ---

def test_token_lleva_cuenta_version_y_vence_en_8_horas():
    ahora = datetime.now(timezone.utc)
    token, expira = crear_token(7, 3, ahora)
    assert expira - ahora == DURACION_SESION == timedelta(hours=8)
    datos = leer_token(token)
    assert (datos.cuenta_id, datos.version) == (7, 3)
    contenido = jwt.decode(token, options={"verify_signature": False})
    assert set(contenido) == {"sub", "ver", "iat", "exp"}            # el rol NO va en el token


def test_token_vencido():
    token, _ = crear_token(7, 0, datetime.now(timezone.utc) - timedelta(hours=8, seconds=1))
    with pytest.raises(TokenInvalido):
        leer_token(token)


def test_token_a_punto_de_vencer_aun_vale():
    token, _ = crear_token(7, 0, datetime.now(timezone.utc) - timedelta(hours=7, minutes=59))
    assert leer_token(token).cuenta_id == 7


def falsificado(datos: dict, clave: str | None = None, algoritmo: str = "HS256") -> str:
    ahora = datetime.now(timezone.utc)
    completo = {"sub": "7", "ver": 0, "iat": ahora, "exp": ahora + timedelta(hours=1), **datos}
    completo = {k: v for k, v in completo.items() if v is not None}
    return jwt.encode(completo, clave if clave is not None else secreto(), algorithm=algoritmo)


@pytest.mark.parametrize("token", [
    "", "abc", "a.b.c",
    falsificado({}, clave="otra-clave-que-no-es-la-del-sistema-123456"),   # firma con otra clave
    falsificado({"sub": None}), falsificado({"ver": None}), falsificado({"exp": None}), falsificado({"iat": None}),
    falsificado({"sub": "abc"}), falsificado({"sub": "0"}), falsificado({"sub": "9223372036854775808"}),
    falsificado({"ver": "0"}), falsificado({"ver": -1}), falsificado({"ver": True}),
])
def test_tokens_invalidos(token):
    with pytest.raises(TokenInvalido):
        leer_token(token)


def test_token_sin_firma_alg_none_se_rechaza():
    ahora = datetime.now(timezone.utc)
    sin_firma = jwt.encode({"sub": "7", "ver": 0, "iat": ahora, "exp": ahora + timedelta(hours=1)}, None,
                           algorithm="none")
    with pytest.raises(TokenInvalido):
        leer_token(sin_firma)


def test_token_modificado_se_rechaza():
    token, _ = crear_token(7, 0)
    cabecera, cuerpo, firma = token.split(".")
    otro, _ = crear_token(1, 0)
    with pytest.raises(TokenInvalido):
        leer_token(".".join([cabecera, otro.split(".")[1], firma]))   # cuerpo de otra cuenta, firma vieja


# --- Mapa de permisos (D2) ---

def test_administrador_contiene_al_operador():
    assert permisos.PERMISOS_OPERADOR < permisos.PERMISOS_ADMINISTRADOR


def test_operador_solo_operativas():
    assert permisos.permisos_de("OPERADOR") == {"estancias", "consultas", "celdas:ver", "vehiculos:ver"}
    for permiso in ("celdas:gestionar", "vehiculos:gestionar", "cuentas:gestionar"):
        assert not permisos.tiene_permiso("OPERADOR", permiso)
        assert permisos.tiene_permiso("ADMINISTRADOR", permiso)


@pytest.mark.parametrize("rol", ["", "administrador", "SUPERVISOR", None])
def test_rol_desconocido_no_tiene_permisos(rol):
    assert permisos.permisos_de(rol) == frozenset()
    assert not permisos.tiene_permiso(rol, "estancias")


# --- Configuración: los errores nombran la variable, nunca el valor ---

@pytest.fixture
def entorno(monkeypatch, tmp_path):
    """Sin backend/.env real: solo cuentan las variables que ponga cada prueba."""
    monkeypatch.setattr("app.config.ENV_FILE", tmp_path / "no-existe.env")
    for clave in ("JWT_SECRETO", "ADMIN_USUARIO", "ADMIN_NOMBRE", "ADMIN_CONTRASENA", "MARTA_CONTRASENA",
                  "DIEGO_CONTRASENA"):
        monkeypatch.delenv(clave, raising=False)
    return monkeypatch


@pytest.mark.parametrize("valor,mensaje", [(None, "Completa en .env: JWT_SECRETO"), ("   ", "JWT_SECRETO"),
                                           ("CAMBIAR_CLAVE_DE_FIRMA_DE_32_O_MAS_CARACTERES", "JWT_SECRETO"),
                                           ("corta-de-31-caracteres-xxxxxxxx", "al menos 32")])
def test_secreto_ausente_o_corto(entorno, valor, mensaje):
    if valor is not None:
        entorno.setenv("JWT_SECRETO", valor)
    with pytest.raises(ConfigurationError, match=mensaje) as error:
        load_auth_settings()
    if valor and valor.strip():
        assert valor not in str(error.value)


def test_secreto_de_32_caracteres_vale(entorno):
    entorno.setenv("JWT_SECRETO", "x" * 32)
    assert load_auth_settings().jwt_secreto == "x" * 32
    assert "x" * 32 not in repr(load_auth_settings())


CREDENCIALES = {"ADMIN_USUARIO": " Admin ", "ADMIN_NOMBRE": " Ana Admin ", "ADMIN_CONTRASENA": "clave123",
                "MARTA_CONTRASENA": "marta123", "DIEGO_CONTRASENA": "diego123"}


def test_credenciales_semilla_validas_y_normalizadas(entorno):
    for clave, valor in CREDENCIALES.items():
        entorno.setenv(clave, valor)
    credenciales = load_seed_credentials()
    assert credenciales.admin_usuario == "admin" and credenciales.admin_nombre == "Ana Admin"
    assert "clave123" not in repr(credenciales) and "marta123" not in repr(credenciales)


@pytest.mark.parametrize("clave,valor,mensaje", [
    ("ADMIN_CONTRASENA", None, "Completa en .env: ADMIN_CONTRASENA"),
    ("MARTA_CONTRASENA", "corta1", "MARTA_CONTRASENA no es válida"),
    ("DIEGO_CONTRASENA", "sinnumeros", "DIEGO_CONTRASENA no es válida"),
    ("ADMIN_USUARIO", "abc", "ADMIN_USUARIO no es válida"),
    ("ADMIN_NOMBRE", "Al", "ADMIN_NOMBRE no es válida"),
    ("ADMIN_USUARIO", "marta.usuga", "no puede ser el usuario de Marta"),
])
def test_credenciales_semilla_invalidas(entorno, clave, valor, mensaje):
    for k, v in CREDENCIALES.items():
        entorno.setenv(k, v)
    if valor is None:
        entorno.delenv(clave)
    else:
        entorno.setenv(clave, valor)
    with pytest.raises(ConfigurationError, match=mensaje) as error:
        load_seed_credentials()
    if valor and clave.endswith("CONTRASENA"):
        assert valor not in str(error.value)
