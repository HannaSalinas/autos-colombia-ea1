"""Medición de RNF-19: tiempo de respuesta (percentil 95) del inicio de sesión y de la gestión.

Escenarios (documento de requerimientos, RNF-19):
  1. Gestión de cuentas y celdas con 4 solicitudes simultáneas (dos porterías y la administración):
     p95 <= 1 s por operación.
  2. Inicio de sesión sin simultaneidad (una persona al empezar su turno): p95 <= 1 s.
  3. Inicio de sesión con 4 ingresos simultáneos: p95 <= 2 s.
Además, como referencia (RNF-19 no le fija límite): crear cuenta sin simultaneidad, que es su uso
real, porque solo el Administrador crea cuentas.

Se ejecuta contra el sistema levantado con Docker (por defecto a través de nginx, como el usuario):
    docker compose down -v && docker compose up --build -d      # base limpia
    backend/.venv/bin/python scripts/medir_rnf19.py
    docker compose down -v && docker compose up --build -d      # volver a una base limpia

Nada se borra en el sistema (D4): la medición deja cuentas "rnf19.*" y algunas celdas nuevas. Por
eso se ejecuta sobre una base limpia y después se recrea. Lee ADMIN_USUARIO y ADMIN_CONTRASENA de
.env (nunca los escribe en el reporte). Genera docs/evidencias/rnf19.md y docs/evidencias/rnf19.csv.
"""

import argparse
import csv
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "evidencias"
LIMITE_GESTION = 1.0
LIMITE_LOGIN_SOLO = 1.0
LIMITE_LOGIN_SIMULTANEO = 2.0
SIMULTANEAS = 4
CLAVE_MEDICION = "medicion2026"   # contraseña de las cuentas que crea la medición (no es un secreto)


def p95(muestras: list[float]) -> float:
    """Percentil 95 por rango más cercano: el valor que deja al 95 % de las muestras por debajo o igual."""
    ordenadas = sorted(muestras)
    return ordenadas[max(0, math.ceil(0.95 * len(ordenadas)) - 1)]


class Cliente:
    def __init__(self, url: str) -> None:
        self.http = httpx.Client(base_url=url, timeout=30)
        self.token = ""

    def solicitud(self, metodo: str, ruta: str, **kwargs) -> tuple[float, httpx.Response]:
        encabezados = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        inicio = time.perf_counter()
        respuesta = self.http.request(metodo, ruta, headers=encabezados, **kwargs)
        return time.perf_counter() - inicio, respuesta

    def ingresar(self, usuario: str, contrasena: str) -> float:
        segundos, respuesta = self.solicitud("POST", "/auth/login", json={"usuario": usuario, "contrasena": contrasena})
        if respuesta.status_code != 200:
            sys.exit(f"No se pudo ingresar como {usuario} (HTTP {respuesta.status_code}). Revisa .env y la base.")
        self.token = respuesta.json()["token"]
        return segundos


def esperado(respuesta: httpx.Response, *codigos: int) -> None:
    if respuesta.status_code not in codigos:
        sys.exit(f"Respuesta inesperada {respuesta.status_code} en {respuesta.request.method} "
                 f"{respuesta.request.url.path}: {respuesta.text[:200]}")


def codigos_libres(admin: Cliente, tipo: str, cantidad: int) -> list[str]:
    _, r = admin.solicitud("GET", "/celdas", params={"tipo": tipo, "limit": 100})
    usados = {c["codigo"] for c in r.json()["items"]}
    prefijo = "C" if tipo == "CARRO" else "M"
    libres = [c for c in (f"{prefijo}{n:02d}" for n in range(99, 0, -1)) if c not in usados]
    if len(libres) < cantidad:
        sys.exit(f"No quedan {cantidad} códigos libres de tipo {tipo}: ejecuta la medición sobre una base limpia.")
    return libres[:cantidad]


def medir_en_paralelo(tareas: list, funcion, hilos: int) -> list[float]:
    """Ejecuta funcion(tarea) con `hilos` solicitudes simultáneas y devuelve los tiempos."""
    with ThreadPoolExecutor(max_workers=hilos) as pool:
        return list(pool.map(funcion, tareas))


def escenario_gestion(url: str, admin_usuario: str, admin_clave: str, muestras: int, sufijo: str) -> dict:
    """Cada operación de gestión se mide con 4 solicitudes simultáneas, cada una con su propia sesión."""
    clientes = [Cliente(url) for _ in range(SIMULTANEAS)]
    for c in clientes:
        c.ingresar(admin_usuario, admin_clave)
    admin = clientes[0]
    resultados: dict[str, list[float]] = {}
    n = 0

    def turno(i: int) -> Cliente:
        return clientes[i % SIMULTANEAS]

    # --- Cuentas ---
    usuarios = [f"rnf19.{sufijo}.{i}" for i in range(muestras)]

    def crear_cuenta(i: int) -> float:
        s, r = turno(i).solicitud("POST", "/cuentas", json={
            "nombre": f"Medicion RNF19 {i}", "nombre_usuario": usuarios[i], "contrasena": CLAVE_MEDICION,
            "rol": "OPERADOR"})
        esperado(r, 201)
        return s
    resultados["Crear cuenta"] = medir_en_paralelo(list(range(muestras)), crear_cuenta, SIMULTANEAS)

    _, r = admin.solicitud("GET", "/cuentas", params={"buscar": f"rnf19.{sufijo}.", "limit": 100})
    ids_cuentas = [c["id"] for c in r.json()["items"]]

    def listar_cuentas(i: int) -> float:
        s, r = turno(i).solicitud("GET", "/cuentas", params={"buscar": "a" if i % 2 else "", "limit": 20})
        esperado(r, 200)
        return s
    resultados["Listar y buscar cuentas"] = medir_en_paralelo(list(range(muestras)), listar_cuentas, SIMULTANEAS)

    def detalle_cuenta(i: int) -> float:
        s, r = turno(i).solicitud("GET", f"/cuentas/{ids_cuentas[i % len(ids_cuentas)]}")
        esperado(r, 200)
        return s
    resultados["Detalle de cuenta"] = medir_en_paralelo(list(range(muestras)), detalle_cuenta, SIMULTANEAS)

    def desactivar(i: int) -> float:
        s, r = turno(i).solicitud("POST", f"/cuentas/{ids_cuentas[i]}/desactivar")
        esperado(r, 200)
        return s
    resultados["Desactivar cuenta"] = medir_en_paralelo(list(range(len(ids_cuentas))), desactivar, SIMULTANEAS)

    def reactivar(i: int) -> float:
        s, r = turno(i).solicitud("POST", f"/cuentas/{ids_cuentas[i]}/reactivar")
        esperado(r, 200)
        return s
    resultados["Reactivar cuenta"] = medir_en_paralelo(list(range(len(ids_cuentas))), reactivar, SIMULTANEAS)

    # --- Celdas ---
    codigos = codigos_libres(admin, "MOTO", muestras)

    def crear_celda(i: int) -> float:
        s, r = turno(i).solicitud("POST", "/celdas", json={"codigo": codigos[i], "tipo": "MOTO",
                                                          "ubicacion": "Medición RNF-19"})
        esperado(r, 201)
        return s
    resultados["Crear celda"] = medir_en_paralelo(list(range(muestras)), crear_celda, SIMULTANEAS)

    _, r = admin.solicitud("GET", "/celdas", params={"buscar": "M", "limit": 100})
    ids_celdas = [c["id"] for c in r.json()["items"] if c["codigo"] in codigos]

    def listar_celdas(i: int) -> float:
        params = [{"limit": 20}, {"estado": "LIBRE", "limit": 20}, {"tipo": "CARRO", "limit": 20}, {"buscar": "C0"}]
        s, r = turno(i).solicitud("GET", "/celdas", params=params[i % 4])
        esperado(r, 200)
        return s
    resultados["Listar y filtrar celdas"] = medir_en_paralelo(list(range(muestras)), listar_celdas, SIMULTANEAS)

    def editar_celda(i: int) -> float:
        s, r = turno(i).solicitud("PATCH", f"/celdas/{ids_celdas[i]}", json={"ubicacion": f"Zona {i}"})
        esperado(r, 200)
        return s
    resultados["Editar celda"] = medir_en_paralelo(list(range(len(ids_celdas))), editar_celda, SIMULTANEAS)

    def inhabilitar(i: int) -> float:
        s, r = turno(i).solicitud("POST", f"/celdas/{ids_celdas[i]}/inhabilitar")
        esperado(r, 200)
        return s
    resultados["Inhabilitar celda"] = medir_en_paralelo(list(range(len(ids_celdas))), inhabilitar, SIMULTANEAS)

    def rehabilitar(i: int) -> float:
        s, r = turno(i).solicitud("POST", f"/celdas/{ids_celdas[i]}/rehabilitar")
        esperado(r, 200)
        return s
    resultados["Rehabilitar celda"] = medir_en_paralelo(list(range(len(ids_celdas))), rehabilitar, SIMULTANEAS)
    return resultados


def escenario_crear_cuenta_solo(url: str, admin_usuario: str, admin_clave: str, muestras: int,
                                sufijo: str) -> list[float]:
    """Referencia: crear cuenta de una en una (el Administrador es quien crea las cuentas)."""
    admin = Cliente(url)
    admin.ingresar(admin_usuario, admin_clave)

    def crear(i: int) -> float:
        s, r = admin.solicitud("POST", "/cuentas", json={
            "nombre": f"Medicion RNF19 sola {i}", "nombre_usuario": f"rnf19.{sufijo}.solo.{i}",
            "contrasena": CLAVE_MEDICION, "rol": "OPERADOR"})
        esperado(r, 201)
        return s
    return medir_en_paralelo(list(range(muestras)), crear, 1)


def escenario_login(url: str, usuario: str, muestras: int, hilos: int) -> list[float]:
    def ingresar(_: int) -> float:
        return Cliente(url).ingresar(usuario, CLAVE_MEDICION)
    return medir_en_paralelo(list(range(muestras)), ingresar, hilos)


def equipo() -> dict[str, str]:
    def leer(comando: list[str]) -> str:
        try:
            return subprocess.run(comando, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return "no disponible"
    cpu = next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines()
                if l.startswith("model name")), platform.processor() or "no disponible")
    memoria_kb = next((int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines()
                       if l.startswith("MemTotal")), 0)
    return {
        "Procesador": cpu,
        "Núcleos lógicos": str(os.cpu_count()),
        "Memoria RAM": f"{memoria_kb / 1024 / 1024:.1f} GiB",
        "Sistema operativo": f"{platform.system()} {platform.release()}",
        "Docker": leer(["docker", "--version"]),
        "Docker Compose": leer(["docker", "compose", "version", "--short"]),
        "Commit medido": leer(["git", "-C", str(RAIZ), "rev-parse", "--short", "HEAD"]),
    }


def fila(nombre: str, tiempos: list[float], limite: float | None, simultaneas: int) -> dict:
    """limite None = fila de referencia: RNF-19 no le fija un límite."""
    valor = p95(tiempos)
    return {"operacion": nombre, "simultaneas": simultaneas, "muestras": len(tiempos),
            "mediana_ms": round(statistics.median(tiempos) * 1000), "p95_ms": round(valor * 1000),
            "maximo_ms": round(max(tiempos) * 1000),
            "limite_ms": round(limite * 1000) if limite is not None else "",
            "cumple": "" if limite is None else valor <= limite}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:4200", help="Dirección del sistema (nginx o API)")
    parser.add_argument("--muestras", type=int, default=40, help="Solicitudes por operación (máx. 80)")
    parser.add_argument("--muestras-login", type=int, default=30, help="Ingresos por escenario de login")
    args = parser.parse_args()
    if not 8 <= args.muestras <= 80:
        sys.exit("--muestras debe estar entre 8 y 80 (crea una celda y una cuenta por muestra).")
    env = {**dotenv_values(RAIZ / ".env"), **os.environ}
    admin_usuario, admin_clave = env.get("ADMIN_USUARIO"), env.get("ADMIN_CONTRASENA")
    if not admin_usuario or not admin_clave:
        sys.exit("Faltan ADMIN_USUARIO y ADMIN_CONTRASENA en .env.")
    try:
        httpx.get(f"{args.url}/health", timeout=10).raise_for_status()
    except httpx.HTTPError:
        sys.exit(f"El sistema no responde en {args.url}. Levántalo con: docker compose up --build -d")

    sufijo = datetime.now().strftime("%H%M%S")
    print("Calentando (primeras solicitudes, no se cuentan)...")
    calentamiento = Cliente(args.url)
    calentamiento.ingresar(admin_usuario, admin_clave)
    for ruta in ("/cuentas", "/celdas", "/reportes/ocupacion"):
        calentamiento.solicitud("GET", ruta)

    print(f"Escenario 1: gestión con {SIMULTANEAS} solicitudes simultáneas ({args.muestras} por operación)...")
    gestion = escenario_gestion(args.url, admin_usuario, admin_clave, args.muestras, sufijo)
    usuario_login = f"rnf19.{sufijo}.0"   # una de las cuentas creadas por la medición
    print(f"Referencia: crear cuenta sin simultaneidad ({args.muestras_login} cuentas)...")
    crear_solo = escenario_crear_cuenta_solo(args.url, admin_usuario, admin_clave, args.muestras_login, sufijo)
    print(f"Escenario 2: inicio de sesión sin simultaneidad ({args.muestras_login} ingresos)...")
    login_solo = escenario_login(args.url, usuario_login, args.muestras_login, 1)
    print(f"Escenario 3: inicio de sesión con {SIMULTANEAS} simultáneos ({args.muestras_login} ingresos)...")
    login_simultaneo = escenario_login(args.url, usuario_login, args.muestras_login, SIMULTANEAS)

    filas = [fila(nombre, tiempos, LIMITE_GESTION, SIMULTANEAS) for nombre, tiempos in gestion.items()]
    filas.append(fila("Crear cuenta (sin simultaneidad, referencia)", crear_solo, None, 1))
    filas.append(fila("Iniciar sesión (sin simultaneidad)", login_solo, LIMITE_LOGIN_SOLO, 1))
    filas.append(fila("Iniciar sesión (4 simultáneos)", login_simultaneo, LIMITE_LOGIN_SIMULTANEO, SIMULTANEAS))
    escribir_reporte(filas, equipo(), args)


# Mediciones anteriores, conservadas como evidencia de cómo se llegó al resultado final.
HISTORIAL = """## Historial de la medición

Primera ejecución (10-nov-2026, commit `1eed2db`, mismo equipo y base limpia): fallaban dos
operaciones con 4 simultáneas.

| Operación (4 simultáneas) | p95 primera ejecución | Causa | Corrección | p95 después |
| --- | ---: | --- | --- | ---: |
| Desactivar cuenta | 1257 ms | Cada desactivación bloqueaba las filas de **todos** los administradores, aun cuando la cuenta era de un Operador: las 4 solicitudes se ponían en fila (una sola tarda unos 180 ms). Además, el bloqueo `FOR UPDATE` hacía esperar al INSERT de la auditoría, que referencia al actor con una llave foránea. | Commit `0aac065`: ese bloqueo solo se toma al desactivar a un administrador (que es lo que exige la regla del último administrador), y con `FOR NO KEY UPDATE`, que no frena a quien solo referencia la fila. | 404 ms (segunda ejecución) |
| Crear cuenta | 1219 ms | bcrypt de costo 12 (RNF-13) | Ninguna: el costo no se reduce por seguridad | 1290 ms (segunda ejecución) |

La segunda ejecución midió el código de `0aac065` antes de confirmarlo; por eso se repitió la
medición con el código ya versionado (resultados de arriba). En la segunda ejecución, crear
cuenta sin simultaneidad, medido aparte con el mismo método (20 muestras), dio p95 579 ms.
"""


def escribir_reporte(filas: list[dict], datos_equipo: dict, args) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    with open(SALIDA / "rnf19.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    ahora = datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M")
    evaluadas = [f for f in filas if f["cumple"] != ""]
    fallan = [f for f in evaluadas if not f["cumple"]]
    por_nombre = {f["operacion"]: f for f in filas}

    def veredicto(f: dict) -> str:
        return "Referencia" if f["cumple"] == "" else ("Sí" if f["cumple"] else "**NO CUMPLE**")

    lineas = [
        "# Evidencia de RNF-19: tiempo de respuesta medido",
        "",
        f"Medición automatizada con `scripts/medir_rnf19.py` el {ahora} (hora de Bogotá), contra el",
        f"sistema levantado con Docker Compose sobre una base limpia, a través de `{args.url}`.",
        "Percentil 95 por rango más cercano. Los tiempos incluyen la red local, nginx, la API y PostgreSQL.",
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
          f"{f['maximo_ms']} | {f['limite_ms'] or '—'} | {veredicto(f)} |" for f in filas],
        "",
    ]
    if fallan:
        lineas += [
            f"**Resultado global: RNF-19 NO SE CUMPLE por completo.** Cumplen {len(evaluadas) - len(fallan)} de "
            f"{len(evaluadas)} mediciones; no cumple: "
            + ", ".join(f"{f['operacion']} con {f['simultaneas']} simultáneas (p95 {f['p95_ms']} ms > "
                        f"{f['limite_ms']} ms)" for f in fallan) + ".",
            "",
        ]
    else:
        lineas += ["**Resultado global: cumple RNF-19.**", ""]
    crear = por_nombre.get("Crear cuenta")
    crear_solo = por_nombre.get("Crear cuenta (sin simultaneidad, referencia)")
    if crear and crear_solo:
        lineas += [
            "## Crear cuenta con 4 simultáneas",
            "",
            f"- **Resultado:** p95 {crear['p95_ms']} ms frente a un límite de 1000 ms"
            + (" (**no cumple**)." if not crear["cumple"] else " (cumple)."),
            "- **Causa:** crear una cuenta calcula el hash bcrypt de la contraseña con costo 12 (RNF-13), unos",
            "  0,5 s de CPU por cuenta en este equipo. Con 4 creaciones a la vez en 2 núcleos, cada una espera",
            "  a las demás. El costo **no se reduce**: es la protección de las contraseñas frente a ataques de",
            "  fuerza bruta.",
            "- **Contexto:** solo el Administrador crea cuentas, así que su uso real no es simultáneo. De una en",
            f"  una, crear cuenta tarda p95 {crear_solo['p95_ms']} ms (fila de referencia de la tabla).",
            "",
        ]
    lineas += [
        "## Escenarios y lectura de los resultados",
        "",
        "- Gestión de cuentas y celdas con 4 solicitudes simultáneas (dos porterías y la administración):",
        "  p95 ≤ 1 s por operación. Inicio de sesión sin simultaneidad: p95 ≤ 1 s. Inicio de sesión con 4",
        "  ingresos simultáneos: p95 ≤ 2 s. El inicio de sesión también usa bcrypt y es lento a propósito.",
        "- Las escrituras tardan unos 200 ms aun de una en una en este equipo (procesador de bajo consumo y",
        "  confirmación en disco de PostgreSQL); con 4 simultáneas se reparten los 2 núcleos.",
        "- Entre ejecuciones hay una variación de unos ±200 ms en las operaciones con bcrypt (por ejemplo,",
        "  el inicio de sesión con 4 simultáneos dio 952 ms en una ejecución y 1184 ms en otra). En un",
        "  equipo con más núcleos los tiempos con simultaneidad bajan, pero la causa no cambia.",
        "",
        HISTORIAL,
        "Datos crudos de esta ejecución: [`rnf19.csv`](rnf19.csv).",
        "",
    ]
    (SALIDA / "rnf19.md").write_text("\n".join(lineas), encoding="utf-8")
    inicio_tabla = lineas.index("## Resultados") + 2
    print("\n".join(lineas[inicio_tabla:inicio_tabla + 3 + len(filas)]))
    print(f"\nReporte: {SALIDA / 'rnf19.md'}")


if __name__ == "__main__":
    main()
