"""Tarifas mensuales por tipo de vehículo (D12, RF-32, RF-33). Nunca se editan ni se borran (RNF-24)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tarifa


def tarifa_vigente(session: Session, tipo_vehiculo: str) -> Tarifa | None:
    """La vigente es la más reciente del tipo: cada cambio crea una tarifa nueva desde ese momento."""
    return session.scalar(select(Tarifa).where(Tarifa.tipo_vehiculo == tipo_vehiculo)
                          .order_by(Tarifa.vigente_desde.desc(), Tarifa.id.desc()).limit(1))
