"""Las semillas crean los casos de demostración y no duplican al repetirse (con rollback)."""

from datetime import timedelta

from sqlalchemy import func, select

from app.domain.reglas import hoy_bogota
from app.seed import VEHICULOS, sembrar
from app.models import Celda, Vehiculo


def test_semillas_idempotentes_y_casos_de_mensualidad(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    sembrar(session, hoy)
    total = session.scalar(select(func.count()).select_from(Vehiculo))
    assert set(sembrar(session, hoy).values()) == {0}
    assert session.scalar(select(func.count()).select_from(Vehiculo)) == total
    estado = {v["placa"]: v for v in api.get("/vehiculos?limit=100").json()["items"]}
    esperado = {"vigente": True, "vence_hoy": True, "renovada": True,
                "vencida": False, "sin_mensualidad": False, "empieza_manana": False}
    for placa, *_, caso in VEHICULOS:
        assert estado[placa]["mensualidad_vigente"] is esperado[caso], placa
    assert estado["GHI789"]["mensualidad_hasta"] == hoy.isoformat()
    assert estado["MNO654"]["mensualidad_hasta"] is None
    # Mensualidad futura: la pantalla muestra "Empieza el ...".
    assert estado["PQR98B"]["mensualidad_proxima"] == (hoy + timedelta(days=1)).isoformat()


def test_semillas_crean_80_celdas_por_tipo(api_y_sesion):
    _, session = api_y_sesion
    sembrar(session, hoy_bogota())
    codigos = {c.codigo: c.tipo for c in session.scalars(select(Celda).where(Celda.codigo.regexp_match("^[CM][0-9]{2}$")))}
    assert sum(t == "CARRO" for t in codigos.values()) == 70 and codigos["C70"] == "CARRO"
    assert sum(t == "MOTO" for t in codigos.values()) == 10 and codigos["M10"] == "MOTO"


# --- Iteración 2: cuentas semilla ---

def test_semillas_crean_cuentas_sobre_las_personas_de_la_ea1(api_y_sesion):
    from app.config import CredencialesSemilla
    from app.models import AuditoriaCuenta, CuentaUsuario, Operador
    from app.services.seguridad import verificar_contrasena

    api, session = api_y_sesion
    if session.scalar(select(func.count()).select_from(CuentaUsuario)
                      .where(CuentaUsuario.nombre_usuario.in_(["marta.usuga", "diego.arango"]))):
        import pytest
        pytest.skip("La base ya tiene las cuentas semilla.")
    credenciales = CredencialesSemilla(admin_usuario="admin.semilla", admin_nombre="Administrador de prueba",
                                       admin_contrasena="admin1234", marta_contrasena="marta1234",
                                       diego_contrasena="diego1234")
    hoy = hoy_bogota()
    sembrar(session, hoy)                         # personas de la EA1, sin cuentas todavía
    marta = session.scalar(select(Operador).where(Operador.nombre == "Marta Úsuga (Portería 1)"))
    assert sembrar(session, hoy, credenciales)["cuentas"] == 3
    cuentas = {c.nombre_usuario: c for c in session.scalars(select(CuentaUsuario).where(
        CuentaUsuario.nombre_usuario.in_(["admin.semilla", "marta.usuga", "diego.arango"])))}
    assert {u: c.rol for u, c in cuentas.items()} == {
        "admin.semilla": "ADMINISTRADOR", "marta.usuga": "OPERADOR", "diego.arango": "OPERADOR"}
    # Marta usa su persona de la EA1: sus movimientos anteriores siguen a su nombre.
    assert cuentas["marta.usuga"].operador_id == marta.id
    assert cuentas["admin.semilla"].persona.nombre == "Administrador de prueba"
    assert cuentas["admin.semilla"].persona.telefono is None
    for usuario, clave in (("admin.semilla", "admin1234"), ("marta.usuga", "marta1234"),
                           ("diego.arango", "diego1234")):
        assert cuentas[usuario].hash_contrasena.startswith("$2b$12$")
        assert verificar_contrasena(clave, cuentas[usuario].hash_contrasena)
    # Auditoría: creadas por el sistema (actor NULL).
    auditoria = list(session.scalars(select(AuditoriaCuenta).where(
        AuditoriaCuenta.cuenta_id.in_([c.id for c in cuentas.values()]))))
    assert len(auditoria) == 3 and all(a.accion == "CREAR" and a.actor_cuenta_id is None for a in auditoria)
    # Idempotente: no crea otra vez ni cambia la contraseña.
    hash_marta = cuentas["marta.usuga"].hash_contrasena
    otras = CredencialesSemilla(admin_usuario="admin.semilla", admin_nombre="Otro nombre", admin_contrasena="otra1234",
                                marta_contrasena="otra1234", diego_contrasena="otra1234")
    assert sembrar(session, hoy, otras)["cuentas"] == 0
    session.refresh(cuentas["marta.usuga"])
    assert cuentas["marta.usuga"].hash_contrasena == hash_marta
    # Marta ingresa con su contraseña y queda como responsable de lo que registre.
    session.commit()
    respuesta = api.post("/auth/login", json={"usuario": "marta.usuga", "contrasena": "marta1234"},
                         headers={"Authorization": ""})
    assert respuesta.status_code == 200 and respuesta.json()["cuenta"]["rol"] == "OPERADOR"
