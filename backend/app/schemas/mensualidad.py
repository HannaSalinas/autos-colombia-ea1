from datetime import date

from pydantic import BaseModel


class MensualidadRespuesta(BaseModel):
    id: int
    vehiculo_id: int
    fecha_inicio: date
    fecha_fin: date
    vigente: bool
    # Iteración 3: comprobante y estado del pago que generó el periodo. None = periodo anterior, sin pago.
    comprobante: str | None = None
    pago_estado: str | None = None
