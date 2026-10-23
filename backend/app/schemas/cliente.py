from pydantic import BaseModel, ConfigDict


class ClienteRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    documento: str
    nombre: str
    telefono: str
    correo: str | None


class ClientesPagina(BaseModel):
    items: list[ClienteRespuesta]
    total: int
    offset: int
    limit: int
