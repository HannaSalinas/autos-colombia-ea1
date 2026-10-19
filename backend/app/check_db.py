"""Comprobación de conexión sin DDL ni cambios de datos."""

import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import ConfigurationError, load_database_settings
from app.database import create_database_engine


def main() -> int:
    engine = None
    try:
        engine = create_database_engine(load_database_settings())
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
        if result != 1:
            print("La comprobación no devolvió el resultado esperado.", file=sys.stderr)
            return 1
        print("Conexión a PostgreSQL verificada: SELECT 1 correcto.")
        return 0
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (SQLAlchemyError, OSError, ValueError):
        # Los errores del driver pueden incluir credenciales o datos de conexión.
        print(
            "No se pudo conectar a PostgreSQL. Revisa que el servicio esté iniciado "
            "y que DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD sean correctos. "
            "La base de datos y el usuario deben existir.",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
