"""Medición de RNF-25: tiempo de respuesta (percentil 95) de las operaciones de pagos.

Escenario (documento de requerimientos de la EA3, RNF-25): registrar un pago, consultar el estado
de una mensualidad, consultar pagos y el resumen de recaudo, cada una con 4 solicitudes
simultáneas (dos porterías y la administración): p95 <= 1 s por operación.

Reutiliza las funciones de scripts/medir_rnf19.py (sesiones, percentil 95, ejecución en paralelo y
datos del equipo), así que mide igual que en la EA2.

Se ejecuta contra el sistema levantado con Docker (por defecto a través de nginx, como el usuario):
    docker compose down -v && docker compose up --build -d      # base limpia
    backend/.venv/bin/python scripts/medir_rnf25.py
    docker compose down -v && docker compose up --build -d      # volver a una base limpia

Los pagos no se pueden borrar (RNF-24): la medición deja clientes "Medicion RNF25", sus vehículos y
un pago de cada uno. Por eso se ejecuta sobre una base limpia y después se recrea. Lee
ADMIN_USUARIO y ADMIN_CONTRASENA de .env (nunca los escribe en el reporte). Genera
docs/evidencias/rnf25.md y docs/evidencias/rnf25.csv.

Los pagos se registran sobre vehículos distintos, que es el uso real (cada portería cobra a un
cliente). Dos pagos del mismo vehículo se registran a propósito uno después del otro (bloqueo de la
fila, RNF-23); eso lo prueban las pruebas de concurrencia, no esta medición.
"""

import argparse
import csv
import os
import random
import string
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from medir_rnf19 import SIMULTANEAS, Cliente, equipo, esperado, fila, medir_en_paralelo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "evidencias"
LIMITE = 1.0
TARIFA_AUTOMOVIL = 120000   # tarifa de las semillas; se comprueba antes de medir


def preparar_vehiculos(admin: Cliente, cantidad: int) -> list[str]:
    """Un cliente y un automóvil sin mensualidad por muestra (fuera de la medición)."""
    letra = random.choice(string.ascii_uppercase)
    placas = []
    for i in range(cantidad):
        _, r = admin.solicitud("POST", "/clientes", json={
            "tipo_documento": "CC", "documento": f"R25{letra}{datetime.now():%H%M%S}{i:03d}"[:15],
            "nombre": f"Medicion RNF25 {i}", "telefono": "3000000000"})
        esperado(r, 201)
        placa = f"RN{letra}{i:03d}"
        _, r = admin.solicitud("POST", "/vehiculos", json={
            "placa": placa, "color": "Gris", "modelo": 2024, "marca": "Medicion", "tipo": "AUTOMOVIL",
            "cliente_id": r.json()["id"]})
        esperado(r, 201)
        placas.append(placa)
    return placas


def escenario_pagos(url: str, admin_usuario: str, admin_clave: str, muestras: int) -> dict[str, list[float]]:
    clientes = [Cliente(url) for _ in range(SIMULTANEAS)]
    for c in clientes:
        c.ingresar(admin_usuario, admin_clave)
    admin = clientes[0]
    _, r = admin.solicitud("GET", "/tarifas")
    automovil = next(t["tarifa"] for t in r.json() if t["tipo_vehiculo"] == "AUTOMOVIL")
    if not automovil or automovil["valor"] != TARIFA_AUTOMOVIL:
        sys.exit("La tarifa de AUTOMOVIL no es la de las semillas: ejecuta la medición sobre una base limpia.")
    print(f"  Preparando {muestras} clientes y vehículos (no se mide)...")
    placas = preparar_vehiculos(admin, muestras)
    resultados: dict[str, list[float]] = {}

    def turno(i: int) -> Cliente:
        return clientes[i % SIMULTANEAS]

    def registrar(i: int) -> float:
        s, r = turno(i).solicitud("POST", "/pagos", json={
            "placa": placas[i], "meses": 1 + i % 3, "metodo": "EFECTIVO",
            "monto_confirmado": TARIFA_AUTOMOVIL * (1 + i % 3)})
        esperado(r, 201)
        return s
    resultados["Registrar pago"] = medir_en_paralelo(list(range(muestras)), registrar, SIMULTANEAS)

    estados = placas + ["ABC123", "STU852", "DEF456", "MNO654"]

    def estado(i: int) -> float:
        s, r = turno(i).solicitud("GET", f"/pagos/estado/{estados[i % len(estados)]}")
        esperado(r, 200)
        return s
    resultados["Consultar estado de la mensualidad"] = medir_en_paralelo(list(range(muestras)), estado, SIMULTANEAS)

    hoy = date.today().isoformat()
    filtros = [{"limit": 20}, {"placa": placas[0]}, {"metodo": "EFECTIVO", "limit": 20},
               {"estado": "VALIDO", "desde": hoy, "hasta": hoy, "limit": 20}]

    def consultar(i: int) -> float:
        s, r = turno(i).solicitud("GET", "/pagos", params=filtros[i % len(filtros)])
        esperado(r, 200)
        return s
    resultados["Consultar pagos"] = medir_en_paralelo(list(range(muestras)), consultar, SIMULTANEAS)

    inicio_mes = date.today().replace(day=1).isoformat()

    def recaudo(i: int) -> float:
        s, r = turno(i).solicitud("GET", "/reportes/recaudo", params={"desde": inicio_mes, "hasta": hoy})
        esperado(r, 200)
        return s
    resultados["Resumen de recaudo"] = medir_en_paralelo(list(range(muestras)), recaudo, SIMULTANEAS)
    return resultados


def escribir_reporte(filas: list[dict], datos_equipo: dict, args) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    with open(SALIDA / "rnf25.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    ahora = datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M")
    fallan = [f for f in filas if not f["cumple"]]
    lineas = [
        "# Evidencia de RNF-25: tiempo de respuesta medido de las operaciones de pagos",
        "",
        f"Medición automatizada con `scripts/medir_rnf25.py` el {ahora} (hora de Bogotá), contra el",
        f"sistema levantado con Docker Compose sobre una base limpia, a través de `{args.url}`.",
        "Percentil 95 por rango más cercano, con el mismo método de RNF-19 (el script reutiliza sus",
        "funciones). Los tiempos incluyen la red local, nginx, la API y PostgreSQL.",
        "",
        "## Equipo",
        "",
        "| Característica | Valor |",
        "| --- | --- |",
        *[f"| {k} | {v} |" for k, v in datos_equipo.items()],
        "",
        "## Resultados",
        "",
        "| Operación | Simultáneas | Muestras | Mediana (ms) | p95 (ms) | Máximo (ms) | Límite p95 (ms) | ¿Cumple? |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        *[f"| {f['operacion']} | {f['simultaneas']} | {f['muestras']} | {f['mediana_ms']} | {f['p95_ms']} | "
          f"{f['maximo_ms']} | {f['limite_ms']} | {'Sí' if f['cumple'] else '**NO CUMPLE**'} |" for f in filas],
        "",
    ]
    if fallan:
        lineas += [
            f"**Resultado global: RNF-25 NO SE CUMPLE por completo.** No cumple: "
            + ", ".join(f"{f['operacion']} (p95 {f['p95_ms']} ms > {f['limite_ms']} ms)" for f in fallan) + ".",
            "",
        ]
    else:
        lineas += ["**Resultado global: cumple RNF-25.**", ""]
    lineas += [
        "## Escenario",
        "",
        "- Cuatro sesiones abiertas a la vez (dos porterías y la administración) envían las solicitudes de",
        "  cada operación al mismo tiempo, en tandas de 4.",
        "- **Registrar pago:** cada solicitud cobra a un vehículo distinto (de 1 a 3 meses, en efectivo), con",
        "  el bloqueo de la fila del vehículo, la inserción del pago y de su periodo, y el comprobante. Antes",
        "  de medir se crean los clientes y vehículos; esa preparación no se mide.",
        "- **Consultar estado de la mensualidad:** vehículos de la medición y de las semillas (vigente, con",
        "  pago por adelantado, vencida y sin mensualidad).",
        "- **Consultar pagos:** con y sin filtros (placa, método, estado y rango de fechas).",
        "- **Resumen de recaudo:** el mes en curso.",
        "- Los pagos registrados no se pueden borrar (RNF-24): por eso la medición se ejecuta sobre una base",
        "  limpia que después se recrea.",
        "",
        "Datos crudos de esta ejecución: [`rnf25.csv`](rnf25.csv).",
        "",
    ]
    (SALIDA / "rnf25.md").write_text("\n".join(lineas), encoding="utf-8")
    inicio = lineas.index("## Resultados") + 2
    print("\n".join(lineas[inicio:inicio + 2 + len(filas)]))
    print(f"\nReporte: {SALIDA / 'rnf25.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:4200", help="Dirección del sistema (nginx o API)")
    parser.add_argument("--muestras", type=int, default=40, help="Solicitudes por operación (8 a 200)")
    args = parser.parse_args()
    if not 8 <= args.muestras <= 200:
        sys.exit("--muestras debe estar entre 8 y 200 (crea un cliente, un vehículo y un pago por muestra).")
    env = {**dotenv_values(RAIZ / ".env"), **os.environ}
    admin_usuario, admin_clave = env.get("ADMIN_USUARIO"), env.get("ADMIN_CONTRASENA")
    if not admin_usuario or not admin_clave:
        sys.exit("Faltan ADMIN_USUARIO y ADMIN_CONTRASENA en .env.")
    try:
        httpx.get(f"{args.url}/health", timeout=10).raise_for_status()
    except httpx.HTTPError:
        sys.exit(f"El sistema no responde en {args.url}. Levántalo con: docker compose up --build -d")

    print("Calentando (primeras solicitudes, no se cuentan)...")
    calentamiento = Cliente(args.url)
    calentamiento.ingresar(admin_usuario, admin_clave)
    for ruta in ("/pagos", "/pagos/estado/ABC123", "/tarifas"):
        calentamiento.solicitud("GET", ruta)
    print(f"Pagos con {SIMULTANEAS} solicitudes simultáneas ({args.muestras} por operación)...")
    resultados = escenario_pagos(args.url, admin_usuario, admin_clave, args.muestras)
    filas = [fila(nombre, tiempos, LIMITE, SIMULTANEAS) for nombre, tiempos in resultados.items()]
    escribir_reporte(filas, equipo(), args)


if __name__ == "__main__":
    main()
