# Evidencia de RNF-26: compatibilidad de navegadores de la Iteración 3 (caso NF-02 del plan PP-03)

Pruebas de extremo a extremo con Playwright 1.64.1 dentro de Docker, el 2026-11-20 21:25 (hora de
Bogotá), sobre el commit `c07f1bd`. Comando: `docker compose --profile e2e run --rm --build e2e-rnf26`.
Cada pantalla se verifica (textos, menús y botones esperados) antes de capturarla, y el recorrido
no modifica datos: el pago llega hasta el resumen, la tarifa y la anulación hasta su confirmación, y las tres se cancelan; el comprobante es el del pago de ejemplo de las semillas.
Los navegadores corren sin ventana (modo headless), con una ventana de 1280 × 900 px; por eso su
identificación dice "HeadlessChrome". La página que dibujan es la misma que con ventana.

## Navegadores

| Navegador | Motor | Versión | Aclaración |
| --- | --- | --- | --- |
| Google Chrome (estable, Linux) | Chromium (Blink) | 157.0.8103.78 | Navegador oficial de Google para Linux, descargado al construir la imagen. |
| Microsoft Edge (estable, Linux) | Chromium (Blink) | 157.0.4341.46 | Navegador oficial de Microsoft para Linux, no la versión de Windows. Comparte motor con Chrome. |
| Firefox de Playwright | Gecko | 157.0 | Firefox que distribuye Playwright 1.64.1: motor Gecko de Firefox estable con parches para automatizarlo. No es el instalador oficial de Mozilla y puede ir unas semanas detrás de la última versión. |

Identificación que envía cada navegador (user agent), como prueba de cuál se ejecutó:

- Google Chrome (estable, Linux): `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/157.0.0.0 Safari/537.36`
- Microsoft Edge (estable, Linux): `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0`
- Firefox de Playwright: `Mozilla/5.0 (X11; Linux x86_64; rv:157.0) Gecko/20100101 Firefox/157.0`

## Resultado por pantalla

| Pantalla | Google Chrome | Microsoft Edge | Firefox de Playwright |
| --- | --- | --- | --- |
| 01 · Tarifas del administrador (vigentes e historial) | Sí · [captura](RNF-26_chrome_01_tarifas_administrador.png) | Sí · [captura](RNF-26_edge_01_tarifas_administrador.png) | Sí · [captura](RNF-26_firefox_01_tarifas_administrador.png) |
| 02 · Confirmación de una tarifa nueva (cancelada) | Sí · [captura](RNF-26_chrome_02_confirmar_tarifa.png) | Sí · [captura](RNF-26_edge_02_confirmar_tarifa.png) | Sí · [captura](RNF-26_firefox_02_confirmar_tarifa.png) |
| 03 · Clientes: búsqueda con vehículos y detalle | Sí · [captura](RNF-26_chrome_03_clientes.png) | Sí · [captura](RNF-26_edge_03_clientes.png) | Sí · [captura](RNF-26_firefox_03_clientes.png) |
| 04 · Registrar cliente con datos inválidos y sus errores | Sí · [captura](RNF-26_chrome_04_registrar_cliente_errores.png) | Sí · [captura](RNF-26_edge_04_registrar_cliente_errores.png) | Sí · [captura](RNF-26_firefox_04_registrar_cliente_errores.png) |
| 05 · Pagos: estado de la mensualidad de STU852 | Sí · [captura](RNF-26_chrome_05_pagos_estado.png) | Sí · [captura](RNF-26_edge_05_pagos_estado.png) | Sí · [captura](RNF-26_firefox_05_pagos_estado.png) |
| 06 · Pagos: resumen antes de confirmar (se vuelve sin registrar) | Sí · [captura](RNF-26_chrome_06_pagos_resumen.png) | Sí · [captura](RNF-26_edge_06_pagos_resumen.png) | Sí · [captura](RNF-26_firefox_06_pagos_resumen.png) |
| 07 · Detalle del pago con su comprobante | Sí · [captura](RNF-26_chrome_07_comprobante.png) | Sí · [captura](RNF-26_edge_07_comprobante.png) | Sí · [captura](RNF-26_firefox_07_comprobante.png) |
| 08 · Anulación: motivo y confirmación (cancelada) | Sí · [captura](RNF-26_chrome_08_confirmar_anulacion.png) | Sí · [captura](RNF-26_edge_08_confirmar_anulacion.png) | Sí · [captura](RNF-26_firefox_08_confirmar_anulacion.png) |
| 09 · Resumen de recaudo | Sí · [captura](RNF-26_chrome_09_recaudo.png) | Sí · [captura](RNF-26_edge_09_recaudo.png) | Sí · [captura](RNF-26_firefox_09_recaudo.png) |
| 10 · Operador: menú sin Recaudo y detalle del pago sin Anular | Sí · [captura](RNF-26_chrome_10_operador_pagos.png) | Sí · [captura](RNF-26_edge_10_operador_pagos.png) | Sí · [captura](RNF-26_firefox_10_operador_pagos.png) |

**Resultado: las 10 pantallas funcionan en los tres navegadores.**

## Capturas idénticas entre Chrome y Edge

9 de las 10 capturas de Chrome y de Edge son idénticas byte por byte. Es lo esperado: los
dos navegadores usan el mismo motor (Chromium) y las mismas fuentes del contenedor, y la captura es
del contenido de la página, no de la ventana del navegador. Que sí se ejecutaron navegadores
distintos lo muestran la versión y la identificación (user agent) de la tabla de navegadores.

Las contraseñas se toman de `.env` a través de Docker Compose: no aparecen en el código, en las
capturas (los campos de contraseña muestran puntos) ni en este reporte. Al terminar, el propio
recorrido comprueba que ningún valor de `.env` quedó en el reporte ni en los nombres de los archivos.
