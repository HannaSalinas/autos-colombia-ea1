from datetime import date

from pydantic import BaseModel


class MensualidadRespuesta(BaseModel):
    id: int
    vehiculo_id: int
    fecha_inicio: date
    fecha_fin: date
    vigente: bool
