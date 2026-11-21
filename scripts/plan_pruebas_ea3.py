"""Completa los resultados del plan de pruebas PP-03 (EA3) y llena el Excel (solo biblioteca estándar).

  python3 scripts/plan_pruebas_ea3.py completar
      Junta en docs/pruebas/evidencias-ea3/resultados.json lo que deja el programa de Playwright con
      las pruebas automatizadas (PA-03, CL-04 y PA-08) y los reportes de NF-01 (RNF-25) y NF-02
      (RNF-26); busca secretos en las evidencias (se detiene si encuentra alguno) y escribe
      docs/pruebas/reporte-ea3.md.

  python3 scripts/plan_pruebas_ea3.py excel COMMIT_EVIDENCIAS RUTA_DEL_EXCEL
      Llena Estado, Resultado real, Evidencia (enlace permanente al commit de las evidencias),
      Incidencia, Fecha de ejecución (Bogotá) y Responsable de la hoja Casos, y en la hoja Plan la
      versión probada y las fechas. Edita el XML del .xlsx (celdas de texto en línea): el resto del
      archivo (tabla, estilos, validación, formato condicional y fórmulas) queda igual. Antes guarda
      una copia del Excel con el sufijo _anterior.
"""
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_pruebas import BOGOTA, REPOSITORIO, RESPONSABLE, formula_n, secretos_de_env, serial_excel  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
EVIDENCIAS = RAIZ / "docs/pruebas/evidencias-ea3"
RESULTADOS = EVIDENCIAS / "resultados.json"
REPORTE = RAIZ / "docs/pruebas/reporte-ea3.md"

ORDEN_EXCEL = ([f"TA-{i:02d}" for i in range(1, 7)] + [f"CL-{i:02d}" for i in range(1, 7)] + [f"ME-{i:02d}" for i in range(1, 6)]
               + [f"PA-{i:02d}" for i in range(1, 14)] + [f"AN-{i:02d}" for i in range(1, 7)] + [f"RE-{i:02d}" for i in range(1, 5)]
               + ["PE-01", "NF-01", "NF-02"])

# Pruebas automatizadas (backend/tests) que respaldan cada caso.
PYTEST = {
    "PA-03": "tests/test_reglas_pagos.py: fin_de_periodo, encadenados, n_meses, inicio_de_periodo y tope_de_adelanto",
    "CL-04": "tests/test_clientes_postgres.py::test_dos_registros_simultaneos_del_mismo_documento_dejan_uno",
    "PA-08": "tests/test_pagos_concurrencia_postgres.py::test_dos_pagos_simultaneos_del_mismo_vehiculo_dan_periodos_consecutivos",
}


# ------------------------------------------------------------------ completar
def resultado_pytest(caso: str) -> tuple[bool, str, int]:
    archivo = EVIDENCIAS / f"{caso}_pytest.txt"
    if not archivo.exists():
        return False, "no se encontró la salida de pytest", 0
    texto = archivo.read_text(encoding="utf-8")
    resumen = next((l.strip("= ").strip() for l in reversed(texto.splitlines()) if re.search(r"\d+ (passed|failed|error)", l)), "")
    aprobadas = re.search(r"(\d+) passed", resumen)
    ok = bool(aprobadas) and not re.search(r"failed|error", resumen)
    return ok, resumen or "sin resumen", int(aprobadas.group(1)) if aprobadas else 0


def buscar_secretos() -> list[str]:
    hallazgos = []
    patrones = {"token JWT": re.compile(rb"eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}"),
                "hash bcrypt": re.compile(rb"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}"),
                "encabezado Authorization": re.compile(rb"Authorization|Bearer [\w-]")}
    valores = [v.encode() for v in secretos_de_env()]
    archivos = sorted(EVIDENCIAS.iterdir()) + [RAIZ / "docs/evidencias/rnf25.md", RAIZ / "docs/evidencias/rnf25.csv",
                                                RAIZ / "docs/evidencias/rnf26/reporte.md"]
    for archivo in archivos:
        datos = archivo.read_bytes()
        for valor in valores:
            if valor in datos:
                hallazgos.append(f"{archivo.name}: contiene un valor de .env")
        for nombre, patron in patrones.items():
            if patron.search(datos):
                hallazgos.append(f"{archivo.name}: contiene un {nombre}")
    return hallazgos


def ejecucion() -> dict:
    return json.loads((EVIDENCIAS / "ejecucion.json").read_text(encoding="utf-8"))


def completar() -> None:
    crudos = json.loads(RESULTADOS.read_text(encoding="utf-8"))
    resultados = {r["id"]: r for r in crudos if r["id"] != "PREPARACION"}
    preparacion = next((r for r in crudos if r["id"] == "PREPARACION"), None)
    ahora = datetime.now(timezone.utc).isoformat()
    commit = ejecucion()["commit_probado"]

    for caso in ("CL-04", "PA-08"):
        r = resultados.get(caso)
        if not r or f"{caso}_pytest.txt" in r["evidencias"]:   # ya completado (se puede volver a ejecutar)
            continue
        ok, resumen, _ = resultado_pytest(caso)
        r["evidencias"].append(f"{caso}_pytest.txt")
        r["resultado"] += f" Prueba automatizada de concurrencia ({PYTEST[caso].split('::')[1]}): {resumen}."
        if r["estado"] == "Aprobado" and not ok:
            r["estado"] = "Fallido"
            r["incidencia"] = f"INC-{caso}: la prueba automatizada de concurrencia no aprobó ({resumen})."

    ok, resumen, n = resultado_pytest("PA-03")
    resultados["PA-03"] = {
        "id": "PA-03", "estado": "Aprobado" if ok else "Fallido",
        "resultado": (f"Se ejecutaron las {n} pruebas de la regla de fechas ({PYTEST['PA-03']}). test_fin_de_periodo incluye los "
                      "tres ejemplos del documento: inicio 20-nov y 1 mes → fin 19-dic; inicio 31-ene y 1 mes → fin 28-feb; inicio "
                      f"15-dic y 2 meses → fin 14-feb (además de bisiestos, meses de 30 días y 6 meses). Resultado de pytest: {resumen}.")
        if ok else f"Las pruebas de la regla de fechas no aprobaron: {resumen}.",
        "incidencia": "" if ok else f"INC-PA-03: {resumen}", "evidencias": ["PA-03_pytest.txt"], "fecha": ahora,
    }

    rnf25 = (RAIZ / "docs/evidencias/rnf25.md").read_text(encoding="utf-8")
    filas25 = [l for l in rnf25.splitlines() if re.match(r"\| (Registrar pago|Consultar|Resumen)", l)]
    global25 = re.search(r"\*\*Resultado global:[^\n]*", rnf25).group(0).replace("**", "").strip()
    fecha25 = re.search(r"el (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(hora de Bogotá\)", rnf25).group(1)
    medidas = "; ".join(f"{c[0].lstrip('| ')}: p95 {c[4]} ms" for c in (l.split(" | ") for l in filas25))
    cumple25 = "NO SE CUMPLE" not in global25 and len(filas25) == 4
    resultados["NF-01"] = {
        "id": "NF-01", "estado": "Aprobado" if cumple25 else "Fallido",
        "resultado": (f"Medición con scripts/medir_rnf25.py el {fecha25} (Bogotá) sobre el commit {commit}, en un entorno Docker "
                      f"recién creado, con 4 solicitudes simultáneas: {medidas}. {global25} El reporte "
                      "docs/evidencias/rnf25.md registra la fecha, el equipo (CPU, memoria, sistema y versiones) y los datos crudos (rnf25.csv)."),
        "incidencia": "" if cumple25 else f"INC-NF-01: {global25}",
        "evidencias": ["../../evidencias/rnf25.md", "NF-01_medicion.txt", "../../evidencias/rnf25.csv"], "fecha": ahora,
    }

    rnf26 = (RAIZ / "docs/evidencias/rnf26/reporte.md").read_text(encoding="utf-8")
    commit26 = re.search(r"sobre el commit `(\w+)`", rnf26).group(1)
    filas26 = [l for l in rnf26.splitlines() if re.match(r"\| \d\d · ", l)]
    si = sum(l.count("Sí ·") for l in filas26)
    total26 = len(filas26) * 3
    cumple26 = si == total26 == 30 and commit26 == commit
    resultados["NF-02"] = {
        "id": "NF-02", "estado": "Aprobado" if cumple26 else "Fallido",
        "resultado": (f"Reporte docs/evidencias/rnf26/reporte.md, generado sobre el commit {commit26} con docker compose --profile e2e "
                      f"run --rm --build e2e-rnf26: {si} de {total26} pantallas (Tarifas, Clientes, Pagos con estado, resumen y "
                      "comprobante, anulación y Recaudo) funcionan en Google Chrome y Microsoft Edge estables para Linux y en el "
                      "Firefox de Playwright (motor Gecko); cada paso verifica su contenido antes de capturarlo. El reporte registra "
                      "la versión de cada navegador y el resultado por pantalla, con sus capturas y sin credenciales."),
        "incidencia": "" if cumple26 else f"INC-NF-02: {total26 - si} pantallas no funcionaron o el commit no coincide (ver el reporte).",
        "evidencias": ["../../evidencias/rnf26/reporte.md"], "fecha": ahora,
    }

    faltan = [c for c in ORDEN_EXCEL if c not in resultados]
    if faltan:
        sys.exit(f"Faltan resultados de: {', '.join(faltan)}")
    final = [resultados[c] for c in ORDEN_EXCEL]
    RESULTADOS.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if preparacion:
        (EVIDENCIAS / "PREPARACION_resultado.json").write_text(json.dumps(preparacion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hallazgos = buscar_secretos()
    if hallazgos:
        sys.exit("SE ENCONTRARON SECRETOS EN LAS EVIDENCIAS (no hacer commit):\n" + "\n".join(hallazgos))
    escribir_reporte(final, preparacion)
    cuenta = {e: sum(1 for r in final if r["estado"] == e) for e in ("Aprobado", "Fallido", "Bloqueado")}
    print(f"Casos: {len(final)} · Aprobados {cuenta['Aprobado']} · Fallidos {cuenta['Fallido']} · Bloqueados {cuenta['Bloqueado']}")
    print("Búsqueda de secretos en las evidencias: sin hallazgos")


def enlace_relativo(archivo: str) -> str:
    return f"evidencias-ea3/{archivo}" if not archivo.startswith("..") else archivo[3:]


def escribir_reporte(final: list[dict], preparacion: dict | None) -> None:
    e = ejecucion()
    vehiculos = json.loads((EVIDENCIAS / "vehiculos.json").read_text(encoding="utf-8"))
    lineas = ["# Ejecución del plan de pruebas PP-03 (EA3)", "",
              f"Generado por `scripts/ejecutar_plan_pruebas_ea3.sh` sobre el commit `{e['commit_probado']}`, entre {e['inicio']}",
              f"y {e['fin']} (Bogotá). Los resultados esperados son los de `Salinas_Hanna_EA3_Plan_Pruebas.xlsx` (hoja Casos);",
              "la columna Evidencia del Excel enlaza a estos archivos en el commit de las evidencias. Fechas en hora de Bogotá.", "",
              f"Base recién creada (solo semillas). Preparación: {preparacion['estado'] if preparacion else 'sin registro'} "
              "([PREPARACION_api.json](evidencias-ea3/PREPARACION_api.json), [PREPARACION_bd.txt](evidencias-ea3/PREPARACION_bd.txt)).",
              "Las cuentas, clientes, vehículos y pagos de prueba se crearon por la API; los periodos sin pago de V-VIG, V-VENC y",
              "V-FUT se insertaron por SQL (la API no permite crear un periodo que ya venció o que empezó antes de hoy).", "",
              f"## Vehículos de prueba (hoy = {vehiculos['hoy_bogota']})", "", "| Rol | Placa real | Tipo | Uso |", "|---|---|---|---|"]
    for rol, v in vehiculos["vehiculos"].items():
        lineas.append(f"| {rol} | {v['placa']} | {v['tipo']} | {v['uso']} |")
    cuenta = {k: sum(1 for r in final if r["estado"] == k) for k in ("Aprobado", "Fallido", "Bloqueado")}
    lineas += ["", f"**{len(final)} casos: {cuenta['Aprobado']} aprobados, {cuenta['Fallido']} fallidos y {cuenta['Bloqueado']} bloqueados.**", "",
               "| Caso | Estado | Fecha | Resultado real | Incidencia | Evidencia |", "|---|---|---|---|---|---|"]
    celda = lambda t: t.replace("|", "\\|").replace("\n", " ")
    for r in final:
        fecha = datetime.fromisoformat(r["fecha"]).astimezone(BOGOTA).strftime("%Y-%m-%d %H:%M")
        evid = ", ".join(f"[{Path(a).name}]({enlace_relativo(a)})" for a in r["evidencias"])
        lineas.append(f"| {r['id']} | {r['estado']} | {fecha} | {celda(r['resultado'])} | {celda(r['incidencia']) or '—'} | {evid} |")
    REPORTE.write_text("\n".join(lineas) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ Excel
def celda_texto(ref: str, estilo: str, texto: str) -> str:
    return f'<c r="{ref}"{estilo} t="inlineStr"><is><t xml:space="preserve">{escape(texto)}</t></is></c>'


def reemplazar(hoja: str, ref: str, nuevo) -> str:
    """Reemplaza la celda ref conservando su estilo. nuevo(estilo) devuelve el XML de la celda."""
    patron = re.compile(rf'<c r="{ref}"( s="\d+")?(?: t="\w+")?(?:/>|>.*?</c>)', re.S)
    actual = patron.search(hoja)
    if not actual:
        raise SystemExit(f"No se encontró la celda {ref}")
    return hoja[:actual.start()] + nuevo(actual.group(1) or "") + hoja[actual.end():]


def excel(commit_evidencias: str, ruta: str) -> None:
    xlsx = Path(ruta).expanduser()
    final = {r["id"]: r for r in json.loads(RESULTADOS.read_text(encoding="utf-8"))}
    e = ejecucion()
    copia = xlsx.with_name(xlsx.stem + "_anterior.xlsx")
    if not copia.exists():
        shutil.copy2(xlsx, copia)
    z = zipfile.ZipFile(xlsx)
    partes = {i.filename: z.read(i.filename) for i in z.infolist()}
    hoja = partes["xl/worksheets/sheet2.xml"].decode()
    rels = partes["xl/worksheets/_rels/sheet2.xml.rels"].decode()
    hipervinculos, relaciones, registros = [], [], []
    cuenta = {"Pendiente": 0, "Aprobado": 0, "Fallido": 0, "Bloqueado": 0, "No aplica": 0}
    for fila in range(6, 49):
        caso = re.sub(r"<[^>]+>", "", re.search(rf'<c r="A{fila}"[^>]*>(.*?)</c>', hoja, re.S).group(1)).strip()
        r = final[caso]
        principal = r["evidencias"][0]
        ruta_repo = (f"docs/pruebas/evidencias-ea3/{principal}" if not principal.startswith("..") else "docs/" + principal.replace("../../", ""))
        url = f"{REPOSITORIO}/blob/{commit_evidencias}/{ruta_repo}"
        texto_j = Path(principal).name + (f" (y {len(r['evidencias']) - 1} archivo(s) más del caso: "
                                          + ", ".join(Path(a).name for a in r["evidencias"][1:]) + ")" if len(r["evidencias"]) > 1 else "")
        hoja = reemplazar(hoja, f"H{fila}", lambda s: celda_texto(f"H{fila}", s, r["estado"]))
        hoja = reemplazar(hoja, f"I{fila}", lambda s: celda_texto(f"I{fila}", s, r["resultado"]))
        hoja = reemplazar(hoja, f"J{fila}", lambda s: celda_texto(f"J{fila}", s, texto_j))
        hoja = reemplazar(hoja, f"K{fila}", lambda s: celda_texto(f"K{fila}", s, r["incidencia"]) if r["incidencia"] else f'<c r="K{fila}"{s}/>')
        hoja = reemplazar(hoja, f"L{fila}", lambda s: f'<c r="L{fila}"{s}><v>{serial_excel(r["fecha"])}</v></c>')
        hoja = reemplazar(hoja, f"M{fila}", lambda s: celda_texto(f"M{fila}", s, RESPONSABLE))
        n = formula_n(r["estado"], r["resultado"], texto_j, r["incidencia"], True, RESPONSABLE)
        hoja = re.sub(rf'(<c r="N{fila}"[^>]*><f>.*?</f><v>)[^<]*(</v>)', lambda m: f"{m.group(1)}{escape(n)}{m.group(2)}", hoja, count=1, flags=re.S)
        rid = f"rIdEvidencia{fila}"
        hipervinculos.append(f'<hyperlink ref="J{fila}" r:id="{rid}"/>')
        relaciones.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                          f'Target="{escape(url)}" TargetMode="External"/>')
        cuenta[r["estado"]] += 1
        registros.append(n)
    hoja = re.sub(r"<hyperlinks[^>]*>.*?</hyperlinks>", "", hoja, flags=re.S)
    rels = re.sub(r'<Relationship Id="rIdEvidencia\d+"[^>]*/>', "", rels)
    hoja = hoja.replace("</dataValidations>", '</dataValidations><hyperlinks xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                        + "".join(hipervinculos) + "</hyperlinks>", 1)
    rels = rels.replace("</Relationships>", "".join(relaciones) + "</Relationships>")
    partes["xl/worksheets/sheet2.xml"] = hoja.encode()
    partes["xl/worksheets/_rels/sheet2.xml.rels"] = rels.encode()

    # Hoja Plan: versión probada (E11), fecha prevista (E13) y de cierre (E15), y valores calculados de las fórmulas.
    plan = partes["xl/worksheets/sheet1.xml"].decode()
    dia = int(serial_excel(datetime.now(timezone.utc).isoformat()))
    plan = reemplazar(plan, "E11", lambda s: celda_texto("E11", s, f"{e['commit_probado']} (rama main de {REPOSITORIO})"))
    plan = reemplazar(plan, "E13", lambda s: f'<c r="E13"{s}><v>{dia}</v></c>')
    plan = reemplazar(plan, "E15", lambda s: f'<c r="E15"{s}><v>{dia}</v></c>')
    ejecutados = cuenta["Aprobado"] + cuenta["Fallido"]
    incompletos = sum(1 for n in registros if n.startswith("Falt") or n == "Revisar estado")
    calculados = {"B10": cuenta["Pendiente"], "B11": cuenta["Aprobado"], "B12": cuenta["Fallido"], "B13": cuenta["Bloqueado"],
                  "B14": cuenta["No aplica"], "B15": ejecutados, "B16": round(ejecutados / 43, 6),
                  "B17": round(cuenta["Aprobado"] / ejecutados, 6) if ejecutados else "", "B18": incompletos}
    for ref, valor in calculados.items():
        plan = re.sub(rf'(<c r="{ref}"[^>]*><f>.*?</f><v>)[^<]*(</v>)', lambda m: f"{m.group(1)}{valor}{m.group(2)}", plan, count=1, flags=re.S)
    situacion = ("Ejecución pendiente" if cuenta["Pendiente"] else "Requiere correcciones o desbloqueo"
                 if cuenta["Fallido"] + cuenta["Bloqueado"] else "Completar registros de ejecución" if incompletos else "Listo para revisión docente")
    plan = re.sub(r'(<c r="E17"[^>]*><f>.*?</f><v>)[^<]*(</v>)', lambda m: f"{m.group(1)}{escape(situacion)}{m.group(2)}", plan, count=1, flags=re.S)
    partes["xl/worksheets/sheet1.xml"] = plan.encode()
    temporal = xlsx.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(temporal, "w") as zz:
        for info in z.infolist():
            zz.writestr(info, partes[info.filename], compress_type=info.compress_type)
    temporal.replace(xlsx)
    print(f"Excel lleno: {cuenta} · situación «{situacion}» · copia previa: {copia.name}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "completar":
        completar()
    elif len(sys.argv) == 4 and sys.argv[1] == "excel":
        excel(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
