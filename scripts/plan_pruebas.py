"""Completa los resultados del plan de pruebas PP-02 y llena el Excel (solo biblioteca estándar).

  python3 scripts/plan_pruebas.py completar
      Junta en docs/pruebas/evidencias/resultados.json lo que deja el programa de Playwright con las
      pruebas de concurrencia (pytest) y los reportes de NF-01 y NF-02; busca secretos en las
      evidencias (se detiene si encuentra alguno) y escribe docs/pruebas/reporte.md.

  python3 scripts/plan_pruebas.py excel COMMIT_EVIDENCIAS RUTA_DEL_EXCEL
      Llena Estado, Resultado real, Evidencia (enlace permanente al commit de las evidencias),
      Incidencia, Fecha de ejecución (Bogotá) y Responsable de la hoja Casos, y en la hoja Plan la
      versión probada y la fecha de cierre. Edita el XML del .xlsx: el resto del archivo (tabla,
      estilos, validación, formato condicional y fórmulas) queda igual, byte a byte.
"""
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
EVIDENCIAS = RAIZ / "docs/pruebas/evidencias"
RESULTADOS = EVIDENCIAS / "resultados.json"
REPOSITORIO = "https://github.com/HannaSalinas/autos-colombia-ea1"
BOGOTA = ZoneInfo("America/Bogota")
RESPONSABLE = "Hanna Salinas"

ORDEN_EXCEL = [f"US-{i:02d}" for i in range(1, 21)] + [f"PE-{i:02d}" for i in range(1, 6)] + \
    [f"CE-{i:02d}" for i in range(1, 18)] + ["NF-01", "NF-02"]

# Pruebas automatizadas de concurrencia (backend/tests) que respaldan cada caso.
PYTEST = {
    "US-13": ["tests/test_cuentas_postgres.py::test_dos_creaciones_simultaneas_del_mismo_usuario_dejan_una_cuenta"],
    "US-19": ["tests/test_cuentas_postgres.py::test_dos_administradores_que_se_desactivan_mutuamente_no_dejan_cero"],
    "CE-13": ["tests/test_gestion_celdas_postgres.py::test_dos_creaciones_simultaneas_del_mismo_codigo_dejan_una_celda"],
    "CE-17": ["tests/test_gestion_celdas_postgres.py::test_inhabilitar_espera_a_la_entrada_en_curso_y_ve_la_celda_ocupada",
              "tests/test_gestion_celdas_postgres.py::test_la_entrada_salta_la_celda_que_se_esta_inhabilitando"],
}


# ------------------------------------------------------------------ completar
def resultado_pytest(caso: str) -> tuple[bool, str]:
    archivo = EVIDENCIAS / f"{caso}_pytest.txt"
    if not archivo.exists():
        return False, "no se encontró la salida de pytest"
    texto = archivo.read_text(encoding="utf-8")
    resumen = next((l.strip("= ").strip() for l in reversed(texto.splitlines()) if re.search(r"\d+ (passed|failed|error)", l)), "")
    esperadas = len(PYTEST[caso])
    ok = bool(re.search(rf"\b{esperadas} passed\b", resumen)) and not re.search(r"failed|error", resumen)
    return ok, resumen or "sin resumen"


def secretos_de_env() -> list[str]:
    valores = []
    for linea in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*)\s*$", linea)
        if m and re.search(r"CONTRASENA|PASSWORD|SECRETO|SECRET|TOKEN|KEY", m.group(1)) and len(m.group(2).strip("'\"")) >= 4:
            valores.append(m.group(2).strip("'\""))
    return valores


def buscar_secretos() -> list[str]:
    hallazgos = []
    patrones = {"token JWT": re.compile(rb"eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}"),
                "hash bcrypt": re.compile(rb"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}"),
                "encabezado Authorization": re.compile(rb"Authorization|Bearer [\w-]")}
    valores = [v.encode() for v in secretos_de_env()]
    for archivo in sorted(EVIDENCIAS.iterdir()):
        datos = archivo.read_bytes()
        for valor in valores:
            if valor in datos:
                hallazgos.append(f"{archivo.name}: contiene un valor de .env")
        for nombre, patron in patrones.items():
            if patron.search(datos):
                hallazgos.append(f"{archivo.name}: contiene un {nombre}")
    return hallazgos


def completar() -> None:
    resultados = {r["id"]: r for r in json.loads(RESULTADOS.read_text(encoding="utf-8"))}
    ahora = datetime.now(timezone.utc).isoformat()
    for caso in ("US-13", "US-19", "CE-13"):
        r = resultados.get(caso)
        if not r or f"{caso}_pytest.txt" in r["evidencias"]:   # ya completado (se puede volver a ejecutar)
            continue
        ok, resumen = resultado_pytest(caso)
        r["evidencias"].append(f"{caso}_pytest.txt")
        r["resultado"] += f" Prueba automatizada ({', '.join(t.split('::')[1] for t in PYTEST[caso])}): {resumen}."
        if r["estado"] == "Aprobado" and not ok:
            r["estado"] = "Fallido"
            r["incidencia"] = f"INC-{caso}: la prueba automatizada de concurrencia no aprobó ({resumen})."
    ok, resumen = resultado_pytest("CE-17")
    resultados["CE-17"] = {
        "id": "CE-17", "estado": "Aprobado" if ok else "Fallido",
        "resultado": ("Variante A (test_inhabilitar_espera_a_la_entrada_en_curso_y_ve_la_celda_ocupada): la inhabilitación "
                      "espera a que termine la entrada que tiene la celda bloqueada y responde 409. Variante B "
                      "(test_la_entrada_salta_la_celda_que_se_esta_inhabilitando): mientras la inhabilitación sostiene el "
                      "bloqueo, la entrada recibe otra celda. Nunca queda un vehículo en una celda inhabilitada. "
                      f"Resultado de pytest: {resumen}.") if ok else f"Las pruebas automatizadas no aprobaron: {resumen}.",
        "incidencia": "" if ok else f"INC-CE-17: {resumen}",
        "evidencias": ["CE-17_pytest.txt"], "fecha": ahora,
    }
    rnf19 = (RAIZ / "docs/evidencias/rnf19.md").read_text(encoding="utf-8")
    commit19 = re.search(r"Commit medido \| (\w+)", rnf19).group(1)
    global19 = re.search(r"\*\*Resultado global:[^\n]*", rnf19).group(0).replace("**", "")
    resultados["NF-01"] = {
        "id": "NF-01", "estado": "Fallido",
        "resultado": (f"Reporte docs/evidencias/rnf19.md (commit medido {commit19}, entorno Docker recién creado, con equipo, "
                      f"CPU y memoria). {global19.strip()} Las demás mediciones cumplen: gestión p95 ≤ 1000 ms con 4 "
                      "simultáneas; login p95 ≤ 1000 ms sin simultaneidad y ≤ 2000 ms con 4 simultáneos."),
        "incidencia": ("INC-NF-01: «Crear cuenta» con 4 solicitudes simultáneas tiene p95 de 1215 ms (> 1000 ms). Causa: "
                       "cada creación calcula el hash bcrypt de costo 12 (unos 0,54 s por cálculo) y el equipo de prueba "
                       "tiene 2 núcleos, así que las 4 solicitudes se ponen en fila. Decisión B: se reporta el "
                       "incumplimiento sin bajar el costo de bcrypt (RNF-13 exige costo 12 o más)."),
        "evidencias": ["../../evidencias/rnf19.md"], "fecha": ahora,
    }
    rnf20 = (RAIZ / "docs/evidencias/rnf20/reporte.md").read_text(encoding="utf-8")
    commit20 = re.search(r"sobre el commit `(\w+)`", rnf20).group(1)
    filas = [l for l in rnf20.splitlines() if re.match(r"\| \d\d · ", l)]
    si = sum(l.count("Sí ·") for l in filas)
    total = len(filas) * 3
    resultados["NF-02"] = {
        "id": "NF-02", "estado": "Aprobado" if si == total == 30 else "Fallido",
        "resultado": (f"Reporte docs/evidencias/rnf20/reporte.md, generado sobre el commit {commit20} con "
                      f"docker compose --profile e2e run --rm --build e2e: {si} de {total} pantallas funcionan en Google "
                      "Chrome y Microsoft Edge estables para Linux y en el Firefox de Playwright (motor Gecko); cada paso "
                      "verifica su contenido. El reporte registra la versión de cada navegador y sus capturas, sin credenciales."),
        "incidencia": "" if si == total == 30 else f"INC-NF-02: {total - si} pantallas no funcionaron (ver el reporte).",
        "evidencias": ["../../evidencias/rnf20/reporte.md"], "fecha": ahora,
    }
    final = [resultados[c] for c in ORDEN_EXCEL if c in resultados]
    faltan = [c for c in ORDEN_EXCEL if c not in resultados]
    if faltan:
        sys.exit(f"Faltan resultados de: {', '.join(faltan)}")
    RESULTADOS.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hallazgos = buscar_secretos()
    if hallazgos:
        sys.exit("SE ENCONTRARON SECRETOS EN LAS EVIDENCIAS (no hacer commit):\n" + "\n".join(hallazgos))
    escribir_reporte(final)
    cuenta = {e: sum(1 for r in final if r["estado"] == e) for e in ("Aprobado", "Fallido", "Bloqueado")}
    print(f"Casos: {len(final)} · Aprobados {cuenta['Aprobado']} · Fallidos {cuenta['Fallido']} · Bloqueados {cuenta['Bloqueado']}")
    print("Búsqueda de secretos en las evidencias: sin hallazgos")


def ejecucion() -> dict:
    return json.loads((EVIDENCIAS / "ejecucion.json").read_text(encoding="utf-8"))


def enlace_relativo(archivo: str) -> str:
    return f"evidencias/{archivo}" if not archivo.startswith("..") else archivo[3:]


def escribir_reporte(final: list[dict]) -> None:
    lineas = ["# Ejecución del plan de pruebas PP-02 (EA2)", "",
              f"Generado por `scripts/ejecutar_plan_pruebas.sh` (ver el README) sobre el commit `{ejecucion()['commit_probado']}`,",
              f"entre {ejecucion()['inicio']} y {ejecucion()['fin']} (Bogotá). Los resultados esperados son los de",
              "`Salinas_Hanna_EA2_Plan_Pruebas.xlsx` (hoja Casos); la columna Evidencia del Excel enlaza a estos archivos",
              "en el commit de las evidencias. Fechas en hora de Bogotá.", ""]
    cuenta = {e: sum(1 for r in final if r["estado"] == e) for e in ("Aprobado", "Fallido", "Bloqueado")}
    lineas += [f"**{len(final)} casos: {cuenta['Aprobado']} aprobados, {cuenta['Fallido']} fallidos y {cuenta['Bloqueado']} bloqueados.**", "",
               "| Caso | Estado | Fecha | Resultado real | Incidencia | Evidencia |", "|---|---|---|---|---|---|"]
    for r in final:
        fecha = datetime.fromisoformat(r["fecha"]).astimezone(BOGOTA).strftime("%Y-%m-%d %H:%M")
        evid = ", ".join(f"[{Path(a).name}]({enlace_relativo(a)})" for a in r["evidencias"])
        celda = lambda t: t.replace("|", "\\|").replace("\n", " ")
        lineas.append(f"| {r['id']} | {r['estado']} | {fecha} | {celda(r['resultado'])} | {celda(r['incidencia']) or '—'} | {evid} |")
    (RAIZ / "docs/pruebas/reporte.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ Excel
def serial_excel(iso: str) -> float:
    local = datetime.fromisoformat(iso).astimezone(BOGOTA).replace(tzinfo=None)
    return round((local - datetime(1899, 12, 30)).total_seconds() / 86400, 6)


def formula_n(estado: str, i: str, j: str, k: str, l_num: bool, m: str) -> str:
    """Valor de la fórmula de la columna N (Registro de ejecución), igual que en el Excel."""
    if estado == "Pendiente":
        return "Pendiente"
    if estado not in ("Aprobado", "Fallido", "Bloqueado", "No aplica"):
        return "Revisar estado"
    if not i or not m or not l_num:
        return "Faltan datos"
    if estado == "No aplica":
        return "Justificación registrada"
    if not j:
        return "Falta evidencia"
    if estado in ("Fallido", "Bloqueado") and not k:
        return "Falta incidencia"
    return "Completo"


def excel(commit_evidencias: str, ruta: str) -> None:
    xlsx = Path(ruta).expanduser()
    final = {r["id"]: r for r in json.loads(RESULTADOS.read_text(encoding="utf-8"))}
    commit_probado = json.loads((EVIDENCIAS / "ejecucion.json").read_text(encoding="utf-8"))["commit_probado"]
    copia = xlsx.with_name(xlsx.stem + "_antes_de_ejecutar.xlsx")
    if not copia.exists():
        shutil.copy2(xlsx, copia)
    z = zipfile.ZipFile(xlsx)
    partes = {i.filename: z.read(i.filename) for i in z.infolist()}
    sst = partes["xl/sharedStrings.xml"].decode()
    items = re.findall(r"<si>.*?</si>", sst, re.S)
    nuevas: list[str] = []

    def cadena(texto: str) -> int:
        nuevas.append(f'<si><t xml:space="preserve">{escape(texto)}</t></si>')
        return len(items) + len(nuevas) - 1

    hoja = partes["xl/worksheets/sheet2.xml"].decode()
    rels = partes["xl/worksheets/_rels/sheet2.xml.rels"].decode()
    hipervinculos, relaciones = [], []
    cuenta = {"Pendiente": 0, "Aprobado": 0, "Fallido": 0, "Bloqueado": 0, "No aplica": 0}
    registros = []
    for fila in range(6, 50):
        m = re.search(rf'<c r="A{fila}"[^>]*t="s"[^>]*><v>(\d+)</v>', hoja)
        caso = re.sub(r"<[^>]+>", "", items[int(m.group(1))])
        r = final[caso]
        principal = r["evidencias"][0]
        ruta_repo = (f"docs/pruebas/evidencias/{principal}" if not principal.startswith("..")
                     else "docs/" + principal.replace("../../", ""))
        url = f"{REPOSITORIO}/blob/{commit_evidencias}/{ruta_repo}"
        texto_j = Path(principal).name + (f" (y {len(r['evidencias']) - 1} archivo(s) más del caso en la misma carpeta: "
                                          + ", ".join(Path(a).name for a in r["evidencias"][1:]) + ")" if len(r["evidencias"]) > 1 else "")
        valores = {"H": ("s", cadena(r["estado"])), "I": ("s", cadena(r["resultado"])), "J": ("s", cadena(texto_j)),
                   "K": ("s", cadena(r["incidencia"])) if r["incidencia"] else None,
                   "L": ("n", serial_excel(r["fecha"])), "M": ("s", cadena(RESPONSABLE))}
        for col, valor in valores.items():
            patron = re.compile(rf'<c r="{col}{fila}"( s="\d+")?(?: t="\w+")?(?:/>|>.*?</c>)', re.S)
            actual = patron.search(hoja)
            estilo = actual.group(1) or ""
            if valor is None:
                nuevo = f'<c r="{col}{fila}"{estilo}/>'
            elif valor[0] == "s":
                nuevo = f'<c r="{col}{fila}"{estilo} t="s"><v>{valor[1]}</v></c>'
            else:
                nuevo = f'<c r="{col}{fila}"{estilo}><v>{valor[1]}</v></c>'
            hoja = hoja[:actual.start()] + nuevo + hoja[actual.end():]
        n = formula_n(r["estado"], r["resultado"], texto_j, r["incidencia"], True, RESPONSABLE)
        hoja = re.sub(rf'(<c r="N{fila}"[^>]*t="str"[^>]*><f[^>]*>.*?</f><v>)[^<]*(</v>)', lambda mm: f"{mm.group(1)}{escape(n)}{mm.group(2)}", hoja, count=1, flags=re.S)
        rid = f"rIdEvidencia{fila}"
        hipervinculos.append(f'<hyperlink ref="J{fila}" r:id="{rid}"/>')
        relaciones.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{escape(url)}" TargetMode="External"/>')
        cuenta[r["estado"]] += 1
        registros.append(n)
    if "<hyperlinks>" in hoja:
        hoja = re.sub(r"<hyperlinks>.*?</hyperlinks>", "", hoja, flags=re.S)
        rels = re.sub(r'<Relationship Id="rIdEvidencia\d+"[^>]*/>', "", rels)
    hoja = hoja.replace("</dataValidations>", "</dataValidations><hyperlinks>" + "".join(hipervinculos) + "</hyperlinks>", 1)
    rels = rels.replace("</Relationships>", "".join(relaciones) + "</Relationships>")
    partes["xl/worksheets/sheet2.xml"] = hoja.encode()
    partes["xl/worksheets/_rels/sheet2.xml.rels"] = rels.encode()

    # Hoja Plan: versión probada (E11), fecha de cierre (E15) y valores calculados de las fórmulas.
    plan = partes["xl/worksheets/sheet1.xml"].decode()
    hoy = serial_excel(datetime.now(timezone.utc).isoformat())

    def poner(celda: str, valor, tipo: str = "s") -> None:
        nonlocal plan
        patron = re.compile(rf'<c r="{celda}"( s="\d+")?(?: t="\w+")?(?:/>|>.*?</c>)', re.S)
        actual = patron.search(plan)
        estilo = actual.group(1) or ""
        nuevo = (f'<c r="{celda}"{estilo} t="s"><v>{cadena(valor)}</v></c>' if tipo == "s"
                 else f'<c r="{celda}"{estilo}><v>{valor}</v></c>')
        plan = plan[:actual.start()] + nuevo + plan[actual.end():]

    poner("E11", f"{commit_probado} (rama main de {REPOSITORIO})")
    poner("E15", int(hoy), "n")
    ejecutados = cuenta["Aprobado"] + cuenta["Fallido"]
    incompletos = sum(1 for n in registros if n.startswith("Falt") or n == "Revisar estado")
    calculados = {"B10": cuenta["Pendiente"], "B11": cuenta["Aprobado"], "B12": cuenta["Fallido"], "B13": cuenta["Bloqueado"],
                  "B14": cuenta["No aplica"], "B15": ejecutados, "B16": round(ejecutados / 44, 6),
                  "B17": round(cuenta["Aprobado"] / ejecutados, 6) if ejecutados else "", "B18": incompletos}
    for celda, valor in calculados.items():
        plan = re.sub(rf'(<c r="{celda}"[^>]*><f[^>]*>.*?</f><v>)[^<]*(</v>)', lambda mm: f"{mm.group(1)}{valor}{mm.group(2)}", plan, count=1, flags=re.S)
    situacion = ("Ejecución pendiente" if cuenta["Pendiente"] else "Requiere correcciones o desbloqueo"
                 if cuenta["Fallido"] + cuenta["Bloqueado"] else "Completar registros de ejecución" if incompletos else "Listo para revisión docente")
    plan = re.sub(r'(<c r="E17"[^>]*><f[^>]*>.*?</f><v>)[^<]*(</v>)', lambda mm: f"{mm.group(1)}{escape(situacion)}{mm.group(2)}", plan, count=1, flags=re.S)
    partes["xl/worksheets/sheet1.xml"] = plan.encode()

    unicas = re.search(r'uniqueCount="(\d+)"', sst)
    sst = sst.replace("</sst>", "".join(nuevas) + "</sst>")
    if unicas:
        sst = sst.replace(unicas.group(0), f'uniqueCount="{int(unicas.group(1)) + len(nuevas)}"', 1)
    partes["xl/sharedStrings.xml"] = sst.encode()
    # Que Excel y LibreOffice recalculen las fórmulas al abrir.
    libro = partes["xl/workbook.xml"].decode()
    if "fullCalcOnLoad" not in libro:
        libro = libro.replace("<calcPr ", '<calcPr fullCalcOnLoad="1" ', 1)
    partes["xl/workbook.xml"] = libro.encode()
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
