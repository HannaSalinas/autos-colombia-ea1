# Frontend de Autos Colombia

Angular 22 con componentes standalone, TypeScript estricto, formularios reactivos y CSS.
Las dependencias son locales; conserva `package-lock.json` y usa `npm.cmd ci` al reinstalar.

## Iniciar en Windows (PowerShell)

Mantén el backend activo en otra terminal, como se explica en el [README principal](../README.md#ejecutar-en-dos-terminales-de-powershell).

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd ci
npm.cmd start -- --host 127.0.0.1 --port 4200
```

Abre <http://127.0.0.1:4200/gestion/vehiculos>. La navegación permite alternar entre
Inicio y Vehículos. Consulta el [uso de la pantalla](../README.md#pantalla-de-gestión-de-vehículos).

El proxy `proxy.conf.json` conecta `/health`, `/vehiculos` y `/vehiculos/**` con
FastAPI en `127.0.0.1:8000`. Reinicia el servidor de Angular si cambias ese archivo.
En producción, configura estas rutas de API en el servidor web; `ng build` no incluye un proxy.

## Verificar

```powershell
npm.cmd run build
npm.cmd test -- --watch=false
```

La compilación se guarda en `dist/frontend`. Las pruebas usan respuestas simuladas y
no modifican PostgreSQL. El CRUD local se comprobó por HTTP a través del proxy con
un registro nuevo, eliminado al terminar. La revisión visual en navegador quedó
pendiente por un límite de uso de la herramienta de navegador.
