"""Pagos de mensualidad (Iteración 3, RF-35 a RF-38, RNF-23, RNF-24).

Reglas de estado (RNF-16): se validan aquí, dentro de una transacción que bloquea la fila del
vehículo (SELECT … FOR UPDATE). Así, dos pagos simultáneos del mismo vehículo se registran uno
después del otro y dan dos periodos consecutivos (RNF-23); y un pago y una anulación simultáneos
tampoco se cruzan. La base de datos es la última barrera: exclusión parcial de periodos pagados,
comprobante único y triggers de inmutabilidad (migraciones 0009 y 0010).
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.domain.pagos import (
    Periodo, calcular_monto, estado_mensualidad, fin_de_periodo, formatear_pesos, inicio_de_periodo,
    tope_de_adelanto, validar_tope_de_adelanto,
)
from app.domain.reglas import hoy_bogota, rango_bogota
from app.models import Cliente, CuentaUsuario, Mensualidad, Operador, Pago, Tarifa, Vehiculo
from app.schemas.pago import (
    AnulacionCrear, ClienteResumen, CotizacionRespuesta, EstadoMensualidadRespuesta, PagoCrear, PagoDetalle,
    PagoResumen, PagosPagina, PeriodoRespuesta, TarifaVigente,
)
from app.services.autenticacion import SesionActual
from app.services.mensualidad import periodo_valido
from app.services.tarifa import tarifa_vigente

VEHICULO_NO_ENCONTRADO = "Vehículo no encontrado."


class PagoError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def operacion(funcion):
    """Centraliza rollback (libera el bloqueo) y mensajes públicos sin detalles del driver."""
    @wraps(funcion)
    def envuelta(session: Session, *args, **kwargs):
        try:
            return funcion(session, *args, **kwargs)
        except PagoError:
            session.rollback()
            raise
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23P01":   # exclusión: dos periodos pagados del mismo vehículo se cruzarían
                raise PagoError(409, "Otro pago de este vehículo se registró al mismo tiempo. Vuelve a consultar "
                                     "el estado de la mensualidad.") from None
            if code == "23505" and constraint == "uq_pago_comprobante":
                raise PagoError(409, "No se pudo asignar el número de comprobante. Intenta de nuevo.") from None
            if code == "23503":
                raise PagoError(404, "Una de las referencias ya no existe. Actualiza los datos.") from None
            if code in {"23502", "23514"}:
                raise PagoError(422, "Los datos incumplen las restricciones del pago.") from None
            if code == "23001":   # triggers de inmutabilidad (RNF-24)
                raise PagoError(409, "Un pago no se edita ni se elimina: solo se puede anular.") from None
            raise PagoError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise PagoError(503, "No se pudo completar la operación con la base de datos.") from None
    return envuelta


# --- Consultas de apoyo ---

def _vehiculo(session: Session, placa: str, bloquear: bool = False) -> Vehiculo:
    consulta = select(Vehiculo).where(Vehiculo.placa == placa)
    vehiculo = session.scalar(consulta.with_for_update() if bloquear else consulta)
    if vehiculo is None:
        raise PagoError(404, VEHICULO_NO_ENCONTRADO)
    return vehiculo


def _periodos_validos(session: Session, vehiculo_id: int) -> list[tuple[Mensualidad, str | None]]:
    """Periodos que cuentan (sin anulados) con el comprobante de su pago, si lo tienen."""
    return list(session.execute(
        select(Mensualidad, Pago.comprobante).outerjoin(Pago, Pago.id == Mensualidad.pago_id)
        .where(Mensualidad.vehiculo_id == vehiculo_id, periodo_valido())
        .order_by(Mensualidad.fecha_inicio, Mensualidad.id)
    ).all())


def _ultimo_fin(session: Session, vehiculo_id: int) -> date | None:
    return session.scalar(select(func.max(Mensualidad.fecha_fin))
                          .where(Mensualidad.vehiculo_id == vehiculo_id, periodo_valido()))


@dataclass(frozen=True)
class _Calculo:
    inicio: date
    fin: date
    tarifa: Tarifa
    monto: int


def _calcular(session: Session, vehiculo: Vehiculo, meses: int, hoy: date) -> _Calculo:
    """Fechas (D13), tope de 12 meses y monto (D11). Lo usan la cotización y el registro."""
    inicio = inicio_de_periodo(_ultimo_fin(session, vehiculo.id), hoy)
    fin = fin_de_periodo(inicio, meses)
    try:
        validar_tope_de_adelanto(fin, hoy)
    except ValueError as error:
        raise PagoError(409, str(error)) from None
    tarifa = tarifa_vigente(session, vehiculo.tipo)
    if tarifa is None:
        raise PagoError(409, f"No hay tarifa definida para {vehiculo.tipo}: el Administrador debe definirla "
                             "en Tarifas antes de registrar el pago.")
    return _Calculo(inicio, fin, tarifa, calcular_monto(tarifa.valor, meses))


def _cliente(session: Session, cliente_id: int) -> Cliente:
    return session.get(Cliente, cliente_id)


# --- Operaciones ---

@operacion
def estado(session: Session, placa: str) -> EstadoMensualidadRespuesta:
    """RF-35, HU-29. Los periodos anulados no cuentan para el estado."""
    vehiculo = _vehiculo(session, placa)
    hoy = hoy_bogota()
    filas = _periodos_validos(session, vehiculo.id)
    comprobantes = {(m.fecha_inicio, m.fecha_fin): c for m, c in filas}
    resultado = estado_mensualidad([Periodo(m.fecha_inicio, m.fecha_fin) for m, _ in filas], hoy)

    def respuesta(p: Periodo) -> PeriodoRespuesta:
        return PeriodoRespuesta(fecha_inicio=p.inicio, fecha_fin=p.fin, comprobante=comprobantes.get((p.inicio, p.fin)))

    cliente = _cliente(session, vehiculo.cliente_id)
    tarifa = tarifa_vigente(session, vehiculo.tipo)
    return EstadoMensualidadRespuesta(
        vehiculo_id=vehiculo.id, placa=vehiculo.placa, tipo_vehiculo=vehiculo.tipo, marca=vehiculo.marca,
        color=vehiculo.color,
        cliente=ClienteResumen(id=cliente.id, tipo_documento=cliente.tipo_documento, documento=cliente.documento,
                               nombre=cliente.nombre, telefono=cliente.telefono),
        estado=resultado.estado,
        periodo_actual=respuesta(resultado.actual) if resultado.actual else None,
        periodos_futuros=[respuesta(p) for p in resultado.futuros],
        vence=resultado.vence, dias_restantes=resultado.dias_restantes,
        inicio_nuevo_periodo=inicio_de_periodo(resultado.ultimo_fin, hoy), fin_maximo=tope_de_adelanto(hoy),
        tarifa=TarifaVigente(id=tarifa.id, tipo_vehiculo=tarifa.tipo_vehiculo, valor=tarifa.valor) if tarifa else None,
    )


@operacion
def cotizar(session: Session, placa: str, meses: int) -> CotizacionRespuesta:
    """El resumen que se confirma antes de registrar (RNF-27). No guarda nada."""
    vehiculo = _vehiculo(session, placa)
    calculo = _calcular(session, vehiculo, meses, hoy_bogota())
    return CotizacionRespuesta(
        placa=vehiculo.placa, cliente_nombre=_cliente(session, vehiculo.cliente_id).nombre,
        tipo_vehiculo=vehiculo.tipo, meses=meses, fecha_inicio=calculo.inicio, fecha_fin=calculo.fin,
        tarifa_id=calculo.tarifa.id, valor_mensual=calculo.tarifa.valor, monto=calculo.monto,
    )


@operacion
def registrar(session: Session, data: PagoCrear, actor: SesionActual) -> PagoDetalle:
    """RF-36, HU-30. FOR UPDATE sobre el vehículo: un segundo pago simultáneo espera a que este
    confirme y entonces ve su periodo, así que empieza el día siguiente (RNF-23)."""
    vehiculo = _vehiculo(session, data.placa, bloquear=True)
    calculo = _calcular(session, vehiculo, data.meses, hoy_bogota())
    if calculo.monto != data.monto_confirmado:
        raise PagoError(409, f"La tarifa cambió después del resumen: el monto ahora es {formatear_pesos(calculo.monto)}. "
                             "Revisa el nuevo resumen y confirma otra vez.")
    pago = Pago(meses=data.meses, tarifa_id=calculo.tarifa.id, tipo_vehiculo=calculo.tarifa.tipo_vehiculo,
                valor_mensual=calculo.tarifa.valor, monto=calculo.monto, metodo=data.metodo,
                referencia=data.referencia, fecha=datetime.now(timezone.utc),   # hora del servidor, nunca del cliente
                registrado_por_cuenta_id=actor.cuenta_id)                       # responsable: la sesión
    session.add(pago)
    session.flush()
    session.add(Mensualidad(vehiculo_id=vehiculo.id, fecha_inicio=calculo.inicio, fecha_fin=calculo.fin,
                            pago_id=pago.id, pago_estado="VALIDO"))
    session.commit()
    return _detalle(session, pago.id)


@operacion
def anular(session: Session, pago_id: int, data: AnulacionCrear, actor: SesionActual) -> PagoDetalle:
    """RF-38, HU-32. Solo el pago VÁLIDO del último periodo del vehículo (D14). FOR UPDATE sobre el
    vehículo (el mismo bloqueo del registro) y luego sobre el pago, para leer su estado actual."""
    periodo = session.scalar(select(Mensualidad).where(Mensualidad.pago_id == pago_id))
    if periodo is None:
        raise PagoError(404, "Pago no encontrado.")
    session.scalar(select(Vehiculo).where(Vehiculo.id == periodo.vehiculo_id).with_for_update())
    pago = session.scalar(select(Pago).where(Pago.id == pago_id).with_for_update().execution_options(
        populate_existing=True))
    if pago.estado == "ANULADO":
        raise PagoError(409, f"El pago {pago.comprobante} ya está anulado.")
    ultimo = _ultimo_periodo(session, periodo.vehiculo_id)
    if ultimo.id != periodo.id:
        raise PagoError(409, f"Solo se puede anular el pago del último periodo del vehículo. El pago "
                             f"{pago.comprobante} cubre del {periodo.fecha_inicio:%d/%m/%Y} al "
                             f"{periodo.fecha_fin:%d/%m/%Y}, pero hay un periodo posterior que va hasta el "
                             f"{ultimo.fecha_fin:%d/%m/%Y}.")
    pago.estado = "ANULADO"
    pago.anulado_en = datetime.now(timezone.utc)
    pago.anulado_por_cuenta_id = actor.cuenta_id
    pago.motivo_anulacion = data.motivo
    session.commit()
    return _detalle(session, pago.id)


def _ultimo_periodo(session: Session, vehiculo_id: int) -> Mensualidad:
    return session.scalar(select(Mensualidad).where(Mensualidad.vehiculo_id == vehiculo_id, periodo_valido())
                          .order_by(Mensualidad.fecha_fin.desc(), Mensualidad.id.desc()).limit(1))


# --- Listado y detalle (RF-37) ---

def _consulta():
    registro, persona_registro = aliased(CuentaUsuario), aliased(Operador)
    anulacion, persona_anulacion = aliased(CuentaUsuario), aliased(Operador)
    return (
        select(Pago, Mensualidad, Vehiculo, Cliente,
               persona_registro.nombre, registro.nombre_usuario, persona_anulacion.nombre, anulacion.nombre_usuario)
        .join(Mensualidad, Mensualidad.pago_id == Pago.id)
        .join(Vehiculo, Vehiculo.id == Mensualidad.vehiculo_id)
        .join(Cliente, Cliente.id == Vehiculo.cliente_id)
        .join(registro, registro.id == Pago.registrado_por_cuenta_id)
        .join(persona_registro, persona_registro.id == registro.operador_id)
        .outerjoin(anulacion, anulacion.id == Pago.anulado_por_cuenta_id)
        .outerjoin(persona_anulacion, persona_anulacion.id == anulacion.operador_id)
    )


def _resumen(fila) -> dict:
    pago, periodo, vehiculo, cliente, nombre, usuario, *_ = fila
    return dict(id=pago.id, comprobante=pago.comprobante, fecha=pago.fecha, placa=vehiculo.placa,
                cliente_nombre=cliente.nombre, fecha_inicio=periodo.fecha_inicio, fecha_fin=periodo.fecha_fin,
                meses=pago.meses, monto=pago.monto, metodo=pago.metodo, estado=pago.estado,
                registrado_por=f"{nombre} ({usuario})")


def _detalle(session: Session, pago_id: int) -> PagoDetalle:
    fila = session.execute(_consulta().where(Pago.id == pago_id)).one_or_none()
    if fila is None:
        raise PagoError(404, "Pago no encontrado.")
    pago, periodo, vehiculo, cliente, _, _, nombre_anula, usuario_anula = fila
    ultimo = _ultimo_periodo(session, vehiculo.id)
    return PagoDetalle(
        **_resumen(fila), vehiculo_id=vehiculo.id, tipo_vehiculo=pago.tipo_vehiculo,
        cliente_tipo_documento=cliente.tipo_documento, cliente_documento=cliente.documento,
        valor_mensual=pago.valor_mensual, referencia=pago.referencia, anulado_en=pago.anulado_en,
        anulado_por=f"{nombre_anula} ({usuario_anula})" if usuario_anula else None,
        motivo_anulacion=pago.motivo_anulacion,
        anulable=pago.estado == "VALIDO" and ultimo is not None and ultimo.id == periodo.id,
    )


@operacion
def detalle(session: Session, pago_id: int) -> PagoDetalle:
    return _detalle(session, pago_id)


@operacion
def listar(session: Session, offset: int, limit: int, placa: str | None = None, desde: date | None = None,
           hasta: date | None = None, metodo: str | None = None, estado: str | None = None) -> PagosPagina:
    """Filtra por el día de Bogotá de la fecha del pago (como el historial). Más recientes primero."""
    try:
        inicio, fin = rango_bogota(desde, hasta)
    except ValueError:
        raise PagoError(422, "La fecha inicial no puede ser posterior a la fecha final.") from None
    consulta = _consulta()
    if placa:
        consulta = consulta.where(Vehiculo.placa == placa)
    if inicio is not None:
        consulta = consulta.where(Pago.fecha >= inicio)
    if fin is not None:
        consulta = consulta.where(Pago.fecha < fin)
    if metodo:
        consulta = consulta.where(Pago.metodo == metodo)
    if estado:
        consulta = consulta.where(Pago.estado == estado)
    total = session.scalar(select(func.count()).select_from(consulta.subquery()))
    filas = session.execute(consulta.order_by(Pago.fecha.desc(), Pago.id.desc()).offset(offset).limit(limit)).all()
    return PagosPagina(items=[PagoResumen(**_resumen(f)) for f in filas], total=total, offset=offset, limit=limit)
