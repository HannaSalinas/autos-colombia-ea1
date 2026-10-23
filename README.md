# Autos Colombia — EA1, Iteración 1: entrada y salida de vehículos

Proyecto del curso **Ingeniería de Software (IU Digital)**. Sistema para el
parqueadero "Autos Colombia": registro de entradas y salidas, asignación de celdas
y consulta de ocupación.

Backend: Python 3.12 · FastAPI · SQLAlchemy · Alembic · PostgreSQL 17.
Frontend: Angular 22 · TypeScript. Todo se levanta con Docker Compose.

## Crédito: qué viene del profesor y qué agregamos

Este proyecto **parte de la solución base publicada por el profesor Reinaldo Rojas**
en <https://github.com/ReinaldoRojas/AutosColombia>. Conservamos su historial de
git (los dos primeros commits son suyos) y su código. Su README original, escrito
para Windows/PowerShell, está **sin cambios** en
[docs/README-profesor.md](docs/README-profesor.md). Su guía `AGENTS.md` también se
conserva tal cual.

| Origen | Contenido |
| --- | --- |
| **Profesor** | Estructura por capas (routers, schemas, services, models), configuración y conexión a PostgreSQL, modelos `Vehiculo`, `Celda`, `Operador` y `Estancia`, migraciones `0001` y `0002`, CRUD de vehículos, celdas y operadores, endpoints de entrada, salida y consulta de estancias, pantallas Angular (Inicio, Vehículos, Celdas, Operadores, Control de acceso) y sus pruebas. |
| **Nuestro** (Fase 0) | Adaptación a Linux, `Dockerfile` del backend y del frontend, `nginx` como proxy de la API, `docker-compose.yml` con base de pruebas desechable y este README. |
| **Nuestro** (Fase 1) | Capa de dominio `app/domain/reglas.py` (placa, modelo, mensualidad de fecha a fecha), modelos `Cliente` y `Mensualidad` con la migración `0003`, cliente obligatorio en cada vehículo, API de consulta de clientes y de mensualidades, semillas de demostración (`app/seed.py`), selector de cliente y estado de mensualidad en la pantalla de Vehículos, y sus pruebas. |

> La tabla se completa al cerrar cada fase de la iteración.

## Reglas implementadas (Iteración 1)

| Regla | Dónde se aplica |
| --- | --- |
| Placa sin espacios ni guiones y en mayúsculas (`abc-123` → `ABC123`) | `app/domain/reglas.py`, pantalla de Vehículos |
| Placa de carro `ABC123` (3 letras + 3 números); de moto `ABC12D` (3 letras + 2 números + 1 letra) | Dominio, API (422), CHECK en PostgreSQL y pantalla |
| Modelo entre 1900 y el año actual + 1 (fecha de Bogotá) | Dominio, API (422), CHECK `>= 1900` y pantalla |
| Todo vehículo pertenece a un cliente; un cliente puede tener varios | FK `vehiculo.cliente_id` NOT NULL |
| No se puede cambiar el tipo de un vehículo que está dentro | Servicio de vehículos (409) |
| Mensualidad **por vehículo**, de fecha a fecha (31-ene → 28/29-feb); vigente si inicio ≤ hoy ≤ fin | Dominio y servicio de mensualidades |

### API agregada

| Método y ruta | Respuesta |
| --- | --- |
| `GET /clientes?offset&limit` | Clientes paginados (solo lectura) |
| `GET /clientes/{id}` | Documento, nombre, teléfono y correo (opcional) |
| `GET /clientes/{id}/vehiculos` | Vehículos del cliente con estado de mensualidad |
| `GET /vehiculos/{id}/mensualidades` | Mensualidades del vehículo y si cada una está vigente |

Las respuestas de `/vehiculos` ahora incluyen `cliente_id`, `cliente_nombre`,
`mensualidad_vigente` y `mensualidad_hasta` (fecha en que vence o venció). Crear y
editar clientes es de la Iteración 2; registrar pagos, de la Iteración 3.

### Datos de demostración

Al arrancar con Docker se ejecuta `python -m app.seed`, que **no duplica** registros
si se repite. Los datos son ficticios y las fechas se calculan a partir del día de
hoy, para que la demostración siempre tenga todos los casos:

| Placa | Tipo | Cliente | Mensualidad |
| --- | --- | --- | --- |
| ABC123 | Automóvil | Laura Gómez | Vigente |
| KLM45D | Moto | Laura Gómez | Vigente |
| DEF456 | Camioneta | Carlos Pérez | Vencida hace 5 días |
| GHI789 | Automóvil | Ana Restrepo | Vence hoy (todavía puede entrar) |
| XYZ12A | Moto | Ana Restrepo | Vencida |
| JKL321 | Automóvil | Jorge Mesa | Renovada (dos periodos seguidos) |
| MNO654 | Camioneta | Paola Ríos | Nunca ha pagado |
| PQR98B | Moto | Andrés Cano | Empieza mañana (hoy no está vigente) |
| STU852 | Automóvil | Andrés Cano | Vigente |

Sin Docker, ejecuta las semillas después de las migraciones:
`.venv/bin/python -m app.seed`.

## Requisitos (Linux)

Verificado en Ubuntu con estas versiones:

| Herramienta | Versión |
| --- | --- |
| Docker / Docker Compose | 29.9 / v5.6 |
| Python (solo sin Docker) | 3.12.3 |
| Node.js / npm (solo sin Docker) | 22.23.3 / 10.9.9 |

El proyecto del profesor indica Python 3.13 y Node 24. Comprobamos que también
funciona con Python 3.12 (todas las dependencias de `requirements.txt` se instalan
y pasan las pruebas) y con Node 22: Angular 22 acepta `^22.22.3 || ^24.15.0`.

## Opción 1: todo con Docker (recomendada)

Desde la raíz del proyecto:

```bash
docker compose up --build
```

Este comando levanta tres contenedores:

- `db`: PostgreSQL 17, con los datos en el volumen `datos_postgres`.
- `backend`: al arrancar aplica las migraciones (`alembic upgrade head`) e inicia la API.
- `frontend`: Angular ya compilado, servido por nginx.

| Qué | Dirección |
| --- | --- |
| Aplicación | <http://localhost:4200> |
| Documentación de la API | <http://localhost:8000/docs> |
| Salud de la API | <http://localhost:8000/health> |

Comandos útiles:

```bash
docker compose up --build -d   # en segundo plano
docker compose logs -f backend # ver el registro del backend
docker compose down            # detener (conserva los datos)
docker compose down -v         # detener y BORRAR la base de datos
```

Nginx hace dentro de Docker lo mismo que `frontend/proxy.conf.json` en desarrollo:
el navegador llama a `/vehiculos`, `/estancias`, etc. en el mismo origen y nginx
lo reenvía al backend, así que no hace falta CORS.

### Pruebas con Docker

```bash
docker compose run --rm --build backend-tests      # backend (unitarias + PostgreSQL real)
docker compose --profile test down -v              # limpia la base de pruebas
```

`backend-tests` usa un PostgreSQL **aparte** (`db-test`) cuyos datos viven en
memoria. Las pruebas de integración y de concurrencia nunca tocan los datos de la
demostración.

## Opción 2: sin Docker

Necesitas un PostgreSQL disponible. Lo más sencillo es usar solo el de Docker
(`docker compose up -d db`), o uno instalado en el equipo con su base y su usuario.

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env        # luego edita DB_NAME, DB_USER y DB_PASSWORD
.venv/bin/python check_db.py   # comprueba la conexión (SELECT 1)
.venv/bin/python -m alembic -c alembic.ini upgrade head
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Con el PostgreSQL de Docker, los valores de `.env` son `DB_NAME=autos_colombia`,
`DB_USER=autos` y `DB_PASSWORD=autos_local_dev`. Son credenciales solo para
desarrollo local. `.env` no se sube a git.

Pruebas:

```bash
.venv/bin/python -m pytest -q                      # sin PostgreSQL (se omiten las de integración)
RUN_POSTGRES_TESTS=1 .venv/bin/python -m pytest -q # con PostgreSQL real
```

Las pruebas con `RUN_POSTGRES_TESTS=1` escriben y limpian sus propios registros
en la base configurada en `.env`. Para no mezclarlos con la demostración, es
preferible usar la opción con Docker.

### Frontend

En otra terminal, con el backend iniciado:

```bash
cd frontend
npm ci
npm start -- --host 127.0.0.1 --port 4200   # http://127.0.0.1:4200
npm test -- --watch=false                   # pruebas
npm run build                               # compilación
```

## Estructura

```text
AutosColombia/
├── docker-compose.yml        # (nuestro) db, backend, frontend, db-test, backend-tests
├── AGENTS.md                 # (profesor) guía original para Windows
├── docs/README-profesor.md   # (profesor) README original sin cambios
├── backend/
│   ├── Dockerfile            # (nuestro)
│   ├── app/                  # routers (presentación), services (dominio), models (persistencia)
│   ├── migrations/versions/  # Alembic: 0001 y 0002 del profesor; las nuevas son nuestras
│   └── tests/
└── frontend/
    ├── Dockerfile            # (nuestro) compila Angular y lo sirve con nginx
    ├── nginx/default.conf    # (nuestro) proxy de la API dentro de Docker
    └── src/app/              # pantallas, servicios y modelos de Angular
```

## Cambios a archivos del profesor

Aquí declaramos cada archivo del profesor que modifiquemos y por qué.

- `README.md` se movió sin cambios a `docs/README-profesor.md`.
- `backend/app/models.py`: modelos `Cliente` y `Mensualidad`; en `Vehiculo`, la columna
  `cliente_id`, los CHECK de formato de placa y modelo mínimo, y la normalización de placa
  sin espacios ni guiones. El mínimo del modelo pasó de 1 a 1900.
- `backend/app/schemas/vehiculo.py`: `cliente_id` obligatorio, placa según tipo, modelo
  1900…año actual + 1; respuesta `VehiculoDetalle` con cliente y mensualidad.
- `backend/app/services/vehiculo.py`: cliente existente, placa válida con el tipo final
  en PATCH y bloqueo del cambio de tipo con el vehículo dentro.
- `backend/app/routers/vehiculos.py`: respuesta detallada y `GET /vehiculos/{id}/mensualidades`.
- `backend/app/schemas/estancia.py`: `Identificador` se movió a `app/schemas/comun.py`.
- `backend/app/main.py`: registra el router de clientes.
- Pruebas del profesor ajustadas: `test_vehiculos_postgres.py`, `test_estancias_postgres.py`
  y `test_operadores_postgres.py` exigen la revisión más reciente (antes `0001`/`0002`) y
  crean un cliente y placas con formato válido; `test_models.py` excluye de la comparación
  con `0001` lo que agregó `0003`.
- `backend/Dockerfile` (nuestro) ejecuta las semillas al arrancar.
- Frontend: `models/vehiculo.ts`, `vehiculos/vehiculos.ts`, `.html`, `.css` y `.spec.ts`
  (selector de cliente, validaciones y columna de mensualidad) y `proxy.conf.json` (`/clientes`).
