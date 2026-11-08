"""Valores límite de las reglas de cuentas y celdas de la Iteración 2 (sin base de datos).

Corresponden a la tabla "Reglas y valores límite" del documento de requerimientos.
"""

import pytest

from app.domain.reglas import (
    normalizar_codigo_celda, normalizar_ubicacion, normalizar_usuario, validar_codigo_celda,
    validar_contrasena, validar_nombre_completo, validar_nombre_usuario,
)


# --- Nombre de usuario: 4 a 30, minúsculas, dígitos, punto y guion bajo ---

@pytest.mark.parametrize("usuario", ["abcd", "marta", "a" * 30, "marta.usuga", "diego_2", "1234"])
def test_usuario_valido_en_el_limite(usuario):
    assert validar_nombre_usuario(usuario) == usuario


@pytest.mark.parametrize("usuario", ["abc", "a" * 31, "", "    ", "marta usuga", "marta-usuga", "martá", "ma@ta"])
def test_usuario_invalido_en_el_limite(usuario):
    with pytest.raises(ValueError, match="nombre de usuario"):
        validar_nombre_usuario(usuario)


@pytest.mark.parametrize("entrada,esperado", [
    (" Marta.Usuga ", "marta.usuga"), ("MARTA", "marta"), ("\tdiego_2\n", "diego_2"),
])
def test_usuario_se_normaliza_antes_de_validar(entrada, esperado):
    # 'Marta' no es un formato inválido: es el mismo usuario que 'marta' (la unicidad lo rechaza).
    assert normalizar_usuario(entrada) == esperado
    assert validar_nombre_usuario(entrada) == esperado


def test_espacios_exteriores_no_cuentan_para_la_longitud():
    assert validar_nombre_usuario("  abcd  ") == "abcd"
    with pytest.raises(ValueError):
        validar_nombre_usuario("  abc  ")


# --- Nombre completo: 3 a 80, se recortan los espacios exteriores ---

@pytest.mark.parametrize("nombre", ["Ana", "a" * 80, "Marta Úsuga"])
def test_nombre_valido_en_el_limite(nombre):
    assert validar_nombre_completo(nombre) == nombre


def test_nombre_recorta_espacios():
    assert validar_nombre_completo("   Ana  ") == "Ana"


@pytest.mark.parametrize("nombre", ["Al", "a" * 81, "", "     ", "  Al  "])
def test_nombre_invalido_en_el_limite(nombre):
    with pytest.raises(ValueError, match="nombre completo"):
        validar_nombre_completo(nombre)


# --- Contraseña: 8 a 64, al menos una letra y un número, máximo 72 bytes ---

@pytest.mark.parametrize("clave", ["clave123", "a1" * 32, "contraseña1", "1234567a", "con espacio 9"])
def test_contrasena_valida_en_el_limite(clave):
    assert validar_contrasena(clave) == clave


@pytest.mark.parametrize("clave,mensaje", [
    ("clave12", "de 8 a 64"), ("a1" * 32 + "x", "de 8 a 64"), ("", "de 8 a 64"),
    ("contraseña", "letra y un número"), ("12345678", "letra y un número"), ("________", "letra y un número"),
])
def test_contrasena_invalida_en_el_limite(clave, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        validar_contrasena(clave)


def test_contrasena_de_64_caracteres_pero_mas_de_72_bytes():
    clave = "ñ" * 40 + "1" * 24      # 64 caracteres, 104 bytes en UTF-8
    assert len(clave) == 64
    with pytest.raises(ValueError, match="demasiado larga"):
        validar_contrasena(clave)


def test_contrasena_no_se_recorta():
    assert validar_contrasena(" clave123 ") == " clave123 "


# --- Código de celda: C o M + 01..99, prefijo según el tipo ---

@pytest.mark.parametrize("codigo,tipo", [("C01", "CARRO"), ("C99", "CARRO"), ("M01", "MOTO"), ("M99", "MOTO"),
                                         ("C10", "CARRO")])
def test_codigo_valido_en_el_limite(codigo, tipo):
    assert validar_codigo_celda(codigo, tipo) == codigo


@pytest.mark.parametrize("entrada,tipo,esperado", [(" c05 ", "CARRO", "C05"), ("m10", "MOTO", "M10"),
                                                   ("\tC70\n", "CARRO", "C70")])
def test_codigo_se_normaliza_antes_de_validar(entrada, tipo, esperado):
    assert normalizar_codigo_celda(entrada) == esperado
    assert validar_codigo_celda(entrada, tipo) == esperado


@pytest.mark.parametrize("codigo", ["C00", "C100", "C1", "C001", "X05", "", "C-05", "C 05", "CC5", "M00"])
def test_codigo_invalido_en_el_limite(codigo):
    with pytest.raises(ValueError, match="dos dígitos del 01 al 99"):
        validar_codigo_celda(codigo, "CARRO" if codigo.startswith("C") else "MOTO")


@pytest.mark.parametrize("codigo,tipo", [("M05", "CARRO"), ("C05", "MOTO")])
def test_codigo_con_prefijo_de_otro_tipo(codigo, tipo):
    with pytest.raises(ValueError, match=f"tipo {tipo} debe tener un código que empiece por"):
        validar_codigo_celda(codigo, tipo)


def test_codigo_con_tipo_desconocido():
    with pytest.raises(ValueError, match="CARRO o MOTO"):
        validar_codigo_celda("C05", "CAMION")


# --- Ubicación: opcional, máximo 60 ---

@pytest.mark.parametrize("entrada,esperada", [(None, None), ("", None), ("   ", None),
                                              ("a" * 60, "a" * 60), ("  Sótano 1 ", "Sótano 1")])
def test_ubicacion_valida_en_el_limite(entrada, esperada):
    assert normalizar_ubicacion(entrada) == esperada


def test_ubicacion_invalida_en_el_limite():
    with pytest.raises(ValueError, match="máximo 60"):
        normalizar_ubicacion("a" * 61)
