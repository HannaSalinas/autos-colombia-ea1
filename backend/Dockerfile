# Imagen del backend: misma versión de Python que el equipo de desarrollo (3.12).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Bogota

# La carpeta se llama backend, igual que en el repositorio (una prueba lo comprueba).
WORKDIR /backend

# Primero las dependencias: Docker reutiliza esta capa si solo cambia el código.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Aplica las migraciones pendientes y luego inicia la API.
CMD ["sh", "-c", "python -m alembic -c alembic.ini upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
