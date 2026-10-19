"""Alembic reutiliza la configuración del backend; offline no requiere credenciales."""

from alembic import context
from alembic.util import CommandError
from sqlalchemy.exc import SQLAlchemyError

from app.config import ConfigurationError, load_database_settings
from app.database import create_database_engine
from app.models import Base


def run_migrations_offline() -> None:
    context.configure(
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = None
    try:
        engine = create_database_engine(load_database_settings())
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    except ConfigurationError as error:
        raise CommandError(str(error)) from None
    except (SQLAlchemyError, OSError, ValueError):
        raise CommandError(
            "No se pudo completar la operación de Alembic. Revisa la conexión, "
            "los permisos y el estado del esquema; no se muestran detalles privados."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
