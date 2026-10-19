"""Motor y sesiones creados bajo demanda; importar la API no conecta a PostgreSQL."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session

from app.config import DatabaseSettings, load_database_settings


def create_database_engine(settings: DatabaseSettings) -> Engine:
    url = URL.create(
        "postgresql+psycopg",
        username=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.name,
    )
    return create_engine(
        url,
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.connect_timeout},
    )


@lru_cache
def get_engine() -> Engine:
    return create_database_engine(load_database_settings())


def get_session() -> Iterator[Session]:
    """Dependencia para futuros endpoints; no confirma transacciones automáticamente."""
    with Session(get_engine()) as session:
        yield session
