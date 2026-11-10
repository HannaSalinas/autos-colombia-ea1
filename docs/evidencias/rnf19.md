# Evidencia de RNF-19: tiempo de respuesta medido

Medición automatizada con `scripts/medir_rnf19.py` el 2026-11-09 21:32 (hora de Bogotá), contra el
sistema levantado con Docker Compose sobre una base limpia, a través de `http://localhost:4200`.
Percentil 95 por rango más cercano. Los tiempos incluyen la red local, nginx, la API y PostgreSQL.

## Equipo

| Característica | Valor |
| --- | --- |
| Procesador | Intel(R) Celeron(R) N4020 CPU @ 1.10GHz |
| Núcleos lógicos | 2 |
| Memoria RAM | 7.5 GiB |
| Sistema operativo | Linux 7.0.0-42-generic |
| Docker | Docker version 29.9.2, build a82e528 |
| Docker Compose | 5.6.1 |
| Commit medido | 62bcd05 |

## Resultados

| Operación | Simultáneas | Muestras | Mediana (ms) | p95 (ms) | Máximo (ms) | Límite p95 (ms) | ¿Cumple? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Crear cuenta | 4 | 40 | 791 | 1215 | 1223 | 1000 | **NO CUMPLE** |
| Listar y buscar cuentas | 4 | 40 | 57 | 129 | 131 | 1000 | Sí |
| Detalle de cuenta | 4 | 40 | 65 | 107 | 132 | 1000 | Sí |
| Desactivar cuenta | 4 | 40 | 379 | 612 | 780 | 1000 | Sí |
| Reactivar cuenta | 4 | 40 | 359 | 507 | 639 | 1000 | Sí |
| Crear celda | 4 | 40 | 404 | 579 | 595 | 1000 | Sí |
| Listar y filtrar celdas | 4 | 40 | 63 | 96 | 108 | 1000 | Sí |
| Editar celda | 4 | 40 | 328 | 544 | 555 | 1000 | Sí |
| Inhabilitar celda | 4 | 40 | 332 | 406 | 412 | 1000 | Sí |
| Rehabilitar celda | 4 | 40 | 345 | 699 | 708 | 1000 | Sí |
| Crear cuenta (sin simultaneidad, referencia) | 1 | 30 | 539 | 689 | 717 | — | Referencia |
| Iniciar sesión (sin simultaneidad) | 1 | 30 | 308 | 341 | 373 | 1000 | Sí |
| Iniciar sesión (4 simultáneos) | 4 | 30 | 769 | 1322 | 1342 | 2000 | Sí |

**Resultado global: RNF-19 NO SE CUMPLE por completo.** Cumplen 11 de 12 mediciones; no cumple: Crear cuenta con 4 simultáneas (p95 1215 ms > 1000 ms).

## Crear cuenta con 4 simultáneas

- **Resultado:** p95 1215 ms frente a un límite de 1000 ms (**no cumple**).
- **Causa:** crear una cuenta calcula el hash bcrypt de la contraseña con costo 12 (RNF-13), unos
  0,5 s de CPU por cuenta en este equipo. Con 4 creaciones a la vez en 2 núcleos, cada una espera
  a las demás. El costo **no se reduce**: es la protección de las contraseñas frente a ataques de
  fuerza bruta.
- **Contexto:** solo el Administrador crea cuentas, así que su uso real no es simultáneo. De una en
  una, crear cuenta tarda p95 689 ms (fila de referencia de la tabla).

## Escenarios y lectura de los resultados

- Gestión de cuentas y celdas con 4 solicitudes simultáneas (dos porterías y la administración):
  p95 ≤ 1 s por operación. Inicio de sesión sin simultaneidad: p95 ≤ 1 s. Inicio de sesión con 4
  ingresos simultáneos: p95 ≤ 2 s. El inicio de sesión también usa bcrypt y es lento a propósito.
- Las escrituras tardan unos 200 ms aun de una en una en este equipo (procesador de bajo consumo y
  confirmación en disco de PostgreSQL); con 4 simultáneas se reparten los 2 núcleos.
- Entre ejecuciones hay una variación de unos ±200 ms en las operaciones con bcrypt (por ejemplo,
  el inicio de sesión con 4 simultáneos dio 952, 1184 y 1322 ms en tres ejecuciones el 9-nov-2026).
  En un equipo con más núcleos los tiempos con simultaneidad bajan, pero la causa no cambia.

## Historial de la medición

Primera ejecución (9-nov-2026, commit `1eed2db`, mismo equipo y base limpia): fallaban dos
operaciones con 4 simultáneas.

| Operación (4 simultáneas) | p95 primera ejecución | Causa | Corrección | p95 después |
| --- | ---: | --- | --- | ---: |
| Desactivar cuenta | 1257 ms | Cada desactivación bloqueaba las filas de **todos** los administradores, aun cuando la cuenta era de un Operador: las 4 solicitudes se ponían en fila (una sola tarda unos 180 ms). Además, el bloqueo `FOR UPDATE` hacía esperar al INSERT de la auditoría, que referencia al actor con una llave foránea. | Commit `0aac065`: ese bloqueo solo se toma al desactivar a un administrador (que es lo que exige la regla del último administrador), y con `FOR NO KEY UPDATE`, que no frena a quien solo referencia la fila. | 404 ms (segunda ejecución) |
| Crear cuenta | 1219 ms | bcrypt de costo 12 (RNF-13) | Ninguna: el costo no se reduce por seguridad | 1290 ms (segunda ejecución) |

La segunda ejecución midió el código de `0aac065` antes de confirmarlo; por eso se repitió la
medición con el código ya versionado (resultados de arriba). En la segunda ejecución, crear
cuenta sin simultaneidad, medido aparte con el mismo método (20 muestras), dio p95 579 ms.

Datos crudos de esta ejecución: [`rnf19.csv`](rnf19.csv).
