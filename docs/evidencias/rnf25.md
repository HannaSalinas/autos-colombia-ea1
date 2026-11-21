# Evidencia de RNF-25: tiempo de respuesta medido de las operaciones de pagos

Medición automatizada con `scripts/medir_rnf25.py` el 2026-11-20 21:26 (hora de Bogotá), contra el
sistema levantado con Docker Compose sobre una base limpia, a través de `http://localhost:4200`.
Percentil 95 por rango más cercano, con el mismo método de RNF-19 (el script reutiliza sus
funciones). Los tiempos incluyen la red local, nginx, la API y PostgreSQL.

## Equipo

| Característica | Valor |
| --- | --- |
| Procesador | Intel(R) Celeron(R) N4020 CPU @ 1.10GHz |
| Núcleos lógicos | 2 |
| Memoria RAM | 7.5 GiB |
| Sistema operativo | Linux 7.0.0-42-generic |
| Docker | Docker version 29.9.2, build a82e528 |
| Docker Compose | 5.6.1 |
| Commit medido | c07f1bd |

## Resultados

| Operación | Simultáneas | Muestras | Mediana (ms) | p95 (ms) | Máximo (ms) | Límite p95 (ms) | ¿Cumple? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Registrar pago | 4 | 40 | 124 | 189 | 233 | 1000 | Sí |
| Consultar estado de la mensualidad | 4 | 40 | 68 | 94 | 108 | 1000 | Sí |
| Consultar pagos | 4 | 40 | 97 | 190 | 206 | 1000 | Sí |
| Resumen de recaudo | 4 | 40 | 69 | 92 | 93 | 1000 | Sí |

**Resultado global: cumple RNF-25.**

## Escenario

- Cuatro sesiones abiertas a la vez (dos porterías y la administración) envían las solicitudes de
  cada operación al mismo tiempo, en tandas de 4.
- **Registrar pago:** cada solicitud cobra a un vehículo distinto (de 1 a 3 meses, en efectivo), con
  el bloqueo de la fila del vehículo, la inserción del pago y de su periodo, y el comprobante. Antes
  de medir se crean los clientes y vehículos; esa preparación no se mide.
- **Consultar estado de la mensualidad:** vehículos de la medición y de las semillas (vigente, con
  pago por adelantado, vencida y sin mensualidad).
- **Consultar pagos:** con y sin filtros (placa, método, estado y rango de fechas).
- **Resumen de recaudo:** el mes en curso.
- Los pagos registrados no se pueden borrar (RNF-24): por eso la medición se ejecuta sobre una base
  limpia que después se recrea.

Datos crudos de esta ejecución: [`rnf25.csv`](rnf25.csv).
