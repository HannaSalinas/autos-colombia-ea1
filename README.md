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
| **Nuestro** (Fase 2) | Celdas de tipo MOTO o CARRO con la fecha desde la que están libres (migración `0004`), asignación automática de celda al entrar, validación de mensualidad vigente, tiempo de permanencia al salir, 80 celdas y 2 operadores en las semillas, pantallas de Control de acceso y Celdas adaptadas, y pruebas de concurrencia de dos porterías. |
| **Nuestro** (Fase 3) | Corrección de la celda de una estancia abierta (solo hacia una celda libre y compatible, con motivo obligatorio y registro) y novedades del vehículo (rayón, golpe, objeto olvidado, otro), tablas `correccion_celda` y `novedad` (migración `0005`), componente Angular `estancia-acciones` dentro de Control de acceso y sus pruebas, incluida la de dos correcciones simultáneas. |
| **Nuestro** (Fase 4) | Reporte de ocupación (vehículos dentro y celdas libres por tipo), historial de estancias filtrable por placa y por días de Bogotá con paginación y detalle de novedades y correcciones, pantallas Ocupación e Historial, bloqueo del cambio de tipo de una celda ocupada y script de datos de demostración (`app/demo.py`). |

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
| Solo entran vehículos con mensualidad vigente | Servicio de estancias (409) |
| 80 celdas: C01–C70 de carro y M01–M10 de moto; automóvil y camioneta usan celda de carro | Semillas, CHECK `tipo IN ('MOTO','CARRO')` |
| El sistema asigna la celda: libre, del tipo correcto y la que lleva más tiempo libre (las nunca usadas primero) | `orden_de_asignacion` en el dominio y `ORDER BY disponible_desde NULLS FIRST, codigo` |
| Dos porterías a la vez nunca reciben la misma celda ni abren dos entradas del mismo vehículo | `SELECT … FOR UPDATE SKIP LOCKED` + índices únicos parciales del profesor |
| La celda queda ocupada hasta la salida; al salir se libera y se muestra la permanencia | Servicio de estancias (`disponible_desde`, `permanencia`) |
| Corregir la celda de una estancia **abierta**, solo hacia una celda **libre y compatible**, con **motivo obligatorio** (máx. 200 caracteres); queda registro con operador y hora del servidor | Servicio de estancias (409/422), tabla `correccion_celda`, CHECK de celda distinta y motivo |
| Novedades del vehículo asociadas a su estancia abierta (rayón, golpe, objeto olvidado, otro) | Tabla `novedad`; se consultan también después de la salida |
| El historial no se borra | FK `ON DELETE RESTRICT` en todas las tablas de movimientos |
| No se cambia el tipo de una celda ocupada | Servicio de celdas (409) |
| Reporte de ocupación: vehículos dentro (placa, tipo, celda, hora de entrada) y celdas libres por tipo | `GET /reportes/ocupacion`, pantalla Ocupación |
| Historial filtrable por placa y por rango de fechas (días de Bogotá sobre la hora de entrada) | `rango_bogota` en el dominio, `GET /reportes/historial`, pantalla Historial |

### API agregada

| Método y ruta | Respuesta |
| --- | --- |
| `GET /clientes?offset&limit` | Clientes paginados (solo lectura) |
| `GET /clientes/{id}` | Documento, nombre, teléfono y correo (opcional) |
| `GET /clientes/{id}/vehiculos` | Vehículos del cliente con estado de mensualidad |
| `GET /vehiculos/{id}/mensualidades` | Mensualidades del vehículo y si cada una está vigente |

Las respuestas de `/vehiculos` ahora incluyen `cliente_id`, `cliente_nombre`,
`mensualidad_vigente`, `mensualidad_hasta` (fecha en que vence o venció) y
`mensualidad_proxima` (inicio de una mensualidad que todavía no empieza).

**Cambio de contrato (Fase 2):** `POST /estancias/entrada` recibe solo `placa` y
`operador_id`; ya no acepta `celda_id`. La entrada y la salida responden además con
`placa`, `celda` (código y tipo asignados) y, al salir, `duracion_segundos` y
`permanencia` (por ejemplo `"2 h 15 min"`). Errores nuevos de entrada (409): sin
mensualidad vigente y sin celdas disponibles del tipo del vehículo.

Fase 3:

| Método y ruta | Respuesta |
| --- | --- |
| `GET /estancias/{id}/celdas-disponibles` | Celdas libres y compatibles con el vehículo (estancia abierta) |
| `POST /estancias/{id}/correccion-celda` | `celda_id`, `operador_id`, `motivo` → 201 con celda anterior y nueva |
| `GET /estancias/{id}/correcciones` | Registro de correcciones de la estancia |
| `POST /estancias/{id}/novedades` | `tipo` (`RAYON`, `GOLPE`, `OBJETO_OLVIDADO`, `OTRO`), `descripcion`, `operador_id` → 201 |
| `GET /estancias/{id}/novedades` | Novedades de la estancia (abierta o cerrada) |

Errores: 404 (estancia, celda u operador inexistente), 409 (estancia cerrada, celda
ocupada, incompatible o la misma) y 422 (motivo o descripción vacíos o muy largos).

Fase 4:

| Método y ruta | Respuesta |
| --- | --- |
| `GET /reportes/ocupacion` | `celdas` (total, ocupadas y libres por tipo) y `dentro` (placa, tipo, celda, entrada, operador, tiempo) |
| `GET /reportes/historial?placa&desde&hasta&offset&limit` | Estancias de la más reciente a la más antigua, con permanencia, operadores y cantidad de novedades y correcciones. `desde`/`hasta` son días `AAAA-MM-DD` de Bogotá, incluidos; `desde > hasta` → 422 |

### Datos de demostración para el historial y el reporte

Aparte de las semillas existe `app/demo.py`, que **no se ejecuta al arrancar**. Crea
estancias cerradas de los últimos 7 días (varias por placa, solo en días con mensualidad
vigente, con correcciones y novedades) y 5 vehículos dentro. Nunca pone dos vehículos en
la misma celda al mismo tiempo. Solo corre sobre una base sin estancias:

```bash
docker compose exec backend python -m app.demo     # con Docker
backend/.venv/bin/python -m app.demo               # sin Docker (después de app.seed)
```

Para volver a la base limpia (solo semillas), borra el volumen y levanta de nuevo:

```bash
docker compose down -v && docker compose up -d
``` Crear y
editar clientes es de la Iteración 2; registrar pagos, de la Iteración 3.

### Datos de demostración

Al arrancar con Docker se ejecuta `python -m app.seed`, que **no duplica** registros
si se repite. Crea las 80 celdas (C01–C70 carro, M01–M10 moto), los operadores
"Marta Úsuga (Portería 1)" y "Diego Arango (Portería 2)" y estos vehículos. Los datos son ficticios y las fechas se calculan a partir del día de
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
demostración. Las de concurrencia (`test_estancias_postgres.py`) además se omiten
solas si la base ya tiene celdas, porque la asignación elige entre todas las libres.

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
- Fase 2, backend: `models.py` (`Celda.tipo` MOTO o CARRO y `disponible_desde`),
  `schemas/celda.py` (tipo de lista fija), `schemas/estancia.py` (entrada sin `celda_id`,
  respuesta `MovimientoRespuesta`), `services/estancia.py` (asignación automática,
  mensualidad vigente, liberación de la celda y permanencia) y `routers/estancias.py`.
- Fase 2, pruebas del profesor: `test_estancias_postgres.py` se **reescribió** con la misma
  técnica (datos confirmados, limpieza por id y barreras) para el nuevo contrato: mismo
  vehículo en dos porterías, dos vehículos con celdas distintas, una sola celda libre y dos
  salidas. `test_estancias_api.py`, `test_celdas_postgres.py` y `test_models.py` usan los
  tipos MOTO o CARRO y la entrada sin celda.
- Fase 3, backend: `models.py` (`CorreccionCelda`, `Novedad`), `schemas/estancia.py`,
  `services/estancia.py` y `routers/estancias.py` (rutas nuevas bajo `/estancias/{id}`).
  `tests/conftest.py` (nuestro) usa `expire_on_commit=False` para preparar datos con rollback.
- Fase 3, frontend: `control-acceso/*` muestra el componente nuevo `estancia-acciones` cuando el
  vehículo está dentro; la etiqueta del operador de consulta pasó a "Operador (salida,
  corrección o novedad)".
- Fase 4: `services/celda.py` (bloqueo del cambio de tipo de una celda ocupada) y en el
  frontend `celdas/celdas.ts` (muestra ese mensaje junto al tipo), `app.routes.ts` y `app.html`
  (pantallas Ocupación e Historial en `/consultas/…`), `proxy.conf.json` (`/reportes/**`).
- Fase 2, frontend: `control-acceso/*` (sin selector de celda, celda asignada y permanencia),
  `celdas/*` y `models/celda.ts` (tipo MOTO o CARRO), `models/estancia.ts` y
  `services/estancias.service.ts`.
- Frontend: `models/vehiculo.ts`, `vehiculos/vehiculos.ts`, `.html`, `.css` y `.spec.ts`
  (selector de cliente, validaciones y columna de mensualidad) y `proxy.conf.json` (`/clientes`).
