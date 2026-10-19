# Autos Colombia

Proyecto con backend en Python y FastAPI y frontend en Angular con TypeScript.
El frontend utiliza componentes standalone, enrutamiento, CSS y comprobación
estricta de TypeScript y plantillas.

## Requisitos en Windows

Versiones verificadas en este equipo:

| Herramienta | Versión |
| --- | --- |
| Python | 3.13.16 |
| pip | 26.2.1 |
| Node.js | 24.22.0 |
| npm | 11.7.0 |
| Git | 2.45.2.windows.1 |
| Angular y Angular CLI locales | 22.2.3 |
| TypeScript local | 6.0.3 |

Utiliza Python 3.13 y una versión de Node.js de la rama 24 igual o superior a
24.15.0. Abre una terminal nueva después de instalar herramientas o cambiar PATH.
Comprueba las herramientas desde PowerShell:

```powershell
py -3.13 --version
py -3.13 -m pip --version
node --version
npm.cmd --version
git --version
Get-Command python, pip, node, npm.cmd, git | Select-Object Name, Source
```

Los comandos siguientes usan la ruta actual de este equipo. Si mueves o clonas
el proyecto en otra ubicación, sustituye la ruta en los comandos `Set-Location`.
Las comillas permiten trabajar con los espacios y acentos del nombre de carpeta.

## Estructura

```text
AutosColombia/
├── README.md
├── .gitignore
├── backend/
│   ├── .venv/                 # Entorno local, excluido de Git
│   ├── app/main.py            # Aplicación FastAPI y GET /health
│   ├── tests/test_health.py   # Prueba del endpoint
│   └── requirements.txt       # Versiones exactas, incluidas las transitivas
└── frontend/
    ├── src/app/               # Componentes y rutas Angular
    ├── angular.json
    ├── tsconfig.json
    ├── package.json
    └── package-lock.json      # Versiones resueltas de las dependencias
```

## Instalar las dependencias

Ejecuta esta preparación antes de iniciar los servidores. Necesitas acceso a
Internet para descargar paquetes de PyPI y npm.

### Backend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Si `.venv` ya existe y funciona, omite el comando de creación. Los comandos usan
directamente su intérprete: no hace falta activar el entorno ni cambiar la
política de ejecución de PowerShell. `requirements.txt` fija las versiones de las
dependencias de ejecución y pruebas.

### Frontend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd ci
npm.cmd ls @angular/core @angular/cli typescript --depth=0
```

`npm ci` instala las versiones de `package-lock.json` y reconstruye
`node_modules`. Conserva `package-lock.json` en el repositorio; no lo borres para
reinstalar. Se utiliza `npm.cmd` para evitar depender de la ejecución de scripts
`.ps1` en PowerShell.

El proyecto se generó con `npx @angular/cli@22`. Los scripts `npm` de este proyecto
utilizan Angular CLI y TypeScript locales. No necesitas instalar ni actualizar
ninguna de estas herramientas globalmente.

## Verificar antes de ejecutar

### Pruebas y dependencias del backend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado esperado: dependencias sin conflictos y todas las pruebas aprobadas. La prueba de salud
verifica HTTP 200, el tipo de contenido JSON y el cuerpo `{"status": "ok"}` de
`GET /health`. No necesita un servidor iniciado. Las dependencias actuales pueden
emitir un aviso de deprecación de Starlette sobre `httpx`; no es un fallo de la prueba.

### Configurar y verificar PostgreSQL local

La configuración se documenta en [backend/README.md](backend/README.md#postgresql-local).
Completa `DB_NAME`, `DB_USER` y `DB_PASSWORD` en `backend/.env` y confirma
`DB_HOST`, `DB_PORT` y `DB_CONNECT_TIMEOUT`. La plantilla `backend/.env.example`
contiene valores de ejemplo; `.env` queda excluido de Git.

Desde la raíz del proyecto:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\check_db.py
```

El comando comprueba `SELECT 1` sin modificar tablas y solo informa éxito si la
conexión funciona. Las pruebas automatizadas no requieren PostgreSQL y no
sustituyen esta comprobación real. `/health` conserva su respuesta aunque falte
la configuración de PostgreSQL.

### Compilación y pruebas del frontend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd run build
npm.cmd test -- --watch=false
```

Resultado esperado: compilación correcta y **6 pruebas aprobadas**. La salida de
compilación queda en `frontend/dist/frontend`. Estas pruebas tampoco requieren
que el servidor de desarrollo esté iniciado.

## Ejecutar en dos terminales de PowerShell

Abre dos ventanas o pestañas de PowerShell. Cada servidor ocupa su terminal hasta
que lo detengas. Mantén ambas abiertas mientras desarrollas.

### Terminal 1: backend, puerto 8000

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Salud de la API: <http://127.0.0.1:8000/health>
- Documentación interactiva: <http://127.0.0.1:8000/docs>

`--reload` reinicia la API cuando cambias el código del backend.

### Terminal 2: comprobar la API e iniciar el frontend, puerto 4200

Cuando la terminal 1 indique que la API está lista, ejecuta lo siguiente en la
terminal 2. La comprobación HTTP se hace antes de iniciar Angular, para que no
necesites una tercera terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
$healthResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing
$healthResponse.StatusCode
$healthResponse.Content
if ($healthResponse.StatusCode -ne 200 -or ($healthResponse.Content | ConvertFrom-Json).status -ne 'ok') {
    throw 'La comprobación de salud del backend falló.'
}
npm.cmd start -- --host 127.0.0.1 --port 4200
```

La comprobación muestra `200` y `{"status":"ok"}`. Cuando Angular termine de
compilar, abre <http://127.0.0.1:4200> en el navegador. Verás la pantalla de bienvenida
de Autos Colombia. Al cargar, la pantalla consulta `GET /health` mediante
`HttpClient` y muestra “Comprobando conexión…”, “Servicio disponible” o
“No se pudo conectar con el servicio”. Una respuesta distinta de `{"status":"ok"}`,
un error HTTP o de red, o una espera superior a 5 segundos muestran el error.
La comprobación se realiza una vez al cargar: recarga la página para repetirla.
Angular actualiza la página al guardar cambios.

El proxy de desarrollo de `frontend/proxy.conf.json`, activado en `angular.json`,
redirige `/health` a `http://127.0.0.1:8000`. El navegador hace la solicitud al
mismo origen de Angular, por lo que no se necesita habilitar CORS en FastAPI.
Reinicia `npm.cmd start` si cambias el proxy. Este proxy solo funciona con el
servidor de desarrollo; en producción se debe configurar el servidor web para
redirigir `/health` al backend.

Para comprobar el proxy con ambos servidores activos, abre una terminal adicional:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:4200/health'
```

El resultado debe mostrar `status` con valor `ok`.

Para detener ambos servidores, pulsa **Ctrl+C en cada terminal**. Si Windows
pregunta si deseas terminar el trabajo por lotes, confirma. Si un puerto ya está
ocupado, detén primero la instancia anterior del servidor antes de volver a iniciarlo.
