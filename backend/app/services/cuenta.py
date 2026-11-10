"""Gestión de cuentas de usuario (RF-24, RF-25, RF-26, RF-31). Las cuentas nunca se borran (D4).

Reglas de estado (RNF-16): se validan aquí, dentro de una transacción con bloqueo de filas, y en
Angular. La unicidad del usuario la garantiza además el índice único lower(nombre_usuario).
"""

from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.models import AuditoriaCuenta, CuentaUsuario, Operador
from app.schemas.cuenta import CuentaCrear, CuentaDetalle, CuentaRespuesta, CuentasPagina, EventoAuditoria
from app.services.autenticacion import SESION_VENCIDA, AutenticacionError, SesionActual
from app.services.seguridad import hash_contrasena

USUARIO_EN_USO = "Ese nombre de usuario ya está en uso."
PROPIA_CUENTA = "No puedes desactivar tu propia cuenta."
ULTIMO_ADMINISTRADOR = "No se puede desactivar al último administrador activo."


class CuentaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def operacion(funcion):
    """Rollback y mensajes en español: nunca un detalle de la base de datos (RNF-15)."""
    @wraps(funcion)
    def envuelta(session: Session, *args, **kwargs):
        try:
            return funcion(session, *args, **kwargs)
        except (CuentaError, AutenticacionError):
            session.rollback()   # libera los bloqueos tomados
            raise
        except IntegrityError as error:
            session.rollback()
            restriccion = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if restriccion == "uq_cuenta_usuario_nombre":
                raise CuentaError(409, USUARIO_EN_USO) from None
            raise CuentaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise CuentaError(503, "No se pudo completar la operación con la base de datos.") from None
    return envuelta


def _respuesta(cuenta: CuentaUsuario, nombre: str) -> CuentaRespuesta:
    return CuentaRespuesta(id=cuenta.id, nombre=nombre, nombre_usuario=cuenta.nombre_usuario, rol=cuenta.rol,
                           activa=cuenta.activa, creada_en=cuenta.creada_en)


def _usuario_existe(session: Session, usuario: str) -> bool:
    return session.scalar(select(CuentaUsuario.id).where(func.lower(CuentaUsuario.nombre_usuario) == usuario)) \
        is not None


@operacion
def crear(session: Session, data: CuentaCrear, actor: SesionActual) -> CuentaRespuesta:
    # Aviso temprano y amable; la garantía real ante dos solicitudes simultáneas es el índice único.
    if _usuario_existe(session, data.nombre_usuario):
        raise CuentaError(409, USUARIO_EN_USO)
    session.commit()   # cierra la lectura: el hash tarda ~0,5 s y no debe retener la conexión
    hash_nuevo = hash_contrasena(data.contrasena)
    persona = Operador(nombre=data.nombre)
    session.add(persona)
    session.flush()
    ahora = datetime.now(timezone.utc)   # hora del servidor en el momento de la acción (no now() de SQL,
    #                                      que es la hora en que empezó la transacción)
    cuenta = CuentaUsuario(operador_id=persona.id, nombre_usuario=data.nombre_usuario, hash_contrasena=hash_nuevo,
                           rol=data.rol, activa=True, version_sesion=0, creada_en=ahora)
    session.add(cuenta)
    session.flush()
    session.add(AuditoriaCuenta(cuenta_id=cuenta.id, actor_cuenta_id=actor.cuenta_id, accion="CREAR",
                                detalle=f"Rol {data.rol.lower()}.", fecha=ahora))
    session.commit()
    session.refresh(cuenta)
    return _respuesta(cuenta, persona.nombre)


def _escapar(texto: str) -> str:
    """Para LIKE: % y _ se buscan como caracteres, no como comodines."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@operacion
def listar(session: Session, buscar: str | None, rol: str | None, activa: bool | None,
           offset: int, limit: int) -> CuentasPagina:
    """Búsqueda por nombre o usuario (sin distinguir mayúsculas) y filtros por rol y estado (RF-25)."""
    consulta = select(CuentaUsuario, Operador.nombre).join(Operador, Operador.id == CuentaUsuario.operador_id)
    if buscar and buscar.strip():
        patron = f"%{_escapar(buscar.strip())}%"
        consulta = consulta.where(or_(Operador.nombre.ilike(patron, escape="\\"),
                                      CuentaUsuario.nombre_usuario.ilike(patron, escape="\\")))
    if rol:
        consulta = consulta.where(CuentaUsuario.rol == rol)
    if activa is not None:
        consulta = consulta.where(CuentaUsuario.activa.is_(activa))
    total = session.scalar(select(func.count()).select_from(consulta.subquery()))
    filas = session.execute(consulta.order_by(Operador.nombre, CuentaUsuario.id).offset(offset).limit(limit)).all()
    return CuentasPagina(items=[_respuesta(c, nombre) for c, nombre in filas], total=total, offset=offset,
                         limit=limit)


# FOR NO KEY UPDATE (no FOR UPDATE): bloquea la fila frente a otras modificaciones, pero no frente a
# quien solo la referencia con una llave foránea (por ejemplo, la auditoría que guarda al actor).
NO_KEY_UPDATE = {"key_share": True}


def _buscar(session: Session, cuenta_id: int, bloquear: bool = False) -> CuentaUsuario:
    cuenta = session.get(CuentaUsuario, cuenta_id, with_for_update=NO_KEY_UPDATE if bloquear else None)
    if cuenta is None:
        raise CuentaError(404, "Cuenta no encontrada.")
    return cuenta


@operacion
def detalle(session: Session, cuenta_id: int) -> CuentaDetalle:
    cuenta = _buscar(session, cuenta_id)
    actor, persona_actor = aliased(CuentaUsuario), aliased(Operador)
    eventos = session.execute(
        select(AuditoriaCuenta, persona_actor.nombre, actor.nombre_usuario)
        .outerjoin(actor, actor.id == AuditoriaCuenta.actor_cuenta_id)
        .outerjoin(persona_actor, persona_actor.id == actor.operador_id)
        .where(AuditoriaCuenta.cuenta_id == cuenta_id).order_by(AuditoriaCuenta.fecha, AuditoriaCuenta.id)
    ).all()
    return CuentaDetalle(
        **_respuesta(cuenta, cuenta.persona.nombre).model_dump(),
        auditoria=[EventoAuditoria(fecha=e.fecha, accion=e.accion, detalle=e.detalle,
                                   actor=f"{nombre} ({usuario})" if usuario else None)
                   for e, nombre, usuario in eventos],
    )


def _actor_vigente(session: Session, actor: SesionActual) -> None:
    """Dentro de la transacción: quien actúa sigue activo (pudo ser desactivado un instante antes)."""
    fila = session.execute(select(CuentaUsuario.activa, CuentaUsuario.version_sesion)
                           .where(CuentaUsuario.id == actor.cuenta_id)).one_or_none()
    if fila is None or not fila.activa or fila.version_sesion != actor.version_sesion:
        raise AutenticacionError(401, SESION_VENCIDA)


@operacion
def desactivar(session: Session, cuenta_id: int, actor: SesionActual) -> CuentaRespuesta:
    """HU-21. Nadie puede desactivar su propia cuenta ni dejar el sistema sin administradores activos.

    Bloqueos al desactivar a un administrador: primero las filas de TODOS los administradores activos
    (siempre en el mismo orden, por id) y después la cuenta a desactivar. Si dos administradores intentan desactivarse el uno al otro
    al mismo tiempo, el segundo espera al primero y, al continuar, ve que solo queda un
    administrador activo: no se pueden quedar en cero.
    """
    if cuenta_id == actor.cuenta_id:
        raise CuentaError(409, PROPIA_CUENTA)
    # El rol de una cuenta nunca cambia (no hay edición de cuentas, D6), así que se puede leer sin
    # bloqueo para decidir qué bloquear. Solo al desactivar a un administrador hace falta bloquear a
    # todos los administradores activos; desactivar operadores no se pone en fila detrás de ellos.
    rol = session.scalar(select(CuentaUsuario.rol).where(CuentaUsuario.id == cuenta_id))
    if rol is None:
        raise CuentaError(404, "Cuenta no encontrada.")
    administradores: list[int] = []
    if rol == "ADMINISTRADOR":
        administradores = list(session.scalars(
            select(CuentaUsuario.id).where(CuentaUsuario.rol == "ADMINISTRADOR", CuentaUsuario.activa.is_(True))
            .order_by(CuentaUsuario.id).with_for_update(key_share=True)
        ))
    cuenta = _buscar(session, cuenta_id, bloquear=True)
    if not cuenta.activa:
        raise CuentaError(409, "La cuenta ya está desactivada.")
    # Como quien actúa es un administrador activo y no puede desactivarse a sí mismo, esta regla solo
    # se activa en la carrera de dos administradores que se desactivan mutuamente: el segundo llega
    # aquí cuando el primero ya confirmó y solo queda un administrador activo.
    if cuenta.rol == "ADMINISTRADOR" and len(administradores) <= 1:
        raise CuentaError(409, ULTIMO_ADMINISTRADOR)
    _actor_vigente(session, actor)
    cuenta.activa = False
    # Revoca sus sesiones abiertas: sus tokens dejan de valer en la siguiente solicitud (RF-26),
    # y siguen sin valer aunque la cuenta se reactive.
    cuenta.version_sesion += 1
    session.add(AuditoriaCuenta(cuenta_id=cuenta.id, actor_cuenta_id=actor.cuenta_id, accion="DESACTIVAR",
                                fecha=datetime.now(timezone.utc)))
    session.commit()
    session.refresh(cuenta)
    return _respuesta(cuenta, cuenta.persona.nombre)


@operacion
def reactivar(session: Session, cuenta_id: int, actor: SesionActual) -> CuentaRespuesta:
    cuenta = _buscar(session, cuenta_id, bloquear=True)
    _actor_vigente(session, actor)
    if cuenta.activa:
        raise CuentaError(409, "La cuenta ya está activa.")
    cuenta.activa = True
    session.add(AuditoriaCuenta(cuenta_id=cuenta.id, actor_cuenta_id=actor.cuenta_id, accion="REACTIVAR",
                                fecha=datetime.now(timezone.utc)))
    session.commit()
    session.refresh(cuenta)
    return _respuesta(cuenta, cuenta.persona.nombre)
