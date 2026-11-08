from pydantic import BaseModel, ConfigDict


class OperadorRespuesta(BaseModel):
    """La persona. Iteración 2: solo lectura (se crea con su cuenta) y el teléfono es opcional."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    telefono: str | None


class OperadoresPagina(BaseModel):
    items: list[OperadorRespuesta]
    total: int
    offset: int
    limit: int
