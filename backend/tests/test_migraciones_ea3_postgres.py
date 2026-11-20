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


def test_checks_de_cliente_validados_en_la_base_de_pruebas(conexion):
    # La 0009 crea los CHECK de formato NOT VALID; la 0011 los valida si todos los clientes cumplen.
    # La base de pruebas no tiene clientes antiguos, así que quedan validados
    # (el caso con clientes que no cumplen está en test_migracion_0011_postgres.py).
    estado = dict(conexion.execute(text(
        "SELECT conname, convalidated FROM pg_constraint WHERE conname LIKE 'ck_cliente_%'"
    )).all())
    assert estado["ck_cliente_documento_formato"] is True and estado["ck_cliente_nombre_longitud"] is True
    assert estado["ck_cliente_telefono_formato"] is True
    # Las columnas nuevas nacieron con datos que cumplen: esos CHECK se validan completos desde la 0009.
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


# --- 0010: pagos ---

def test_sql_offline_de_0010():
    sql = sql_offline("0009:0010")
    assert "CREATE EXTENSION IF NOT EXISTS btree_gist" in sql
    assert "CREATE SEQUENCE pago_comprobante_seq MINVALUE 1 MAXVALUE 999999 NO CYCLE" in sql
    assert "CREATE TABLE pago" in sql and "CHECK (monto = valor_mensual * meses)" in sql
    assert "FOREIGN KEY(tarifa_id, tipo_vehiculo, valor_mensual) REFERENCES tarifa (id, tipo_vehiculo, valor)" in sql
    assert "referencia IS NOT NULL AND referencia ~ '^[A-Za-z0-9-]{4,30}$'" in sql
    assert "ALTER TABLE mensualidad ADD COLUMN pago_id BIGINT" in sql
    assert "FOREIGN KEY(pago_id, pago_estado) REFERENCES pago (id, estado) ON DELETE RESTRICT ON UPDATE CASCADE" in sql
    assert "EXCLUDE USING gist (vehiculo_id WITH =, daterange(fecha_inicio, fecha_fin, '[]') WITH &&) " \
           "WHERE (pago_estado = 'VALIDO')" in sql
    assert "BEFORE UPDATE OR DELETE ON pago" in sql and "BEFORE TRUNCATE ON pago" in sql
    assert "BEFORE UPDATE OR DELETE ON mensualidad" in sql and "BEFORE TRUNCATE ON mensualidad" in sql
    # Sin conexión, el aviso de superposiciones antiguas se escribe en SQL.
    assert "periodos antiguos que se superponen" in sql
    # No borra tablas, columnas, restricciones ni datos.
    for borrado in ("DROP TABLE", "DROP COLUMN", "DROP CONSTRAINT", "DROP INDEX", "DELETE FROM"):
        assert borrado not in sql


class Datos:
    """Vehículo, tarifa y cuenta para probar pagos con SQL directo."""

    def __init__(self, conexion, placa: str = "ZZY991", valor: int = 120000, tarifa: int | None = None) -> None:
        self.c = conexion
        cliente_id = cliente(conexion, d="88" + placa[3:] + "88")
        self.vehiculo = conexion.scalar(text(
            "INSERT INTO vehiculo (placa, color, modelo, marca, tipo, cliente_id) "
            "VALUES (:p, 'Rojo', 2024, 'Mazda', 'AUTOMOVIL', :c) RETURNING id"), {"p": placa, "c": cliente_id})
        # Dos tarifas del mismo tipo en una transacción tendrían el mismo vigente_desde (now() es la hora
        # de inicio de la transacción) y uq_tarifa_tipo_desde las rechaza: se puede reutilizar una.
        self.tarifa = tarifa or conexion.scalar(text(TARIFA), {"t": "AUTOMOVIL", "v": valor})
        self.valor = valor
        self.cuenta = cuenta(conexion, f"cuenta.{placa.lower()}")

    def pago(self, meses: int = 1, metodo: str = "EFECTIVO", referencia: str | None = None) -> int:
        return self.c.scalar(text(
            "INSERT INTO pago (meses, tarifa_id, tipo_vehiculo, valor_mensual, monto, metodo, referencia, "
            "registrado_por_cuenta_id) VALUES (:m, :t, 'AUTOMOVIL', :v, :monto, :metodo, :r, :c) RETURNING id"),
            {"m": meses, "t": self.tarifa, "v": self.valor, "monto": self.valor * meses, "metodo": metodo,
             "r": referencia, "c": self.cuenta})

    def periodo(self, inicio: str, fin: str, pago: int | None = None) -> int:
        return self.c.scalar(text(
            "INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin, pago_id, pago_estado) "
            "VALUES (:v, :i, :f, :p, :e) RETURNING id"),
            {"v": self.vehiculo, "i": inicio, "f": fin, "p": pago, "e": "VALIDO" if pago else None})

    def anular(self, pago: int, motivo: str = "Error al digitar la placa") -> None:
        self.c.execute(text("UPDATE pago SET estado = 'ANULADO', anulado_en = now(), anulado_por_cuenta_id = :c, "
                            "motivo_anulacion = :m WHERE id = :p"), {"c": self.cuenta, "m": motivo, "p": pago})


PAGO = ("INSERT INTO pago (meses, tarifa_id, tipo_vehiculo, valor_mensual, monto, metodo, referencia, "
        "registrado_por_cuenta_id) VALUES (:m, :t, :tipo, :v, :monto, :metodo, :r, :c)")


def test_pago_reglas_en_sus_limites(conexion):
    d = Datos(conexion)
    base = {"m": 1, "t": d.tarifa, "tipo": "AUTOMOVIL", "v": d.valor, "monto": d.valor, "metodo": "EFECTIVO",
            "r": None, "c": d.cuenta}
    fila = conexion.execute(text(
        "SELECT comprobante, estado, fecha FROM pago WHERE id = :i"), {"i": d.pago(6)}).one()
    assert fila.estado == "VALIDO" and fila.fecha is not None
    assert fila.comprobante.startswith("RC-") and len(fila.comprobante) == 9
    for meses in (0, 7):
        falla(conexion, PAGO, {**base, "m": meses, "monto": d.valor * meses}, "23514", "ck_pago_meses")
    # El monto lo calcula el sistema (D11): la base exige tarifa × meses.
    falla(conexion, PAGO, {**base, "monto": d.valor + 1}, "23514", "ck_pago_monto")
    # El valor y el tipo copiados deben ser los de una tarifa real (FK compuesta).
    falla(conexion, PAGO, {**base, "v": d.valor + 1000, "monto": d.valor + 1000}, "23503", "fk_pago_tarifa")
    falla(conexion, PAGO, {**base, "tipo": "MOTO"}, "23503", "fk_pago_tarifa")
    falla(conexion, PAGO, {**base, "metodo": "CHEQUE"}, "23514", "ck_pago_metodo")
    # Referencia: vacía en efectivo; obligatoria de 4 a 30 en transferencia y tarjeta.
    assert d.pago(1, "TRANSFERENCIA", "A1B2") and d.pago(1, "TARJETA", "x" * 30)
    falla(conexion, PAGO, {**base, "r": "TRX-1234"}, "23514", "ck_pago_referencia")
    for metodo in ("TRANSFERENCIA", "TARJETA"):
        for referencia in (None, "ABC", "x" * 31, "con espacio"):
            falla(conexion, PAGO, {**base, "metodo": metodo, "r": referencia}, "23514", "ck_pago_referencia")
    columnas = {c["name"]: str(c["type"]) for c in inspect(conexion).get_columns("pago")}
    assert columnas["monto"] == "INTEGER" and columnas["valor_mensual"] == "INTEGER"   # RNF-22


def test_comprobante_unico_garantizado_por_la_base(conexion):
    d = Datos(conexion)
    primero = conexion.scalar(text("SELECT comprobante FROM pago WHERE id = :i"), {"i": d.pago()})
    segundo = conexion.scalar(text("SELECT comprobante FROM pago WHERE id = :i"), {"i": d.pago()})
    assert primero != segundo and int(segundo[3:]) > int(primero[3:])
    falla(conexion, PAGO.replace("registrado_por_cuenta_id)", "registrado_por_cuenta_id, comprobante)")
          .replace(":c)", ":c, :comp)"),
          {"m": 1, "t": d.tarifa, "tipo": "AUTOMOVIL", "v": d.valor, "monto": d.valor, "metodo": "EFECTIVO",
           "r": None, "c": d.cuenta, "comp": primero}, "23505", "uq_pago_comprobante")


def test_anular_una_sola_vez_con_sus_datos(conexion):
    d = Datos(conexion)
    pago = d.pago()
    periodo = d.periodo("2026-11-20", "2026-12-19", pago)
    # Sin motivo, con motivo corto o con espacios exteriores: lo rechaza el CHECK.
    for motivo in (None, "a" * 9, "a" * 201, " " + "a" * 10):
        falla(conexion, "UPDATE pago SET estado = 'ANULADO', anulado_en = now(), anulado_por_cuenta_id = :c, "
                        "motivo_anulacion = :m WHERE id = :p", {"c": d.cuenta, "m": motivo, "p": pago}, "23514",
              "ck_pago_anulacion")
    d.anular(pago, "a" * 10)
    # ON UPDATE CASCADE: la copia del estado en el periodo cambia en la misma sentencia.
    assert conexion.scalar(text("SELECT pago_estado FROM mensualidad WHERE id = :i"), {"i": periodo}) == "ANULADO"
    mensaje = "Un pago no se edita ni se elimina"
    # Una sola vez: ni volver a VALIDO, ni cambiar el motivo de un anulado.
    falla(conexion, "UPDATE pago SET estado = 'VALIDO', anulado_en = NULL, anulado_por_cuenta_id = NULL, "
                    "motivo_anulacion = NULL WHERE id = :p", {"p": pago}, "23001", mensaje=mensaje)
    falla(conexion, "UPDATE pago SET motivo_anulacion = 'Otro motivo distinto' WHERE id = :p", {"p": pago}, "23001",
          mensaje=mensaje)


def test_pago_no_se_edita_ni_se_borra_aunque_se_intente_en_la_base(conexion):
    d = Datos(conexion)
    pago = d.pago(2, "TRANSFERENCIA", "TRX-0001")
    mensaje = "Un pago no se edita ni se elimina"
    for cambio in ("monto = monto", "referencia = 'TRX-0002'", "fecha = now() - interval '1 day'",
                   "meses = 1, monto = valor_mensual", "comprobante = 'RC-999998'"):
        falla(conexion, f"UPDATE pago SET {cambio} WHERE id = :p", {"p": pago}, "23001", mensaje=mensaje)
    # Anular cambiando a la vez otro dato tampoco se permite.
    falla(conexion, "UPDATE pago SET estado = 'ANULADO', anulado_en = now(), anulado_por_cuenta_id = :c, "
                    "motivo_anulacion = 'Error al digitar', referencia = 'TRX-0003' WHERE id = :p",
          {"c": d.cuenta, "p": pago}, "23001", mensaje=mensaje)
    falla(conexion, "DELETE FROM pago WHERE id = :p", {"p": pago}, "23001", mensaje=mensaje)
    falla(conexion, "TRUNCATE pago CASCADE", {}, "23001", mensaje=mensaje)
    assert conexion.scalar(text("SELECT referencia FROM pago WHERE id = :p"), {"p": pago}) == "TRX-0001"


def test_periodo_pagado_no_se_edita_ni_se_borra(conexion):
    d = Datos(conexion)
    pagado = d.periodo("2026-11-20", "2026-12-19", d.pago())
    antiguo = d.periodo("2026-09-01", "2026-10-01")
    for cambio in ("fecha_fin = '2027-01-19'", "fecha_inicio = '2026-11-21'", "pago_id = NULL, pago_estado = NULL"):
        falla(conexion, f"UPDATE mensualidad SET {cambio} WHERE id = :i", {"i": pagado}, "23001",
              mensaje="Un periodo pagado no se edita")
    falla(conexion, "DELETE FROM mensualidad WHERE id = :i", {"i": pagado}, "23001",
          mensaje="Un periodo pagado no se elimina")
    falla(conexion, "TRUNCATE mensualidad", {}, "23001", mensaje="Un periodo pagado no se elimina")
    # La copia del estado solo la cambia la cascada: a mano no coincide con el pago (FK compuesta).
    falla(conexion, "UPDATE mensualidad SET pago_estado = 'ANULADO' WHERE id = :i", {"i": pagado}, "23503",
          "fk_mensualidad_pago")
    # Un periodo antiguo no se puede vincular a un pago.
    falla(conexion, "UPDATE mensualidad SET pago_id = :p, pago_estado = 'VALIDO' WHERE id = :i",
          {"p": d.pago(), "i": antiguo}, "23001", mensaje="no se puede vincular")
    # Los periodos antiguos siguen como antes (D10): la regla nueva solo protege los pagados.
    conexion.execute(text("UPDATE mensualidad SET fecha_fin = '2026-10-02' WHERE id = :i"), {"i": antiguo})
    conexion.execute(text("DELETE FROM mensualidad WHERE id = :i"), {"i": antiguo})


def test_vinculo_uno_a_uno_y_estado_coherente(conexion):
    d = Datos(conexion)
    pago = d.pago()
    d.periodo("2026-11-20", "2026-12-19", pago)
    falla(conexion, "INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin, pago_id, pago_estado) "
                    "VALUES (:v, '2027-03-01', '2027-03-31', :p, 'VALIDO')", {"v": d.vehiculo, "p": pago},
          "23505", "uq_mensualidad_pago")
    falla(conexion, "INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin, pago_id) "
                    "VALUES (:v, '2027-03-01', '2027-03-31', :p)", {"v": d.vehiculo, "p": d.pago()},
          "23514", "ck_mensualidad_pago")
    falla(conexion, "INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin, pago_id, pago_estado) "
                    "VALUES (:v, '2027-03-01', '2027-03-31', :p, 'ANULADO')", {"v": d.vehiculo, "p": d.pago()},
          "23503", "fk_mensualidad_pago")


def test_exclusion_parcial_de_periodos_pagados(conexion):
    d = Datos(conexion)
    d.periodo("2026-11-20", "2026-12-19", d.pago())
    # Encadenado (empieza el día siguiente al fin): se acepta.
    d.periodo("2026-12-20", "2027-01-19", d.pago())
    # Cruzarse un solo día con otro periodo pagado y no anulado: lo rechaza la base (23P01).
    sql = ("INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin, pago_id, pago_estado) "
           "VALUES (:v, :i, :f, :p, 'VALIDO')")
    for inicio, fin in (("2027-01-19", "2027-02-18"), ("2026-12-01", "2026-12-10"), ("2026-10-01", "2027-03-01")):
        falla(conexion, sql, {"v": d.vehiculo, "i": inicio, "f": fin, "p": d.pago()}, "23P01",
              "ex_mensualidad_pagada_sin_superposicion")
    # Anulado, su periodo deja de contar: ahora sí cabe otro en las mismas fechas.
    ultimo = conexion.scalar(text("SELECT pago_id FROM mensualidad WHERE vehiculo_id = :v AND fecha_inicio = "
                                  "'2026-12-20'"), {"v": d.vehiculo})
    d.anular(ultimo)
    d.periodo("2026-12-20", "2027-01-19", d.pago())
    # Otro vehículo puede tener las mismas fechas.
    otro = Datos(conexion, "ZZY992", tarifa=d.tarifa)
    otro.periodo("2026-11-20", "2026-12-19", otro.pago())


def test_limitacion_declarada_periodos_antiguos_no_entran_en_la_exclusion(conexion):
    # RNF-23: entre un periodo pagado y uno antiguo la no superposición la garantiza el servicio,
    # no la base. Esta prueba deja escrita esa limitación: la base acepta el cruce.
    d = Datos(conexion)
    d.periodo("2026-11-01", "2026-12-01")
    d.periodo("2026-12-01", "2027-01-01")   # dos antiguos que se tocan, como JKL321
    d.periodo("2026-12-15", "2027-01-14", d.pago())
    assert conexion.scalar(text("SELECT count(*) FROM mensualidad WHERE vehiculo_id = :v"), {"v": d.vehiculo}) == 3


def test_extension_y_restriccion_de_exclusion_instaladas(conexion):
    assert conexion.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'btree_gist'")) == 1
    definicion = conexion.scalar(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ex_mensualidad_pagada_sin_superposicion'"))
    assert "EXCLUDE USING gist" in definicion and "pago_estado = 'VALIDO'" in definicion


# --- Aplicar 0009 y 0010 sobre datos de las iteraciones 1 y 2 ---

@con_postgres
def test_0009_y_0010_se_aplican_sobre_datos_anteriores_sin_modificarlos(caplog):
    import logging
    engine = get_engine()
    with engine.connect() as c:
        if c.scalar(text("SELECT count(*) FROM celda")):
            pytest.skip("Baja y sube migraciones: requiere la base de pruebas vacía "
                        "(docker compose run --rm backend-tests).")
    config = Config(ALEMBIC_INI)
    ids: dict[str, int] = {}
    try:
        command.downgrade(config, "0008")
        with engine.begin() as c:
            # Clientes con la forma de la EA1: documento con guion, teléfono corto, nombre de 2 letras.
            ids["cliente"] = c.scalar(text("INSERT INTO cliente (documento, nombre, telefono) VALUES "
                                           "('EA1-0009', 'Lu', '300') RETURNING id"))
            ids["vehiculo"] = c.scalar(text("INSERT INTO vehiculo (placa, color, modelo, marca, tipo, cliente_id) "
                                            "VALUES ('ZZX321', 'Plata', 2024, 'Chevrolet', 'AUTOMOVIL', :c) "
                                            "RETURNING id"), {"c": ids["cliente"]})
            # Como la semilla "renovada" (JKL321): el segundo periodo empieza el día en que termina el primero.
            ids["primero"] = c.scalar(text("INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin) VALUES "
                                           "(:v, current_date - 40, current_date - 9) RETURNING id"),
                                      {"v": ids["vehiculo"]})
            ids["segundo"] = c.scalar(text("INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin) VALUES "
                                           "(:v, current_date - 9, current_date + 21) RETURNING id"),
                                      {"v": ids["vehiculo"]})
            antes = c.execute(text("SELECT id, fecha_inicio, fecha_fin FROM mensualidad WHERE vehiculo_id = :v "
                                   "ORDER BY id"), {"v": ids["vehiculo"]}).all()

        with caplog.at_level(logging.WARNING, logger="alembic.migraciones"):
            command.upgrade(config, "head")             # no se detiene por los periodos que se tocan

        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
            fila = c.execute(text("SELECT tipo_documento, documento, nombre, telefono, registrado_en, "
                                  "registrado_por_cuenta_id FROM cliente WHERE id = :i"), {"i": ids["cliente"]}).one()
            assert tuple(fila) == ("CC", "EA1-0009", "Lu", "300", None, None)
            despues = c.execute(text("SELECT id, fecha_inicio, fecha_fin, pago_id, pago_estado FROM mensualidad "
                                     "WHERE vehiculo_id = :v ORDER BY id"), {"v": ids["vehiculo"]}).all()
            assert [tuple(f)[:3] for f in despues] == [tuple(f) for f in antes]
            assert all(f.pago_id is None and f.pago_estado is None for f in despues)
            # 0011: el cliente antiguo no cumple ninguno de los tres CHECK: quedan NOT VALID.
            assert dict(c.execute(text(
                "SELECT conname, convalidated FROM pg_constraint WHERE conname IN ('ck_cliente_documento_formato', "
                "'ck_cliente_nombre_longitud', 'ck_cliente_telefono_formato')")).all()) == {
                "ck_cliente_documento_formato": False, "ck_cliente_nombre_longitud": False,
                "ck_cliente_telefono_formato": False}
        avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("periodos antiguos que se superponen" in a and "ZZX321" in a for a in avisos)
        assert sum("queda NOT VALID" in a and str(ids["cliente"]) in a for a in avisos) == 3

        # Ida y vuelta con un pago registrado: la bajada también funciona con datos.
        with engine.begin() as c:
            ids["tarifa"] = c.scalar(text("INSERT INTO tarifa (tipo_vehiculo, valor) VALUES ('AUTOMOVIL', 120000) "
                                          "RETURNING id"))
            persona = c.scalar(text("INSERT INTO operador (nombre) VALUES ('Persona 0010') RETURNING id"))
            ids["persona"] = persona
            ids["cuenta"] = c.scalar(text("INSERT INTO cuenta_usuario (operador_id, nombre_usuario, hash_contrasena, "
                                          "rol) VALUES (:o, 'cuenta.migracion.0010', :h, 'OPERADOR') RETURNING id"),
                                     {"o": persona, "h": HASH_12})
            pago = c.scalar(text("INSERT INTO pago (meses, tarifa_id, tipo_vehiculo, valor_mensual, monto, metodo, "
                                 "registrado_por_cuenta_id) VALUES (1, :t, 'AUTOMOVIL', 120000, 120000, 'EFECTIVO', :c) "
                                 "RETURNING id"), {"t": ids["tarifa"], "c": ids["cuenta"]})
            c.execute(text("INSERT INTO mensualidad (vehiculo_id, fecha_inicio, fecha_fin, pago_id, pago_estado) "
                           "VALUES (:v, current_date + 22, current_date + 50, :p, 'VALIDO')"),
                      {"v": ids["vehiculo"], "p": pago})
        command.downgrade(config, "0008")
        with engine.connect() as c:
            # El periodo pagado y válido queda como periodo sin pago; los antiguos siguen igual.
            assert c.scalar(text("SELECT count(*) FROM mensualidad WHERE vehiculo_id = :v"), {"v": ids["vehiculo"]}) == 3
        command.upgrade(config, "head")
    finally:
        command.downgrade(config, "0008")    # sin triggers de pagos: se puede limpiar por id
        with engine.begin() as c:
            if "vehiculo" in ids:
                c.execute(text("DELETE FROM mensualidad WHERE vehiculo_id = :v"), {"v": ids["vehiculo"]})
            for tabla, clave in (("vehiculo", "vehiculo"), ("cliente", "cliente"), ("cuenta_usuario", "cuenta"),
                                 ("operador", "persona")):
                if clave in ids:
                    c.execute(text(f"DELETE FROM {tabla} WHERE id = :i"), {"i": ids[clave]})
        command.upgrade(config, "head")
        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == ALEMBIC_HEAD
