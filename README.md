# Autos Colombia — EA1, Iteración 1: entrada y salida de vehículos

Proyecto del curso **Ingeniería de Software (IU Digital)**. Sistema para el parqueadero
"Autos Colombia": clientes con mensualidad por vehículo, entrada con asignación automática
de celda, salida con tiempo de permanencia, corrección de celda, novedades, reporte de
ocupación e historial.

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy · Alembic · PostgreSQL 17.
- **Frontend:** Angular 22 · TypeScript, servido por nginx.
- **Todo se levanta con un solo comando** usando Docker Compose.

> **Basado en el proyecto del profesor Reinaldo Rojas**
> (<https://github.com/ReinaldoRojas/AutosColombia>). Ver [Crédito](#crédito-qué-viene-del-profesor-y-qué-agregamos).

## Contenido

1. [Inicio rápido](#inicio-rápido)
2. [Guion de demostración (HU-01 a HU-14)](#guion-de-demostración-hu-01-a-hu-14)
3. [Reglas implementadas](#reglas-implementadas)
4. [API](#api)
5. [Datos de demostración](#datos-de-demostración)
6. [Pruebas](#pruebas)
7. [Arquitectura y estructura](#arquitectura-y-estructura)
8. [Instalación sin Docker](#instalación-sin-docker)
9. [Crédito: qué viene del profesor y qué agregamos](#crédito-qué-viene-del-profesor-y-qué-agregamos)
10. [Decisiones y supuestos](#decisiones-y-supuestos)

## Inicio rápido

Requisitos: Docker 29 y Docker Compose v5 (verificado en Ubuntu con 29.9 / v5.6).

```bash
git clone https://github.com/HannaSalinas/autos-colombia-ea1.git
cd autos-colombia-ea1
docker compose up --build
```

| Qué | Dirección |
| --- | --- |
| Aplicación | <http://localhost:4200> |
| Documentación interactiva de la API | <http://localhost:8000/docs> |
| Salud de la API | <http://localhost:8000/health> |

Al arrancar, el backend aplica las migraciones (`alembic upgrade head`) y carga las
**semillas** (`python -m app.seed`): 80 celdas, 2 operadores, 6 clientes, 9 vehículos y sus
mensualidades. Las semillas no se duplican si se reinicia.

```bash
docker compose up --build -d                    # en segundo plano
docker compose logs -f backend                  # registro del backend
docker compose exec backend python -m app.demo  # (opcional) historial de 7 días para capturas
docker compose down                             # detener (conserva los datos)
docker compose down -v                          # detener y BORRAR la base (vuelve a quedar limpia al levantar)
```

## Guion de demostración (HU-01 a HU-14)

Empieza con la **base limpia** (solo semillas), para que las celdas asignadas coincidan
con las de este guion:

```bash
docker compose down -v && docker compose up --build -d
```

Los dos operadores son **Marta Úsuga (Portería 1)** y **Diego Arango (Portería 2)**.
Las fechas se muestran en hora de Bogotá y las asigna el servidor.

> Las historias se numeran en el orden de los requerimientos del cliente dados en clase.
> Si el documento del curso usa otra numeración, basta con reordenar esta tabla.

| HU | Historia | Dónde se ve |
| --- | --- | --- |
| HU-01 | Solo entran vehículos con mensualidad vigente (de fecha a fecha) | Vehículos, Control de acceso |
| HU-02 | Vehículos registrados y asociados a su cliente (uno o varios por cliente) | Vehículos, `/docs` |
| HU-03 | Tipos de vehículo moto y carro (automóvil, camioneta); no se reciben camiones | Vehículos, `/docs` |
| HU-04 | 80 celdas: 70 de carro y 10 de moto | Celdas, Ocupación |
| HU-05 | Asignación automática de una celda libre del tipo correcto, repartiendo el uso | Control de acceso |
| HU-06 | Dos porterías a la vez sin repetir celda ni abrir dos entradas del mismo vehículo | Dos ventanas, pruebas de concurrencia |
| HU-07 | La celda queda ocupada hasta la salida; al salir se libera | Control de acceso, Ocupación |
| HU-08 | Corrección de la celda de una estancia abierta, con registro y motivo | Control de acceso |
| HU-09 | Novedades del vehículo asociadas a su estancia | Control de acceso, Historial |
| HU-10 | Reporte de ocupación | Ocupación |
| HU-11 | Historial filtrable por placa y por rango de fechas | Historial |
| HU-12 | Tiempo de permanencia al registrar la salida | Control de acceso, Historial |
| HU-13 | Hora del servidor y operador en cada movimiento; el historial no se borra | Historial, `/docs` |
| HU-14 | Validaciones de placa (ABC123 / ABC12D) y modelo (1900 … año actual + 1) | Vehículos |

### HU-01 · Mensualidad vigente

1. Abre **Vehículos**. La columna *Mensualidad* muestra cada caso:
   - ABC123: "Vigente hasta …".
   - GHI789: vigente hasta **hoy** (vence hoy y todavía puede entrar).
   - DEF456: "Vencida el …".
   - PQR98B: "Empieza el …" (mañana).
   - MNO654: "Sin mensualidad".
2. En **Control de acceso → Registrar entrada**, con Marta Úsuga, intenta `DEF456`, `PQR98B`
   y `MNO654`. Las tres se rechazan con "El vehículo no tiene mensualidad vigente".
3. Fecha a fecha: en `/docs`, `GET /vehiculos/6/mensualidades` (JKL321) muestra una
   renovación en la que cada periodo termina el mismo día del mes siguiente. Los casos de
   31 de enero → 28/29 de febrero están en `tests/test_reglas.py`.

### HU-02 · Vehículo asociado a su cliente

1. En **Vehículos → Nuevo vehículo** registra: placa `qwe-456`, marca Kia, modelo 2024,
   color Gris, tipo AUTOMOVIL, cliente **Paola Ríos**. Se guarda como `QWE456`.
2. Sin cliente no deja guardar ("Selecciona el cliente").
3. En `/docs`, `GET /clientes` y luego `GET /clientes/{id}/vehiculos` de Paola Ríos: ahora
   tiene dos vehículos (MNO654 y QWE456).

### HU-03 · Tipos de vehículo

1. El selector de tipo solo ofrece MOTO, AUTOMOVIL y CAMIONETA.
2. En `/docs`, `POST /vehiculos` con `"tipo": "CAMION"` responde **422**.

### HU-04 · 80 celdas

1. **Celdas** muestra 80 celdas: C01–C70 de tipo CARRO y M01–M10 de tipo MOTO. El tipo
   solo puede ser MOTO o CARRO.
2. **Ocupación** muestra "70 libres de 70" carros y "10 libres de 10" motos.

### HU-05 · Asignación automática

En **Control de acceso → Registrar entrada** (no hay selector de celda), con Marta Úsuga:

| Placa | Celda asignada |
| --- | --- |
| `abc-123` | **C01** (carro; la placa se normaliza a ABC123) |
| `KLM45D` | **M01** (moto) |
| `GHI789` | **C02** |

Regla: celda libre del tipo del vehículo; primero las nunca usadas y luego la que lleva
**más tiempo libre**. Se comprueba en HU-07.

### HU-06 · Dos porterías al mismo tiempo

1. Abre Control de acceso en **dos ventanas**: una con Marta (Portería 1) y otra con Diego
   (Portería 2).
2. Escribe `JKL321` en las dos y pulsa *Registrar entrada* en ambas. Una registra la entrada
   (celda **C03**) y la otra responde "El vehículo ya está dentro".
3. La carrera exacta se demuestra con pruebas que obligan a las dos solicitudes a llegar a
   la vez:
   - mismo vehículo;
   - dos vehículos que reciben celdas distintas;
   - una sola celda libre;
   - dos salidas;
   - dos correcciones hacia la misma celda.

   ```bash
   docker compose run --rm --build backend-tests sh -c \
     "python -m alembic -c alembic.ini upgrade head && python -m pytest -v tests/test_estancias_postgres.py"
   ```

### HU-07 · Celda ocupada hasta la salida

1. **Ocupación** muestra 4 vehículos dentro (ABC123 en C01, KLM45D en M01, GHI789 en C02 y
   JKL321 en C03).
2. En **Control de acceso → Consultar vehículo**, consulta `ABC123` con Diego Arango:
   aparece "Dentro · Celda C01". Pulsa **Confirmar salida**.
3. Registra la entrada de `STU852`. Recibe **C04**, que nunca se ha usado, y no C01, que
   acaba de quedar libre: así se reparte el uso.

### HU-08 · Corrección de celda

1. Consulta `GHI789` (está en C02). Debajo aparece **Corregir celda**, que solo lista celdas
   libres de carro.
2. Pulsa *Corregir celda* sin motivo: lo pide.
3. Elige **C10**, escribe el motivo "El conductor parqueó en la C10" y pulsa *Corregir celda*.
   La consulta pasa a "Celda C10" y la corrección queda listada (C02 → C10) con fecha y motivo.
4. En `/docs`, `POST /estancias/{id}/correccion-celda` hacia una celda de moto o hacia una
   ocupada responde **409** con el motivo.

### HU-09 · Novedades

Con GHI789 consultado, en **Novedades del vehículo** elige *Rayón*, escribe "Rayón en el
bómper trasero" y pulsa *Registrar novedad*. Aparece en la lista con fecha y hora.

### HU-10 · Reporte de ocupación

**Ocupación** muestra 4 vehículos dentro (KLM45D en M01, GHI789 en C10, JKL321 en C03 y
STU852 en C04) con hora de entrada, tiempo dentro y operador. Arriba aparecen **67 libres
de 70** carros y **9 libres de 10** motos.

### HU-11 · Historial

1. **Historial** muestra todas las estancias, de la más reciente a la más antigua.
2. Filtra por placa `abc-123`: aparece la estancia cerrada de ABC123.
3. Filtra por *Desde* y *Hasta* = hoy: aparecen las estancias de hoy. Si *Desde* es
   posterior a *Hasta*, no deja buscar.
4. En la fila de GHI789 pulsa el botón "1 nov. · 1 corr.": muestra la corrección C02 → C10
   y la novedad.

Para capturas con más datos, ver [Datos de demostración](#datos-de-demostración).

### HU-12 · Tiempo de permanencia

Consulta `GHI789` y pulsa **Confirmar salida**: se muestra en grande el **tiempo de
permanencia** (por ejemplo "12 min"). También aparece en la columna *Permanencia* del Historial.

### HU-13 · Trazabilidad e historial que no se borra

1. En **Historial** cada estancia muestra el operador de entrada y el de salida, y las horas
   asignadas por el servidor en hora de Bogotá. Las correcciones y novedades también guardan
   operador y hora.
2. En **Vehículos**, intenta eliminar ABC123: se rechaza porque tiene registros relacionados.
3. La API no tiene ninguna operación para borrar estancias, correcciones ni novedades, y la
   base usa `ON DELETE RESTRICT`.

### HU-14 · Validaciones de placa y modelo

En **Vehículos → Nuevo vehículo**:

| Datos | Resultado |
| --- | --- |
| Placa `ABC12D`, tipo AUTOMOVIL | Error: la placa de carro es 3 letras y 3 números |
| Placa `ZZZ111`, tipo MOTO | Error: la placa de moto es 3 letras, 2 números y 1 letra |
| Modelo `1899` o el año actual + 2 | Error de año |
| Placa ` xyz-98 a `, tipo MOTO, modelo del año actual + 1 | Se guarda como `XYZ98A` |

La misma regla se valida en el navegador, en la API (422) y en PostgreSQL (CHECK).

## Reglas implementadas

| Regla | Dónde se aplica |
| --- | --- |
| Placa sin espacios ni guiones y en mayúsculas (`abc-123` → `ABC123`) | `app/domain/reglas.py`, pantallas |
| Placa de carro `ABC123`; de moto `ABC12D` | Dominio, API (422), CHECK en PostgreSQL y pantalla |
| Modelo entre 1900 y el año actual + 1 (fecha de Bogotá) | Dominio, API (422), CHECK `>= 1900` y pantalla |
| Todo vehículo pertenece a un cliente; un cliente puede tener varios | FK `vehiculo.cliente_id` NOT NULL |
| No se puede cambiar el tipo de un vehículo que está dentro | Servicio de vehículos (409) |
| Mensualidad **por vehículo**, de fecha a fecha (31-ene → 28/29-feb); vigente si inicio ≤ hoy ≤ fin | Dominio y servicio de mensualidades |
| Solo entran vehículos con mensualidad vigente | Servicio de estancias (409) |
| 80 celdas: C01–C70 de carro y M01–M10 de moto; automóvil y camioneta usan celda de carro | Semillas, CHECK `tipo IN ('MOTO','CARRO')` |
| El sistema asigna la celda: libre, del tipo correcto y la que lleva más tiempo libre (las nunca usadas primero) | `orden_de_asignacion` en el dominio y `ORDER BY disponible_desde NULLS FIRST, codigo` |
| Dos porterías a la vez nunca reciben la misma celda ni abren dos entradas del mismo vehículo | `SELECT … FOR UPDATE SKIP LOCKED` + índices únicos parciales del profesor |
| La celda queda ocupada hasta la salida; al salir se libera y se muestra la permanencia | Servicio de estancias (`disponible_desde`, `permanencia`) |
| Corregir la celda de una estancia **abierta**, solo hacia una celda **libre y compatible**, con **motivo obligatorio** (máx. 200 caracteres) | Servicio de estancias (409/422), tabla `correccion_celda` |
| Novedades del vehículo (rayón, golpe, objeto olvidado, otro) en su estancia abierta | Tabla `novedad`; se consultan también después de la salida |
| No se cambia el tipo de una celda ocupada | Servicio de celdas (409) |
| Reporte de ocupación: vehículos dentro y celdas libres por tipo | `GET /reportes/ocupacion`, pantalla Ocupación |
| Historial filtrable por placa y por días de Bogotá (sobre la hora de entrada) | `rango_bogota` en el dominio, `GET /reportes/historial`, pantalla Historial |
| Cada movimiento guarda hora del servidor (UTC) y operador; se muestra en America/Bogota | Servicios y pantallas |
| El historial no se borra | Sin endpoints de borrado de movimientos; FK `ON DELETE RESTRICT` |

## API

Documentación interactiva completa en <http://localhost:8000/docs>. Rutas del profesor
(CRUD de `/vehiculos`, `/celdas` y `/operadores`, `/health`) y rutas agregadas o cambiadas:

| Método y ruta | Descripción |
| --- | --- |
| `GET /clientes`, `GET /clientes/{id}`, `GET /clientes/{id}/vehiculos` | Clientes (solo lectura) y sus vehículos con estado de mensualidad |
| `GET /vehiculos/{id}/mensualidades` | Mensualidades del vehículo y si cada una está vigente |
| `POST /estancias/entrada` | **Cambió:** recibe solo `placa` y `operador_id`; responde con la celda asignada |
| `POST /estancias/salida` | Responde además con `duracion_segundos` y `permanencia` ("2 h 15 min") |
| `GET /estancias/vehiculo/{placa}` | (Profesor) estado del vehículo: dentro o fuera y su celda |
| `GET /estancias/{id}/celdas-disponibles` | Celdas libres y compatibles para corregir |
| `POST /estancias/{id}/correccion-celda` | `celda_id`, `operador_id`, `motivo` → 201 |
| `GET /estancias/{id}/correcciones` | Correcciones de la estancia |
| `POST /estancias/{id}/novedades`, `GET /estancias/{id}/novedades` | `tipo` (`RAYON`, `GOLPE`, `OBJETO_OLVIDADO`, `OTRO`), `descripcion`, `operador_id` |
| `GET /reportes/ocupacion` | Celdas por tipo (total, ocupadas, libres) y vehículos dentro |
| `GET /reportes/historial?placa&desde&hasta&offset&limit` | Historial paginado; `desde`/`hasta` son días `AAAA-MM-DD` de Bogotá, incluidos |

Las respuestas de `/vehiculos` incluyen `cliente_id`, `cliente_nombre`,
`mensualidad_vigente`, `mensualidad_hasta` y `mensualidad_proxima`.

Códigos de error: **404** (referencia inexistente), **409** (conflicto con el estado:
vehículo ya dentro, sin mensualidad vigente, sin celdas libres, celda ocupada o
incompatible, estancia cerrada, cambio de tipo no permitido), **422** (datos inválidos) y
**503** (fallo de base de datos, con mensaje genérico).

## Datos de demostración

### Semillas (se cargan siempre al arrancar)

`backend/app/seed.py` crea las 80 celdas, los operadores "Marta Úsuga (Portería 1)" y
"Diego Arango (Portería 2)" y estos vehículos ficticios. Las fechas de las mensualidades se
calculan a partir de **hoy**, para que la demostración siempre tenga todos los casos:

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

### Historial de 7 días para capturas (opcional, NO se ejecuta al arrancar)

`backend/app/demo.py` crea estancias cerradas de los últimos 7 días y 5 vehículos dentro
(ABC123, KLM45D, GHI789, JKL321 y STU852):

- varias estancias por placa;
- solo en días en que el vehículo tenía mensualidad vigente;
- con correcciones y novedades;
- nunca dos vehículos en la misma celda al mismo tiempo.

Solo corre sobre una base **sin estancias**:

```bash
docker compose exec backend python -m app.demo       # con Docker
backend/.venv/bin/python -m app.demo                 # sin Docker (después de app.seed)
```

Para **volver a la base limpia** (solo semillas):

```bash
docker compose down -v && docker compose up -d
```

> Con los datos de demostración cargados, los 5 vehículos con mensualidad vigente ya están
> dentro. Para seguir el guion de arriba, usa la base limpia.

## Pruebas

```bash
docker compose run --rm --build backend-tests   # backend: unitarias + integración con PostgreSQL real
docker compose --profile test down -v           # limpia la base de pruebas
cd frontend && npm test -- --watch=false        # frontend (Vitest)
```

`backend-tests` usa un PostgreSQL **aparte** (`db-test`, en memoria): las pruebas nunca
tocan los datos de la demostración. Resultado al cerrar la iteración: **244 pruebas de
backend** y **58 de frontend** aprobadas.

| Tipo | Archivos | Qué comprueban |
| --- | --- | --- |
| Unitarias de reglas y valores límite | `tests/test_reglas.py` | Placa (formatos, normalización), modelo (1899/1900, año + 1/+ 2), mensualidad fecha a fecha (fin de mes, bisiesto, día anterior/inicio/fin/día siguiente), tipo de celda, orden de asignación, permanencia, rango de días de Bogotá (00:00 y 23:59:59) |
| Integración de endpoints | `tests/test_*_postgres.py`, `test_estancias_api.py` | Cada endpoint con PostgreSQL real, sus errores 404/409/422 y las restricciones de la base, dentro de transacciones que se revierten |
| Concurrencia | `tests/test_estancias_postgres.py` | Dos porterías a la vez: mismo vehículo, dos vehículos, una sola celda libre, dos salidas y dos correcciones hacia la misma celda |
| Esquema | `tests/test_models.py`, `test_estancia.py`, `test_esquema_postgres.py` | Migraciones iguales a los modelos y SQL de cada migración |
| Datos | `tests/test_seed_postgres.py`, `test_demo_postgres.py` | Semillas sin duplicados; datos de demostración que respetan las reglas |
| Frontend | `src/app/**/*.spec.ts` | Formularios, validaciones, llamadas HTTP y mensajes de cada pantalla |

## Arquitectura y estructura

Arquitectura por capas, igual que el proyecto base:

```text
Presentación   frontend/src/app/*            Angular: pantallas, formularios, llamadas HTTP
               backend/app/routers/*         FastAPI: rutas, sin lógica de negocio
Dominio        backend/app/domain/reglas.py  Reglas puras (sin BD): placa, modelo, mensualidad,
                                             tipo de celda, orden de asignación, permanencia, fechas
Servicios      backend/app/services/*        Casos de uso: transacciones, bloqueos, errores públicos
Persistencia   backend/app/models.py         SQLAlchemy + restricciones; migraciones Alembic 0001–0005
```

```text
AutosColombia/
├── docker-compose.yml          # (nuestro) db, backend, frontend, db-test, backend-tests
├── AGENTS.md                   # (profesor) guía original para Windows
├── docs/README-profesor.md     # (profesor) README original sin cambios
├── backend/
│   ├── Dockerfile              # (nuestro) migra, carga semillas e inicia la API
│   ├── app/
│   │   ├── domain/reglas.py    # (nuestro) reglas de negocio puras
│   │   ├── models.py           # (profesor + nuestro) Cliente, Mensualidad, CorreccionCelda, Novedad
│   │   ├── schemas/ services/ routers/
│   │   ├── seed.py             # (nuestro) semillas
│   │   └── demo.py             # (nuestro) datos de demostración opcionales
│   ├── migrations/versions/    # 0001–0002 del profesor; 0003–0005 nuestras
│   └── tests/
└── frontend/
    ├── Dockerfile              # (nuestro) compila Angular y lo sirve con nginx
    ├── nginx/default.conf      # (nuestro) proxy de la API dentro de Docker
    └── src/app/                # control-acceso, estancia-acciones, ocupacion, historial, vehiculos, celdas, …
```

Nginx hace dentro de Docker lo mismo que `frontend/proxy.conf.json` en desarrollo: el
navegador llama a `/vehiculos`, `/estancias`, `/reportes`, etc. en el mismo origen y nginx
lo reenvía al backend, así que no hace falta CORS. Las pantallas usan rutas `/gestion/…` y
`/consultas/…` para no chocar con las rutas de la API.

### Migraciones

| Revisión | Autor | Cambio |
| --- | --- | --- |
| 0001 | Profesor | `vehiculo`, `celda`, `operador` |
| 0002 | Profesor | `estancia` con índices únicos de estancias abiertas |
| 0003 | Nuestra | `cliente`, `mensualidad`, `vehiculo.cliente_id`, CHECK de placa según tipo y modelo ≥ 1900 |
| 0004 | Nuestra | `celda.tipo` MOTO o CARRO (`NOT VALID`) y `celda.disponible_desde` |
| 0005 | Nuestra | `correccion_celda` y `novedad` |

No se modificó ninguna migración existente.

## Instalación sin Docker

Verificado con Python 3.12.3 y Node 22.23.3 / npm 10.9.9. El proyecto del profesor indica
Python 3.13 y Node 24. Comprobamos que también funciona con Python 3.12 (todas las
dependencias se instalan y pasan las pruebas) y con Node 22 (Angular 22 acepta
`^22.22.3 || ^24.15.0`).

Necesitas un PostgreSQL. Lo más sencillo es levantar solo el de Docker con
`docker compose up -d db`.

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env        # edita DB_NAME, DB_USER y DB_PASSWORD
.venv/bin/python check_db.py   # comprueba la conexión (SELECT 1)
.venv/bin/python -m alembic -c alembic.ini upgrade head
.venv/bin/python -m app.seed
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Con el PostgreSQL de Docker, los valores de `.env` son `DB_NAME=autos_colombia`,
`DB_USER=autos` y `DB_PASSWORD=autos_local_dev`. Son credenciales **solo para desarrollo
local**, igual que las de `docker-compose.yml`. `.env` no se sube a git.

```bash
.venv/bin/python -m pytest -q                      # sin PostgreSQL (se omiten las de integración)
RUN_POSTGRES_TESTS=1 .venv/bin/python -m pytest -q # con PostgreSQL real
```

Con `RUN_POSTGRES_TESTS=1`, las pruebas escriben y limpian sus propios registros en la
base de `.env`. Las de concurrencia se omiten solas si la base ya tiene celdas, porque
la asignación elige entre todas las libres. Por eso conviene usar `backend-tests` de Docker.

### Frontend

```bash
cd frontend
npm ci
npm start -- --host 127.0.0.1 --port 4200   # http://127.0.0.1:4200 (con el backend iniciado)
npm test -- --watch=false
npm run build
```

## Crédito: qué viene del profesor y qué agregamos

Este proyecto **parte de la solución base publicada por el profesor Reinaldo Rojas** en
<https://github.com/ReinaldoRojas/AutosColombia>. Conservamos su historial de git (los dos
primeros commits son suyos) y su código. Su README original, escrito para
Windows/PowerShell, está **sin cambios** en [docs/README-profesor.md](docs/README-profesor.md),
y su guía `AGENTS.md` también se conserva.

| Origen | Contenido |
| --- | --- |
| **Profesor** | Estructura por capas (routers, schemas, services, models), configuración y conexión a PostgreSQL, modelos `Vehiculo`, `Celda`, `Operador` y `Estancia`, migraciones `0001` y `0002` (con los índices únicos de estancias abiertas), CRUD de vehículos, celdas y operadores, entrada, salida y consulta de estancias, pantallas Angular (Inicio, Vehículos, Celdas, Operadores, Control de acceso) y sus pruebas, incluida la técnica de pruebas de concurrencia con barreras. |
| **Nuestro** · Fase 0 | Adaptación a Linux, Dockerfiles, nginx, `docker-compose.yml` con base de pruebas desechable y este README. |
| **Nuestro** · Fase 1 | Capa de dominio, `Cliente` y `Mensualidad` (migración 0003), cliente obligatorio, validaciones de placa y modelo, API de clientes y mensualidades, semillas, selector de cliente y estado de mensualidad en Vehículos. |
| **Nuestro** · Fase 2 | Celdas MOTO o CARRO con `disponible_desde` (0004), asignación automática, mensualidad vigente al entrar, permanencia, 80 celdas y 2 operadores, Control de acceso sin selector de celda, pruebas de concurrencia del contrato nuevo. |
| **Nuestro** · Fase 3 | Corrección de celda y novedades (0005), componente `estancia-acciones`, prueba de correcciones simultáneas. |
| **Nuestro** · Fase 4 | Reporte de ocupación, historial filtrable, pantallas Ocupación e Historial, bloqueo del cambio de tipo de una celda ocupada, datos de demostración. |

### Cambios a archivos del profesor

| Archivo | Cambio y motivo |
| --- | --- |
| `README.md` | Se movió **sin cambios** a `docs/README-profesor.md`; este es el README nuevo. |
| `backend/app/models.py` | Modelos `Cliente`, `Mensualidad`, `CorreccionCelda` y `Novedad`. `Vehiculo`: `cliente_id`, CHECK de placa según tipo y modelo ≥ 1900, normalización sin espacios ni guiones (el mínimo del modelo pasó de 1 a 1900). `Celda`: tipo MOTO o CARRO y `disponible_desde`. |
| `backend/app/schemas/vehiculo.py` | `cliente_id` obligatorio, placa según tipo, modelo 1900 … año actual + 1; respuesta `VehiculoDetalle`. |
| `backend/app/schemas/celda.py` | El tipo pasó de texto libre a MOTO o CARRO; la respuesta no revalida (pueden existir celdas antiguas). |
| `backend/app/schemas/estancia.py` | Entrada sin `celda_id`; respuestas con celda y permanencia; corrección y novedad. `Identificador` se movió a `schemas/comun.py`. |
| `backend/app/services/vehiculo.py` | Cliente existente, placa válida con el tipo final en PATCH, bloqueo del cambio de tipo con el vehículo dentro. |
| `backend/app/services/celda.py` | Bloqueo del cambio de tipo de una celda ocupada. |
| `backend/app/services/estancia.py` | Asignación automática con `SKIP LOCKED`, mensualidad vigente, liberación de celda, permanencia, corrección de celda y novedades. |
| `backend/app/routers/vehiculos.py`, `routers/estancias.py`, `main.py` | Rutas nuevas y registro de los routers de clientes y reportes. |
| `backend/tests/test_estancias_postgres.py` | **Reescrita** con la misma técnica (datos confirmados, limpieza por id, barreras) para el contrato nuevo de entrada. |
| `backend/tests/test_vehiculos_postgres.py`, `test_operadores_postgres.py`, `test_celdas_postgres.py`, `test_estancias_api.py`, `test_models.py` | Exigen la revisión más reciente (antes `0001`/`0002`), crean un cliente y placas válidas, usan tipos MOTO o CARRO, entrada sin celda; `test_models.py` excluye de la comparación con `0001` lo agregado por `0003` y `0004`. |
| `frontend/src/app/control-acceso/*` | Sin selector de celda; celda asignada y permanencia; componente de corrección y novedades; etiqueta del operador. |
| `frontend/src/app/vehiculos/*`, `celdas/*` | Selector de cliente, validaciones, columna de mensualidad; tipo de celda MOTO o CARRO. |
| `frontend/src/app/models/*.ts`, `services/estancias.service.ts` | Contratos y llamadas nuevas. |
| `frontend/src/app/app.routes.ts`, `app.html`, `frontend/proxy.conf.json` | Pantallas Ocupación e Historial; rutas `/clientes` y `/reportes` en el proxy. |

## Decisiones y supuestos

- **Fuera de alcance de esta iteración:** login, roles y gestión de usuarios, así como la
  pantalla de gestión de clientes (Iteración 2); pagos y pantalla de mensualidades
  (Iteración 3). El operador se elige en cada formulario, como en el proyecto base.
- **Mensualidad:** por vehículo; vigente si inicio ≤ hoy ≤ fin, con "hoy" en Bogotá. La
  tarifa (carro o moto) no se guarda porque los pagos son de la Iteración 3.
- **Asignación de celda:** entre las celdas libres del tipo correcto, primero las nunca
  usadas y luego la que quedó libre hace más tiempo; si empatan, por código.
- **Concurrencia:** `FOR UPDATE SKIP LOCKED` al elegir la celda, una nueva comprobación con
  el bloqueo tomado, `FOR UPDATE` sobre la estancia al salir o corregir, y los índices únicos
  parciales del profesor como última barrera.
- **Fechas:** se guardan con zona horaria (UTC) y hora del servidor; nunca se aceptan fechas
  del cliente. Se muestran en America/Bogota. El filtro del historial usa días de Bogotá
  sobre la hora de entrada.
- **Restricciones nuevas sobre tablas existentes:** el tipo de celda usa `NOT VALID` para no
  romper celdas antiguas. La 0003 exige la tabla `vehiculo` vacía porque `cliente_id` es
  obligatorio; si hay vehículos sin dueño, se detiene con un mensaje claro.
- **Numeración HU-01 a HU-14:** sigue el orden de los requerimientos dados en clase.
