from typing import Annotated

from pydantic import Field

# Ids enteros JSON positivos dentro del rango BIGINT (antes vivía en schemas/estancia.py).
Identificador = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]
