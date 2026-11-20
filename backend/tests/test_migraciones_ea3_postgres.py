"""Migraciones 0009 (clientes y tarifas) y 0010 (pagos): restricciones de la base, triggers de
inmutabilidad y aplicación sobre datos de las iteraciones 1 y 2. Iteración 3.

Las pruebas de restricciones trabajan dentro de una transacción que se revierte. La prueba de
"datos anteriores" baja la base de pruebas a la 0008, inserta datos con la forma de la EA1 y la EA2,
vuelve a subir a la última migración y limpia; al final la base siempre queda en la última revisión.
"""

import os
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from conftest import ALEMBIC_HEAD
from app.database import get_engine

ALEMBIC_INI = str(Path(__file__).resolve().parents[1] / "alembic.ini")
HASH_12 = "$2b$12$" + "a" * 53

con_postgres = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


# --- SQL offline: no necesita base de datos ---

def sql_offline(rango: str) -> str:
    output = StringIO()
    command.upgrade(Config(ALEMBIC_INI, output_buffer=output), rango, sql=True)
    return output.getvalue()


def test_sql_offline_de_0009():
    sql = sql_offline("0008:0009")
    # Los clientes existentes quedan con CC y después el DEFAULT se quita (D15).
    assert "ALTER TABLE cliente ADD COLUMN tipo_documento TEXT DEFAULT 'CC' NOT NULL" in sql
    assert "ALTER TABLE cliente ALTER COLUMN tipo_documento DROP DEFAULT" in sql
    assert "CHECK (tipo_documento IN ('CC', 'CE', 'PA'))" in sql
    assert "CHECK (documento ~ '^[A-Z0-9]{5,15}$') NOT VALID" in sql
    assert "CHECK (telefono ~ '^[0-9]{10}$') NOT VALID" in sql
    assert "char_length(nombre) BETWEEN 3 AND 80" in sql
    assert "ALTER TABLE cliente DROP CONSTRAINT uq_cliente_documento" in sql
    assert "CREATE UNIQUE INDEX uq_cliente_tipo_documento ON cliente (tipo_documento, upper(documento))" in sql
    assert "CREATE TABLE tarifa" in sql and "CHECK (valor BETWEEN 1000 AND 2000000)" in sql
    assert "BEFORE UPDATE OR DELETE ON tarifa" in sql and "BEFORE TRUNCATE ON tarifa" in sql
    # Lo único que se quita: el DEFAULT temporal y el único por número (lo reemplaza el de tipo y número).
    assert sql.count("DROP") == 2


# --- Restricciones en PostgreSQL (transacción revertida) ---

@pytest.fixture
def conexion():
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Activa RUN_POSTGRES_TESTS=1 para probar con PostgreSQL.")
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
            yield connection
        finally:
            transaction.rollback()


def falla(conexion, sql: str, params: dict, estado: str, restriccion: str | None = None,
          mensaje: str | None = None) -> None:
    with pytest.raises(IntegrityError) as error:
        with conexion.begin_nested():
            conexion.execute(text(sql), params)
    assert error.value.orig.sqlstate == estado
    if restriccion:
        assert error.value.orig.diag.constraint_name == restriccion
    if mensaje:
        assert mensaje in str(error.value.orig)


CLIENTE = ("INSERT INTO cliente (tipo_documento, documento, nombre, telefono, correo) "
           "VALUES (:t, :d, :n, :f, :c) RETURNING id")


def cliente(conexion, **cambios) -> int:
    datos = {"t": "CC", "d": "1099888777", "n": "Cliente EA3", "f": "3001234567", "c": None, **cambios}
    return conexion.scalar(text(CLIENTE), datos)


def cuenta(conexion, usuario: str = "cuenta.ea3") -> int:
    persona = conexion.scalar(text("INSERT INTO operador (nombre) VALUES ('Persona EA3') RETURNING id"))
    return conexion.scalar(text("INSERT INTO cuenta_usuario (operador_id, nombre_usuario, hash_contrasena, rol) "
                                "VALUES (:o, :u, :h, 'ADMINISTRADOR') RETURNING id"),
                           {"o": persona, "u": usuario, "h": HASH_12})


def test_cliente_columnas_nuevas(conexion):
    columnas = {c["name"]: c for c in inspect(conexion).get_columns("cliente")}
    assert {"tipo_documento", "registrado_en", "registrado_por_cuenta_id"} <= set(columnas)
    assert not columnas["tipo_documento"]["nullable"] and columnas["tipo_documento"]["default"] is None
    # Sin DEFAULT en la base: un INSERT directo sin tipo de documento falla.
    falla(conexion, "INSERT INTO cliente (documento, nombre, telefono) VALUES ('1099888777', 'Ana', '3001234567')",
          {}, "23502")


def test_cliente_reglas_de_la_tabla_en_sus_limites(conexion):
    # Válidos en el límite: documento de 5 y 15, nombre de 3 y 80, teléfono de 10 dígitos, correo vacío.
    assert cliente(conexion, d="12345", n="Ana") and cliente(conexion, d="A" * 15, n="a" * 80, t="PA")
    assert cliente(conexion, d="CE12345", t="CE", c="ana@correo.com")
    for documento in ("1234", "1" * 16, "1.234.567", "abc12345", " 12345"):
        falla(conexion, CLIENTE, {"t": "CC", "d": documento, "n": "Ana", "f": "3001234567", "c": None}, "23514",
              "ck_cliente_documento_formato")
    for nombre in ("Al", "a" * 81, " Ana", "Ana "):
        falla(conexion, CLIENTE, {"t": "CC", "d": "55555", "n": nombre, "f": "3001234567", "c": None}, "23514",
              "ck_cliente_nombre_longitud")
    for telefono in ("300123456", "30012345678", "300123456a"):
        falla(conexion, CLIENTE, {"t": "CC", "d": "55555", "n": "Ana", "f": telefono, "c": None}, "23514",
              "ck_cliente_telefono_formato")
    for tipo in ("TI", "cc", "NIT"):
        falla(conexion, CLIENTE, {"t": tipo, "d": "55555", "n": "Ana", "f": "3001234567", "c": None}, "23514",
              "ck_cliente_tipo_documento")
    falla(conexion, CLIENTE, {"t": "CC", "d": "55555", "n": "Ana", "f": "3001234567", "c": "ana@"}, "23514",
          "ck_cliente_correo_formato")


def test_documento_unico_por_tipo_y_numero_sin_distinguir_mayusculas(conexion):
    cliente(conexion, t="PA", d="AB12345")
    falla(conexion, CLIENTE, {"t": "PA", "d": "AB12345", "n": "Otra", "f": "3001234567", "c": None}, "23505",
          "uq_cliente_tipo_documento")
    # Mismo número con otro tipo: es otro documento (RF-34: único por tipo y número).
    assert cliente(conexion, t="CE", d="AB12345")
    definicion = conexion.scalar(text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_cliente_tipo_documento'"))
    assert "UNIQUE" in definicion and "upper(documento)" in definicion
    assert conexion.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname = 'uq_cliente_documento'")) == 0


def test_cliente_registrado_por_y_cuando(conexion):
    admin = cuenta(conexion)
    falla(conexion, "INSERT INTO cliente (tipo_documento, documento, nombre, telefono, registrado_por_cuenta_id) "
                    "VALUES ('CC', '77777', 'Ana', '3001234567', :a)", {"a": admin}, "23514", "ck_cliente_registro")
    conexion.execute(text("INSERT INTO cliente (tipo_documento, documento, nombre, telefono, registrado_en, "
                          "registrado_por_cuenta_id) VALUES ('CC', '77777', 'Ana', '3001234567', now(), :a)"),
                     {"a": admin})
    falla(conexion, "DELETE FROM cuenta_usuario WHERE id = :a", {"a": admin}, "23503")


def test_checks_de_cliente_no_revisan_clientes_antiguos(conexion):
    # NOT VALID: los clientes de las iteraciones 1 y 2 no se revisan; los nuevos y los modificados, sí.
    estado = dict(conexion.execute(text(
        "SELECT conname, convalidated FROM pg_constraint WHERE conname LIKE 'ck_cliente_%'"
    )).all())
    assert estado["ck_cliente_documento_formato"] is False and estado["ck_cliente_nombre_longitud"] is False
    assert estado["ck_cliente_telefono_formato"] is False
    # Las columnas nuevas nacieron con datos que cumplen: esos CHECK se validan completos.
    assert estado["ck_cliente_tipo_documento"] is True and estado["ck_cliente_registro"] is True


TARIFA = "INSERT INTO tarifa (tipo_vehiculo, valor) VALUES (:t, :v) RETURNING id"


def test_tarifa_reglas_en_sus_limites(conexion):
    assert conexion.scalar(text(TARIFA), {"t": "MOTO", "v": 1000})
    assert conexion.scalar(text(TARIFA), {"t": "CAMIONETA", "v": 2000000})
    for valor in (999, 2000001):
        falla(conexion, TARIFA, {"t": "AUTOMOVIL", "v": valor}, "23514", "ck_tarifa_valor")
    for tipo in ("CARRO", "CAMION", "moto"):
        falla(conexion, TARIFA, {"t": tipo, "v": 50000}, "23514", "ck_tarifa_tipo_vehiculo")
    columnas = {c["name"]: c for c in inspect(conexion).get_columns("tarifa")}
    # Tipo numérico exacto (RNF-22): nunca punto flotante.
    assert str(columnas["valor"]["type"]) == "INTEGER"
    fila = conexion.execute(text("INSERT INTO tarifa (tipo_vehiculo, valor) VALUES ('AUTOMOVIL', 120000) "
                                 "RETURNING vigente_desde, definida_por_cuenta_id")).one()
    assert fila.vigente_desde is not None and fila.definida_por_cuenta_id is None   # NULL = semillas


def test_tarifa_no_se_edita_ni_se_borra_aunque_se_intente_en_la_base(conexion):
    tarifa = conexion.scalar(text(TARIFA), {"t": "AUTOMOVIL", "v": 120000})
    mensaje = "Las tarifas no se editan ni se eliminan"
    falla(conexion, "UPDATE tarifa SET valor = 130000 WHERE id = :i", {"i": tarifa}, "23001", mensaje=mensaje)
    falla(conexion, "UPDATE tarifa SET vigente_desde = now() - interval '1 day' WHERE id = :i", {"i": tarifa},
          "23001", mensaje=mensaje)
    falla(conexion, "DELETE FROM tarifa WHERE id = :i", {"i": tarifa}, "23001", mensaje=mensaje)
    falla(conexion, "TRUNCATE tarifa CASCADE", {}, "23001", mensaje=mensaje)
    assert conexion.scalar(text("SELECT valor FROM tarifa WHERE id = :i"), {"i": tarifa}) == 120000
