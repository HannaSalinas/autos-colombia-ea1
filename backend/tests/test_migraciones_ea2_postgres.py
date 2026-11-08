"""Migraciones 0006 (cuentas) y 0007 (gestión de celdas): restricciones de la base y aplicación
sobre datos de la EA1. Iteración 2.

Las pruebas de restricciones trabajan dentro de una transacción que se revierte. La prueba de
"datos de la EA1" baja la base de pruebas a la 0005, inserta datos con la forma de la EA1, vuelve a
subir a la última migración y limpia por id; al final la base siempre queda en la última revisión.
"""

import os
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from conftest import ALEMBIC_HEAD, codigos_celda_libres
from app.database import get_engine

ALEMBIC_INI = str(Path(__file__).resolve().parents[1] / "alembic.ini")
# Un hash con la forma de bcrypt y costo 12 (60 caracteres). La base solo revisa la forma.
HASH_12 = "$2b$12$" + "a" * 53

con_postgres = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


# --- SQL offline: no necesita base de datos ---

def sql_offline(rango: str) -> str:
    output = StringIO()
    command.upgrade(Config(ALEMBIC_INI, output_buffer=output), rango, sql=True)
    return output.getvalue()


def test_sql_offline_de_0006():
    sql = sql_offline("0005:0006")
    assert "ALTER TABLE operador ALTER COLUMN telefono DROP NOT NULL" in sql
    assert "CREATE TABLE cuenta_usuario" in sql and "CREATE TABLE auditoria_cuenta" in sql
    assert "CREATE UNIQUE INDEX uq_cuenta_usuario_nombre ON cuenta_usuario (lower(nombre_usuario))" in sql
    assert "CHECK (nombre_usuario ~ '^[a-z0-9._]{4,30}$')" in sql
    assert "CHECK (rol IN ('ADMINISTRADOR', 'OPERADOR'))" in sql
    assert "(1[2-9]|[23][0-9])" in sql            # costo bcrypt >= 12
    assert "char_length(nombre) BETWEEN 3 AND 80" in sql and "NOT VALID" in sql
    assert sql.count("ON DELETE RESTRICT") == 3
    # Lo único que se "quita" es el NOT NULL del teléfono: no se borran tablas, columnas ni restricciones.
    assert sql.count("DROP") == 1 and "telefono DROP NOT NULL" in sql


def test_sql_offline_de_0007():
    sql = sql_offline("0006:0007")
    assert "ALTER TABLE celda ADD COLUMN ubicacion TEXT" in sql
    assert "ALTER TABLE celda ADD COLUMN habilitada BOOLEAN DEFAULT true NOT NULL" in sql
    assert "char_length(ubicacion) BETWEEN 1 AND 60" in sql
    assert "codigo ~ '^C(0[1-9]|[1-9][0-9])$'" in sql and "codigo ~ '^M(0[1-9]|[1-9][0-9])$'" in sql
    assert "CREATE UNIQUE INDEX uq_celda_codigo_ci ON celda (upper(codigo))" in sql
    assert "CREATE INDEX ix_estancia_celda ON estancia (celda_id)" in sql
    assert "CREATE TABLE auditoria_celda" in sql
    assert sql.count("ON DELETE RESTRICT") == 2
    assert "DROP" not in sql


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


def falla(conexion, sql: str, params: dict, estado: str, restriccion: str | None = None) -> None:
    with pytest.raises(IntegrityError) as error:
        with conexion.begin_nested():
            conexion.execute(text(sql), params)
    assert error.value.orig.sqlstate == estado
    if restriccion:
        assert error.value.orig.diag.constraint_name == restriccion


def persona(conexion, nombre: str = "Persona de prueba") -> int:
    return conexion.scalar(text("INSERT INTO operador (nombre) VALUES (:n) RETURNING id"), {"n": nombre})


CUENTA = ("INSERT INTO cuenta_usuario (operador_id, nombre_usuario, hash_contrasena, rol) "
          "VALUES (:o, :u, :h, :r) RETURNING id")


def test_persona_sin_telefono_y_nombre_de_3_a_80(conexion):
    # Teléfono opcional (0006); si se da, sigue sin poder estar vacío.
    assert persona(conexion, "Ana") and persona(conexion, "a" * 80)
    falla(conexion, "INSERT INTO operador (nombre, telefono) VALUES ('Ana', ' ')", {}, "23514")
    for nombre in ("Al", "a" * 81, " Ana", "Ana "):
        falla(conexion, "INSERT INTO operador (nombre) VALUES (:n)", {"n": nombre}, "23514",
              "ck_operador_nombre_longitud")


def test_cuenta_usuario_restricciones(conexion):
    columnas = {c["name"]: c for c in inspect(conexion).get_columns("cuenta_usuario")}
    assert set(columnas) == {"id", "operador_id", "nombre_usuario", "hash_contrasena", "rol", "activa",
                             "version_sesion", "creada_en"}
    assert not any(c["nullable"] for c in columnas.values())
    o = persona(conexion)
    cuenta = conexion.scalar(text(CUENTA), {"o": o, "u": "prueba.ea2", "h": HASH_12, "r": "OPERADOR"})
    fila = conexion.execute(text("SELECT activa, version_sesion, creada_en FROM cuenta_usuario WHERE id = :i"),
                            {"i": cuenta}).one()
    assert fila.activa is True and fila.version_sesion == 0 and fila.creada_en is not None
    # Una persona, una cuenta.
    falla(conexion, CUENTA, {"o": o, "u": "otra.cuenta", "h": HASH_12, "r": "OPERADOR"}, "23505",
          "uq_cuenta_usuario_operador")
    # Mismo nombre de usuario: el índice único lo rechaza (sin distinguir mayúsculas).
    falla(conexion, CUENTA, {"o": persona(conexion), "u": "prueba.ea2", "h": HASH_12, "r": "OPERADOR"},
          "23505", "uq_cuenta_usuario_nombre")
    for usuario in ("abc", "a" * 31, "Prueba.ea2", "con espacio", "guion-medio"):
        falla(conexion, CUENTA, {"o": persona(conexion), "u": usuario, "h": HASH_12, "r": "OPERADOR"},
              "23514", "ck_cuenta_usuario_nombre_formato")
    assert conexion.scalar(text(CUENTA), {"o": persona(conexion), "u": "abcd", "h": HASH_12, "r": "OPERADOR"})
    assert conexion.scalar(text(CUENTA), {"o": persona(conexion), "u": "b" * 30, "h": HASH_12,
                                          "r": "ADMINISTRADOR"})
    falla(conexion, CUENTA, {"o": persona(conexion), "u": "rol.malo", "h": HASH_12, "r": "SUPERVISOR"},
          "23514", "ck_cuenta_usuario_rol")
    # Nunca texto plano ni bcrypt con costo menor a 12.
    for hash_malo in ("clave123", "$2b$10$" + "a" * 53, "$2b$12$" + "a" * 52):
        falla(conexion, CUENTA, {"o": persona(conexion), "u": "hash.malo", "h": hash_malo, "r": "OPERADOR"},
              "23514", "ck_cuenta_usuario_hash_bcrypt")
    falla(conexion, "UPDATE cuenta_usuario SET version_sesion = -1 WHERE id = :i", {"i": cuenta}, "23514")
    # La persona con cuenta no se puede borrar (RESTRICT).
    falla(conexion, "DELETE FROM operador WHERE id = :o", {"o": o}, "23503")


def test_indice_de_usuario_es_sin_distinguir_mayusculas(conexion):
    definicion = conexion.scalar(text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_cuenta_usuario_nombre'"))
    assert "UNIQUE" in definicion and "lower(nombre_usuario)" in definicion


def test_celda_ubicacion_habilitada_y_formato(conexion):
    carro, otro, tercero = codigos_celda_libres(conexion, "CARRO", 3)
    celda = conexion.scalar(text("INSERT INTO celda (codigo, tipo) VALUES (:c, 'CARRO') RETURNING id"), {"c": carro})
    fila = conexion.execute(text("SELECT habilitada, ubicacion FROM celda WHERE id = :i"), {"i": celda}).one()
    assert fila.habilitada is True and fila.ubicacion is None
    conexion.execute(text("UPDATE celda SET ubicacion = :u WHERE id = :i"), {"u": "a" * 60, "i": celda})
    for ubicacion in ("a" * 61, "", "  ", " Sótano", "Sótano "):
        falla(conexion, "UPDATE celda SET ubicacion = :u WHERE id = :i", {"u": ubicacion, "i": celda}, "23514",
              "ck_celda_ubicacion")
    falla(conexion, "UPDATE celda SET habilitada = NULL WHERE id = :i", {"i": celda}, "23502")
    # Código C o M + 01..99, con el prefijo de su tipo.
    for codigo, tipo in (("C00", "CARRO"), ("C100", "CARRO"), ("X05", "CARRO"), (otro, "MOTO")):
        falla(conexion, "INSERT INTO celda (codigo, tipo) VALUES (:c, :t)", {"c": codigo, "t": tipo}, "23514")
    # Un cambio de tipo sin cambiar el código también lo rechaza la base.
    falla(conexion, "UPDATE celda SET tipo = 'MOTO' WHERE id = :i", {"i": celda}, "23514", "ck_celda_codigo_formato")
    assert conexion.scalar(text("INSERT INTO celda (codigo, tipo) VALUES (:c, 'CARRO') RETURNING id"), {"c": tercero})
    definicion = conexion.scalar(text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_celda_codigo_ci'"))
    assert "UNIQUE" in definicion and "upper(codigo)" in definicion


def test_restricciones_nuevas_no_revisan_datos_antiguos(conexion):
    # NOT VALID: las filas que ya existían no se revisan; las nuevas y las modificadas, sí.
    # El nombre de la persona queda siempre NOT VALID. Los CHECK de celda los valida la 0008 cuando
    # todos los datos cumplen (test_migracion_0008_postgres.py); ubicacion nació validado (0007).
    estado = dict(conexion.execute(text(
        "SELECT conname, convalidated FROM pg_constraint WHERE conname IN "
        "('ck_operador_nombre_longitud', 'ck_celda_ubicacion')"
    )).all())
    assert estado == {"ck_operador_nombre_longitud": False, "ck_celda_ubicacion": True}


def test_auditoria_restricciones(conexion):
    cuenta = conexion.scalar(text(CUENTA), {"o": persona(conexion), "u": "auditada", "h": HASH_12, "r": "OPERADOR"})
    celda = conexion.scalar(text("INSERT INTO celda (codigo, tipo) VALUES (:c, 'MOTO') RETURNING id"),
                            {"c": codigos_celda_libres(conexion, "MOTO")[0]})
    # El actor puede ser NULL (lo hizo el sistema, con las semillas).
    conexion.execute(text("INSERT INTO auditoria_cuenta (cuenta_id, accion) VALUES (:c, 'CREAR')"), {"c": cuenta})
    conexion.execute(text("INSERT INTO auditoria_celda (celda_id, actor_cuenta_id, accion, detalle) "
                          "VALUES (:c, :a, 'EDITAR', 'ubicación: — → Sótano')"), {"c": celda, "a": cuenta})
    falla(conexion, "INSERT INTO auditoria_cuenta (cuenta_id, accion) VALUES (:c, 'EDITAR')", {"c": cuenta},
          "23514", "ck_auditoria_cuenta_accion")
    falla(conexion, "INSERT INTO auditoria_celda (celda_id, accion) VALUES (:c, 'ELIMINAR')", {"c": celda},
          "23514", "ck_auditoria_celda_accion")
    falla(conexion, "INSERT INTO auditoria_celda (celda_id, accion, detalle) VALUES (:c, 'CREAR', :d)",
          {"c": celda, "d": "x" * 501}, "23514", "ck_auditoria_celda_detalle")
    falla(conexion, "INSERT INTO auditoria_celda (celda_id, accion) VALUES (9223372036854775807, 'CREAR')", {},
          "23503")
    # Con auditoría, ni la cuenta ni la celda se pueden borrar (RESTRICT).
    falla(conexion, "DELETE FROM cuenta_usuario WHERE id = :c", {"c": cuenta}, "23503")
    falla(conexion, "DELETE FROM celda WHERE id = :c", {"c": celda}, "23503")


# --- Aplicar 0006 y 0007 sobre datos de la EA1 ---

@con_postgres
def test_0006_y_0007_se_aplican_sobre_datos_de_la_ea1():
    engine = get_engine()
    with engine.connect() as c:
        if c.scalar(text("SELECT count(*) FROM celda")):
            pytest.skip("Baja y sube migraciones: requiere la base de pruebas vacía "
                        "(docker compose run --rm backend-tests).")
    config = Config(ALEMBIC_INI)
    ids: dict[str, int] = {}
    try:
        command.downgrade(config, "0005")
        with engine.begin() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
            # Datos con la forma de la EA1: dos operadores con teléfono, una celda con el código libre
            # que permitía el proyecto base, estancias, una corrección y una novedad.
            ids["marta"] = c.scalar(text("INSERT INTO operador (nombre, telefono) VALUES "
                                         "('Marta EA1 (Portería 1)', '3101112233') RETURNING id"))
            ids["diego"] = c.scalar(text("INSERT INTO operador (nombre, telefono) VALUES ('Di', '3102223344') "
                                         "RETURNING id"))   # nombre de 2 letras: la EA1 lo aceptaba
            ids["vieja"] = c.scalar(text("INSERT INTO celda (codigo, tipo) VALUES ('ZONA-A', 'CARRO') RETURNING id"))
            ids["nueva"] = c.scalar(text("INSERT INTO celda (codigo, tipo) VALUES ('C98', 'CARRO') RETURNING id"))
            ids["cliente"] = c.scalar(text("INSERT INTO cliente (documento, nombre, telefono) VALUES "
                                           "('EA1-MIGRACION', 'Cliente EA1', '300') RETURNING id"))
            ids["vehiculo"] = c.scalar(text("INSERT INTO vehiculo (placa, color, modelo, marca, tipo, cliente_id) "
                                            "VALUES ('ZZZ998', 'Rojo', 2020, 'M', 'AUTOMOVIL', :c) RETURNING id"),
                                       {"c": ids["cliente"]})
            ids["cerrada"] = c.scalar(text(
                "INSERT INTO estancia (vehiculo_id, celda_id, entrada, salida, operador_entrada_id, operador_salida_id) "
                "VALUES (:v, :vieja, now() - interval '3 hours', now() - interval '2 hours', :m, :d) RETURNING id"
            ), {"v": ids["vehiculo"], "vieja": ids["vieja"], "m": ids["marta"], "d": ids["diego"]})
            ids["abierta"] = c.scalar(text(
                "INSERT INTO estancia (vehiculo_id, celda_id, operador_entrada_id) VALUES (:v, :n, :d) RETURNING id"
            ), {"v": ids["vehiculo"], "n": ids["nueva"], "d": ids["diego"]})
            ids["correccion"] = c.scalar(text(
                "INSERT INTO correccion_celda (estancia_id, celda_anterior_id, celda_nueva_id, operador_id, motivo) "
                "VALUES (:e, :vieja, :n, :m, 'Se parqueó en otra') RETURNING id"
            ), {"e": ids["abierta"], "vieja": ids["vieja"], "n": ids["nueva"], "m": ids["marta"]})
            ids["novedad"] = c.scalar(text(
                "INSERT INTO novedad (estancia_id, operador_id, tipo, descripcion) VALUES (:e, :m, 'RAYON', 'Rayón') "
                "RETURNING id"), {"e": ids["abierta"], "m": ids["marta"]})

        command.upgrade(config, "head")

        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
            # La autoría de la EA1 no cambia.
            estancias = c.execute(text("SELECT id, operador_entrada_id, operador_salida_id FROM estancia "
                                       "WHERE id IN (:a, :b) ORDER BY id"),
                                  {"a": ids["cerrada"], "b": ids["abierta"]}).all()
            assert [tuple(e) for e in estancias] == [(ids["cerrada"], ids["marta"], ids["diego"]),
                                                    (ids["abierta"], ids["diego"], None)]
            assert c.scalar(text("SELECT operador_id FROM correccion_celda WHERE id = :i"),
                            {"i": ids["correccion"]}) == ids["marta"]
            assert c.scalar(text("SELECT operador_id FROM novedad WHERE id = :i"), {"i": ids["novedad"]}) == ids["marta"]
            # Personas y celdas antiguas siguen ahí, aunque no cumplan las reglas nuevas (NOT VALID).
            assert c.scalar(text("SELECT telefono FROM operador WHERE id = :i"), {"i": ids["diego"]}) == "3102223344"
            celdas = c.execute(text("SELECT codigo, habilitada, ubicacion FROM celda WHERE id IN (:a, :b) "
                                    "ORDER BY id"), {"a": ids["vieja"], "b": ids["nueva"]}).all()
            assert [tuple(f) for f in celdas] == [("ZONA-A", True, None), ("C98", True, None)]
            # 0008: por 'ZONA-A' el formato del código queda NOT VALID; el tipo sí se valida.
            assert dict(c.execute(text(
                "SELECT conname, convalidated FROM pg_constraint "
                "WHERE conname IN ('ck_celda_tipo', 'ck_celda_codigo_formato')"
            )).all()) == {"ck_celda_tipo": True, "ck_celda_codigo_formato": False}

        # Ida y vuelta: la bajada también funciona con datos, y la subida se puede repetir.
        command.downgrade(config, "0005")
        command.upgrade(config, "head")
    finally:
        command.upgrade(config, "head")
        with engine.begin() as c:
            for tabla, clave in (("novedad", "novedad"), ("correccion_celda", "correccion"),
                                 ("estancia", "abierta"), ("estancia", "cerrada"), ("vehiculo", "vehiculo"),
                                 ("cliente", "cliente"), ("celda", "vieja"), ("celda", "nueva"),
                                 ("operador", "marta"), ("operador", "diego")):
                if clave in ids:
                    c.execute(text(f"DELETE FROM {tabla} WHERE id = :i"), {"i": ids[clave]})
        # Sin las celdas antiguas, pasar otra vez por la 0008 deja los CHECK de celda validados.
        command.downgrade(config, "0007")
        command.upgrade(config, "head")
        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
