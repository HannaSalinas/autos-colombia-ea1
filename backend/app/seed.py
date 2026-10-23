"""Datos de demostración (ficticios). Se puede ejecutar varias veces: no duplica registros.

Uso: python -m app.seed
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.domain.reglas import TOTAL_CELDAS, fin_de_mensualidad, hoy_bogota, sumar_meses
from app.models import Celda, Cliente, Mensualidad, Operador, Vehiculo

# 80 celdas: C01–C70 para carros y M01–M10 para motos.
CELDAS = [(f"C{n:02d}", "CARRO") for n in range(1, TOTAL_CELDAS["CARRO"] + 1)] + [
    (f"M{n:02d}", "MOTO") for n in range(1, TOTAL_CELDAS["MOTO"] + 1)
]
# Un operador por portería.
OPERADORES = [("Marta Úsuga (Portería 1)", "3101112233"), ("Diego Arango (Portería 2)", "3102223344")]

CLIENTES = [
    # documento, nombre, teléfono, correo (opcional)
    ("1001234567", "Laura Gómez", "3001112233", "laura.gomez@example.com"),
    ("1002345678", "Carlos Pérez", "3012223344", None),
    ("1003456789", "Ana Restrepo", "3023334455", "ana.restrepo@example.com"),
    ("1004567890", "Jorge Mesa", "3034445566", "jorge.mesa@example.com"),
    ("1005678901", "Paola Ríos", "3045556677", None),
    ("1006789012", "Andrés Cano", "3056667788", "andres.cano@example.com"),
]

# placa, tipo, marca, modelo, color, documento del dueño, mensualidad para la demo
VEHICULOS = [
    ("ABC123", "AUTOMOVIL", "Mazda", 2022, "Rojo", "1001234567", "vigente"),
    ("KLM45D", "MOTO", "Yamaha", 2023, "Negro", "1001234567", "vigente"),
    ("DEF456", "CAMIONETA", "Toyota", 2020, "Blanco", "1002345678", "vencida"),
    ("GHI789", "AUTOMOVIL", "Renault", 2019, "Gris", "1003456789", "vence_hoy"),
    ("XYZ12A", "MOTO", "Honda", 2021, "Azul", "1003456789", "vencida"),
    ("JKL321", "AUTOMOVIL", "Chevrolet", 2024, "Plata", "1004567890", "renovada"),
    ("MNO654", "CAMIONETA", "Kia", 2025, "Verde", "1005678901", "sin_mensualidad"),
    ("PQR98B", "MOTO", "Suzuki", 2026, "Rojo", "1006789012", "empieza_manana"),
    ("STU852", "AUTOMOVIL", "Nissan", 2018, "Negro", "1006789012", "vigente"),
]


def mensualidades(caso: str, hoy: date) -> list[tuple[date, date]]:
    """Periodos (inicio, fin) según el caso de demostración, relativos a hoy."""
    if caso == "vigente":
        inicio = hoy - timedelta(days=10)
        return [(inicio, fin_de_mensualidad(inicio))]
    if caso == "vence_hoy":
        return [(sumar_meses(hoy, -1), hoy)]
    if caso == "vencida":
        fin = hoy - timedelta(days=5)
        return [(sumar_meses(fin, -1), fin)]
    if caso == "renovada":
        primera = hoy - timedelta(days=40)
        segunda = fin_de_mensualidad(primera)
        return [(primera, segunda), (segunda, fin_de_mensualidad(segunda))]
    if caso == "empieza_manana":
        inicio = hoy + timedelta(days=1)
        return [(inicio, fin_de_mensualidad(inicio))]
    return []


def sembrar(session: Session, hoy: date) -> dict[str, int]:
    creados = {"celdas": 0, "operadores": 0, "clientes": 0, "vehiculos": 0, "mensualidades": 0}
    existentes = set(session.scalars(select(Celda.codigo)))
    for codigo, tipo in CELDAS:
        if codigo not in existentes:
            session.add(Celda(codigo=codigo, tipo=tipo))
            creados["celdas"] += 1
    for nombre, telefono in OPERADORES:
        if session.scalar(select(Operador.id).where(Operador.nombre == nombre)) is None:
            session.add(Operador(nombre=nombre, telefono=telefono))
            creados["operadores"] += 1

    por_documento: dict[str, Cliente] = {}
    for documento, nombre, telefono, correo in CLIENTES:
        cliente = session.scalar(select(Cliente).where(Cliente.documento == documento))
        if cliente is None:
            cliente = Cliente(documento=documento, nombre=nombre, telefono=telefono, correo=correo)
            session.add(cliente)
            creados["clientes"] += 1
        por_documento[documento] = cliente
    session.flush()

    for placa, tipo, marca, modelo, color, documento, caso in VEHICULOS:
        if session.scalar(select(Vehiculo.id).where(Vehiculo.placa == placa)) is not None:
            continue  # ya existe: no se tocan sus mensualidades
        vehiculo = Vehiculo(placa=placa, tipo=tipo, marca=marca, modelo=modelo, color=color,
                            cliente_id=por_documento[documento].id)
        session.add(vehiculo)
        session.flush()
        creados["vehiculos"] += 1
        for inicio, fin in mensualidades(caso, hoy):
            session.add(Mensualidad(vehiculo_id=vehiculo.id, fecha_inicio=inicio, fecha_fin=fin))
            creados["mensualidades"] += 1
    return creados


def main() -> None:
    with Session(get_engine()) as session, session.begin():
        creados = sembrar(session, hoy_bogota())
    print("Semillas aplicadas. Nuevos registros: "
          + ", ".join(f"{cantidad} {tabla}" for tabla, cantidad in creados.items()))


if __name__ == "__main__":
    main()
