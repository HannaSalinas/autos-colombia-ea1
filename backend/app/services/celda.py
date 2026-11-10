"""Gestión de celdas (RF-27 a RF-31). Las celdas nunca se borran (D4): se inhabilitan.

Reglas de estado (RNF-16): se validan aquí, dentro de una transacción con bloqueo de la fila de la
celda (FOR UPDATE), y en Angular. El formato y la unicidad del código los garantiza además la base.
"""

from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.domain.reglas import validar_codigo_celda
from app.models import AuditoriaCelda, Celda, CorreccionCelda, CuentaUsuario, Estancia, Operador, Vehiculo
from app.schemas.celda import (
    CeldaActualizar, CeldaCrear, CeldaDetalle, CeldaGestion, CeldasPagina, EventoAuditoriaCelda,
)
from app.services.autenticacion import SesionActual

CODIGO_EN_USO = "Ya existe una celda con ese código."


class CeldaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def database_operation(operation):
    """Centraliza rollback y mensajes públicos sin detalles del driver."""
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except CeldaError:
            session.rollback()   # libera el bloqueo de la fila
            raise
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            # uq_celda_codigo (0001) o uq_celda_codigo_ci (0007, sin distinguir mayúsculas).
            if code == "23505" and constraint in {"uq_celda_codigo", "uq_celda_codigo_ci"}:
                raise CeldaError(409, CODIGO_EN_USO) from None
            if code in {"23502", "23514"}:
                raise CeldaError(422, "Los datos incumplen las restricciones de la celda.") from None
            raise CeldaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise CeldaError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


# --- Estado calculado (nunca guardado, para que no pueda desincronizarse) ---

def _abierta(celda=Celda):
    return (Estancia.celda_id == celda.id) & Estancia.salida.is_(None)


def _historial(celda=Celda):
    """D8: la celda aparece en alguna estancia o en alguna corrección (como anterior o como nueva).
    Hay que mirar las correcciones porque al corregir se sobrescribe estancia.celda_id."""
    return or_(
        exists().where(Estancia.celda_id == celda.id),
        exists().where(or_(CorreccionCelda.celda_anterior_id == celda.id, CorreccionCelda.celda_nueva_id == celda.id)),
    )


def _estado():
    return case(
        (Celda.habilitada.is_(False), "INHABILITADA"),
        (exists().where(_abierta()), "OCUPADA"),
        else_="LIBRE",
    )


def _consulta():
    placa = select(Vehiculo.placa).join(Estancia, Estancia.vehiculo_id == Vehiculo.id).where(_abierta()) \
        .limit(1).scalar_subquery()
    return select(Celda, _estado().label("estado"), placa.label("placa"), _historial().label("tiene_historial"))


def _gestion(fila) -> CeldaGestion:
    celda, estado, placa, tiene_historial = fila
    return CeldaGestion(id=celda.id, codigo=celda.codigo, tipo=celda.tipo, disponible_desde=celda.disponible_desde,
                        ubicacion=celda.ubicacion, habilitada=celda.habilitada, estado=estado, placa=placa,
                        tiene_historial=bool(tiene_historial))


def _una(session: Session, cell_id: int) -> CeldaGestion:
    fila = session.execute(_consulta().where(Celda.id == cell_id)).one_or_none()
    if fila is None:
        raise CeldaError(404, "Celda no encontrada.")
    return _gestion(fila)


def find_cell(session: Session, cell_id: int, for_update: bool = False) -> Celda:
    cell = session.get(Celda, cell_id, with_for_update=for_update)
    if cell is None:
        raise CeldaError(404, "Celda no encontrada.")
    return cell


def _auditar(session: Session, celda_id: int, actor: SesionActual, accion: str, detalle: str | None = None) -> None:
    # Hora del servidor en el momento de la acción (now() de SQL sería la del inicio de la transacción).
    session.add(AuditoriaCelda(celda_id=celda_id, actor_cuenta_id=actor.cuenta_id, accion=accion, detalle=detalle,
                               fecha=datetime.now(timezone.utc)))


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# --- Operaciones ---

@database_operation
def list_cells(session: Session, offset: int, limit: int, buscar: str | None = None, tipo: str | None = None,
               estado: str | None = None) -> CeldasPagina:
    """RF-27: búsqueda por código y filtros por tipo y estado; las ocupadas traen la placa."""
    consulta = _consulta()
    if buscar and buscar.strip():
        consulta = consulta.where(Celda.codigo.ilike(f"%{_escapar(buscar.strip())}%", escape="\\"))
    if tipo:
        consulta = consulta.where(Celda.tipo == tipo)
    if estado:
        consulta = consulta.where(_estado() == estado)
    total = session.scalar(select(func.count()).select_from(consulta.subquery()))
    filas = session.execute(consulta.order_by(Celda.codigo, Celda.id).offset(offset).limit(limit)).all()
    return CeldasPagina(items=[_gestion(f) for f in filas], total=total, offset=offset, limit=limit)


@database_operation
def get_cell(session: Session, cell_id: int) -> CeldaDetalle:
    celda = _una(session, cell_id)
    actor, persona = aliased(CuentaUsuario), aliased(Operador)
    eventos = session.execute(
        select(AuditoriaCelda, persona.nombre, actor.nombre_usuario)
        .outerjoin(actor, actor.id == AuditoriaCelda.actor_cuenta_id)
        .outerjoin(persona, persona.id == actor.operador_id)
        .where(AuditoriaCelda.celda_id == cell_id).order_by(AuditoriaCelda.fecha, AuditoriaCelda.id)
    ).all()
    return CeldaDetalle(**celda.model_dump(), auditoria=[
        EventoAuditoriaCelda(fecha=e.fecha, accion=e.accion, detalle=e.detalle,
                             actor=f"{nombre} ({usuario})" if usuario else None)
        for e, nombre, usuario in eventos
    ])


@database_operation
def create_cell(session: Session, data: CeldaCrear, actor: SesionActual) -> CeldaGestion:
    """RF-28. disponible_desde queda NULL: "nunca usada", así que se asigna primero.
    Si dos administradores crean el mismo código a la vez, el índice único deja solo una."""
    cell = Celda(codigo=data.codigo, tipo=data.tipo, ubicacion=data.ubicacion, habilitada=True)
    session.add(cell)
    session.flush()
    _auditar(session, cell.id, actor, "CREAR",
             f"Código {cell.codigo}, tipo {cell.tipo}" + (f", ubicación {cell.ubicacion}" if cell.ubicacion else "") + ".")
    session.commit()
    return _una(session, cell.id)


def _ocupada(session: Session, cell_id: int) -> bool:
    return session.scalar(select(exists().where((Estancia.celda_id == cell_id) & Estancia.salida.is_(None))))


def _tiene_historial(session: Session, cell_id: int) -> bool:
    return session.scalar(select(_historial()).where(Celda.id == cell_id))


@database_operation
def update_cell(session: Session, cell_id: int, data: CeldaActualizar, actor: SesionActual) -> CeldaGestion:
    """RF-29 y D8. FOR UPDATE: mientras se edita, una entrada simultánea (SKIP LOCKED) salta la celda y
    las revisiones de ocupación e historial ven todo lo confirmado antes del bloqueo."""
    cell = find_cell(session, cell_id, for_update=True)
    cambios = data.model_dump(exclude_unset=True)
    codigo, tipo = cambios.get("codigo", cell.codigo), cambios.get("tipo", cell.tipo)
    if codigo != cell.codigo or tipo != cell.tipo:
        if _ocupada(session, cell.id):
            raise CeldaError(409, f"La celda {cell.codigo} está ocupada: su código y su tipo no se pueden cambiar.")
        if _tiene_historial(session, cell.id):
            raise CeldaError(409, f"La celda {cell.codigo} ya tuvo movimientos: su código y su tipo no se pueden "
                                  "cambiar, para que el historial siga siendo legible. Solo se puede editar su ubicación.")
        try:
            validar_codigo_celda(codigo, tipo)
        except ValueError as error:
            raise CeldaError(422, str(error)) from None
    detalle = []
    etiquetas = {"codigo": "código", "tipo": "tipo", "ubicacion": "ubicación"}
    for campo, valor in cambios.items():
        anterior = getattr(cell, campo)
        if valor != anterior:
            detalle.append(f"{etiquetas[campo]}: {anterior or '—'} → {valor or '—'}")
            setattr(cell, campo, valor)
    if detalle:
        _auditar(session, cell.id, actor, "EDITAR", "; ".join(detalle))
    session.commit()
    return _una(session, cell.id)


@database_operation
def disable_cell(session: Session, cell_id: int, actor: SesionActual) -> CeldaGestion:
    """RF-30 y RNF-17. FOR UPDATE (espera, no salta): si una portería está asignando esta celda, se
    espera a que confirme y entonces se ve la estancia abierta (409). Si inhabilitar llega primero,
    la entrada simultánea salta la celda bloqueada (SKIP LOCKED) y toma otra."""
    cell = find_cell(session, cell_id, for_update=True)
    if not cell.habilitada:
        raise CeldaError(409, f"La celda {cell.codigo} ya está inhabilitada.")
    if _ocupada(session, cell.id):
        raise CeldaError(409, f"La celda {cell.codigo} está ocupada: primero debe salir el vehículo.")
    cell.habilitada = False
    _auditar(session, cell.id, actor, "INHABILITAR")
    session.commit()
    return _una(session, cell.id)


@database_operation
def enable_cell(session: Session, cell_id: int, actor: SesionActual) -> CeldaGestion:
    """RF-30: vuelve a estar disponible y su tiempo libre se cuenta desde la rehabilitación."""
    cell = find_cell(session, cell_id, for_update=True)
    if cell.habilitada:
        raise CeldaError(409, f"La celda {cell.codigo} ya está habilitada.")
    cell.habilitada = True
    cell.disponible_desde = datetime.now(timezone.utc)
    _auditar(session, cell.id, actor, "REHABILITAR")
    session.commit()
    return _una(session, cell.id)
