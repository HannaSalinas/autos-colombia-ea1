from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import and_, exists, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.reglas import formatear_permanencia, hoy_bogota, permanencia_segundos, tipo_celda_para
from app.models import Celda, Estancia, Mensualidad, Operador, Vehiculo, required_text
from app.schemas.celda import CeldaRespuesta
from app.schemas.estancia import (
    EntradaCrear, SalidaCrear, EstanciaRespuesta, EstanciaAbiertaRespuesta,
    EstadoVehiculoRespuesta, MovimientoRespuesta,
)
from app.schemas.vehiculo import VehiculoRespuesta


class EstanciaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def transaccion(operation):
    """Una transacción por solicitud; materializa la respuesta antes del commit."""
    @wraps(operation)
    def wrapped(self, *args, **kwargs):
        try:
            with self.session.begin():
                return operation(self, *args, **kwargs)
        except IntegrityError as error:
            self.session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505":
                if constraint == "uq_estancia_vehiculo_abierta":
                    raise EstanciaError(409, "El vehículo ya está dentro.") from None
                if constraint == "uq_estancia_celda_abierta":
                    raise EstanciaError(409, "La celda está ocupada.") from None
            if code == "23503":
                raise EstanciaError(404, "Una de las referencias ya no existe. Actualiza los datos.") from None
            if code in {"23502", "23514"}:
                raise EstanciaError(422, "Los datos incumplen las restricciones de la estancia.") from None
            raise EstanciaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            self.session.rollback()
            raise EstanciaError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


class ServicioEstancia:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _vehiculo(self, placa: str) -> Vehiculo:
        vehiculo = self.session.scalar(select(Vehiculo).where(Vehiculo.placa == placa))
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no encontrado.")
        return vehiculo

    def _operador(self, operador_id: int) -> Operador:
        operador = self.session.get(Operador, operador_id)
        if operador is None:
            raise EstanciaError(404, "Operador no encontrado.")
        return operador

    def _celda_libre(self, tipo: str) -> Celda | None:
        """Celda libre del tipo pedido que lleva más tiempo libre (las nunca usadas primero).

        FOR UPDATE SKIP LOCKED: si la otra portería está asignando una celda en este mismo
        instante, esa fila está bloqueada y se salta; cada portería toma una celda distinta.
        """
        abierta = exists().where(Estancia.celda_id == Celda.id, Estancia.salida.is_(None))
        descartadas: list[int] = []
        while True:
            consulta = (
                select(Celda).where(Celda.tipo == tipo, ~abierta)
                .order_by(Celda.disponible_desde.asc().nulls_first(), Celda.codigo)
                .limit(1).with_for_update(skip_locked=True)
            )
            if descartadas:
                consulta = consulta.where(Celda.id.not_in(descartadas))
            celda = self.session.scalar(consulta)
            if celda is None:
                return None
            # Con el bloqueo ya tomado se vuelve a mirar: la otra portería pudo ocuparla y
            # confirmar justo antes de que la bloqueáramos.
            if self.session.scalar(select(Estancia.id).where(
                Estancia.celda_id == celda.id, Estancia.salida.is_(None)
            )) is None:
                return celda
            descartadas.append(celda.id)

    def _movimiento(self, estancia: Estancia, vehiculo: Vehiculo, celda: Celda) -> MovimientoRespuesta:
        segundos = permanencia_segundos(estancia.entrada, estancia.salida) if estancia.salida else None
        return MovimientoRespuesta(
            **EstanciaRespuesta.model_validate(estancia).model_dump(),
            placa=vehiculo.placa, celda=CeldaRespuesta.model_validate(celda),
            duracion_segundos=segundos,
            permanencia=formatear_permanencia(segundos) if segundos is not None else None,
        )

    @transaccion
    def entrada(self, data: EntradaCrear) -> MovimientoRespuesta:
        # FOR SHARE: mientras entra, nadie puede cambiar el tipo del vehículo (PATCH usa FOR UPDATE).
        vehiculo = self.session.scalar(
            select(Vehiculo).where(Vehiculo.placa == data.placa).with_for_update(read=True)
        )
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no encontrado.")
        operador = self._operador(data.operador_id)
        hoy = hoy_bogota()
        # Misma regla que app.domain.reglas.mensualidad_vigente: inicio <= hoy <= fin.
        if not self.session.scalar(select(exists().where(
            Mensualidad.vehiculo_id == vehiculo.id, Mensualidad.fecha_inicio <= hoy, Mensualidad.fecha_fin >= hoy
        ))):
            raise EstanciaError(409, "El vehículo no tiene mensualidad vigente. No puede ingresar.")
        if self.session.scalar(select(Estancia.id).where(
            Estancia.vehiculo_id == vehiculo.id, Estancia.salida.is_(None)
        )) is not None:
            raise EstanciaError(409, "El vehículo ya está dentro.")
        tipo = tipo_celda_para(vehiculo.tipo)
        celda = self._celda_libre(tipo)
        if celda is None:
            raise EstanciaError(409, f"No hay celdas disponibles para {'motos' if tipo == 'MOTO' else 'carros'}.")
        estancia = Estancia(vehiculo_id=vehiculo.id, celda_id=celda.id,
                            operador_entrada_id=operador.id, entrada=datetime.now(timezone.utc))
        self.session.add(estancia)
        # Los índices únicos siguen siendo la última barrera ante dos entradas del mismo vehículo.
        self.session.flush()
        return self._movimiento(estancia, vehiculo, celda)

    @transaccion
    def salida(self, data: SalidaCrear) -> MovimientoRespuesta:
        vehiculo = self._vehiculo(data.placa)
        operador = self._operador(data.operador_id)
        # PostgreSQL vuelve a evaluar salida IS NULL tras esperar el bloqueo.
        estancia = self.session.scalar(select(Estancia).where(
            Estancia.vehiculo_id == vehiculo.id, Estancia.salida.is_(None)
        ).with_for_update())
        if estancia is None:
            raise EstanciaError(409, "El vehículo no tiene una estancia abierta.")
        try:
            estancia.cerrar(datetime.now(timezone.utc), operador)
        except ValueError:
            raise EstanciaError(409, "No se puede cerrar la estancia con su estado o fecha actuales.") from None
        # La celda queda libre desde ahora: pasa al final de la fila de asignación.
        estancia.celda.disponible_desde = estancia.salida
        self.session.flush()
        return self._movimiento(estancia, vehiculo, estancia.celda)

    @transaccion
    def consultar(self, placa: str) -> EstadoVehiculoRespuesta:
        placa = required_text(placa, "placa").upper()
        # Una sola consulta da un estado consistente de vehículo, estancia y celda.
        row = self.session.execute(select(Vehiculo, Estancia, Celda).outerjoin(
            Estancia, and_(Estancia.vehiculo_id == Vehiculo.id, Estancia.salida.is_(None))
        ).outerjoin(Celda, Celda.id == Estancia.celda_id).where(Vehiculo.placa == placa)).one_or_none()
        if row is None:
            raise EstanciaError(404, "Vehículo no encontrado.")
        vehiculo, estancia, celda = row
        abierta = None
        if estancia is not None:
            abierta = EstanciaAbiertaRespuesta(
                **EstanciaRespuesta.model_validate(estancia).model_dump(),
                celda=CeldaRespuesta.model_validate(celda),
            )
        return EstadoVehiculoRespuesta(vehiculo=VehiculoRespuesta.model_validate(vehiculo),
                                       esta_dentro=estancia is not None, estancia=abierta)
