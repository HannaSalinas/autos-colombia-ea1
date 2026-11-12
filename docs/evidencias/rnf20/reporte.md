# Evidencia de RNF-20: compatibilidad de navegadores (caso NF-02)

Pruebas de extremo a extremo con Playwright 1.64.1 dentro de Docker, el 2026-11-12 09:16 (hora de
Bogotá), sobre el commit `c16a30a`. Comando: `docker compose --profile e2e run --rm --build e2e`.
Cada pantalla se verifica (textos, menús y botones esperados) antes de capturarla, y el recorrido
no modifica datos: las confirmaciones se cancelan y la cuenta "abc" no llega a enviarse.
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
| 01 · Ingreso | Sí · [captura](NF-02_chrome_01_ingreso.png) | Sí · [captura](NF-02_edge_01_ingreso.png) | Sí · [captura](NF-02_firefox_01_ingreso.png) |
| 02 · Error de credenciales | Sí · [captura](NF-02_chrome_02_error_credenciales.png) | Sí · [captura](NF-02_edge_02_error_credenciales.png) | Sí · [captura](NF-02_firefox_02_error_credenciales.png) |
| 03 · Inicio del administrador | Sí · [captura](NF-02_chrome_03_inicio_administrador.png) | Sí · [captura](NF-02_edge_03_inicio_administrador.png) | Sí · [captura](NF-02_firefox_03_inicio_administrador.png) |
| 04 · Cuentas de usuario | Sí · [captura](NF-02_chrome_04_cuentas.png) | Sí · [captura](NF-02_edge_04_cuentas.png) | Sí · [captura](NF-02_firefox_04_cuentas.png) |
| 05 · Crear cuenta con el usuario "abc" y su error | Sí · [captura](NF-02_chrome_05_crear_cuenta_abc.png) | Sí · [captura](NF-02_edge_05_crear_cuenta_abc.png) | Sí · [captura](NF-02_firefox_05_crear_cuenta_abc.png) |
| 06 · Confirmación de desactivar a diego.arango (cancelada) | Sí · [captura](NF-02_chrome_06_confirmar_desactivar.png) | Sí · [captura](NF-02_edge_06_confirmar_desactivar.png) | Sí · [captura](NF-02_firefox_06_confirmar_desactivar.png) |
| 07 · Celdas del administrador | Sí · [captura](NF-02_chrome_07_celdas_administrador.png) | Sí · [captura](NF-02_edge_07_celdas_administrador.png) | Sí · [captura](NF-02_firefox_07_celdas_administrador.png) |
| 08 · Confirmación de inhabilitar una celda (cancelada) | Sí · [captura](NF-02_chrome_08_confirmar_inhabilitar.png) | Sí · [captura](NF-02_edge_08_confirmar_inhabilitar.png) | Sí · [captura](NF-02_firefox_08_confirmar_inhabilitar.png) |
| 09 · Inicio del operador | Sí · [captura](NF-02_chrome_09_inicio_operador.png) | Sí · [captura](NF-02_edge_09_inicio_operador.png) | Sí · [captura](NF-02_firefox_09_inicio_operador.png) |
| 10 · Celdas del operador | Sí · [captura](NF-02_chrome_10_celdas_operador.png) | Sí · [captura](NF-02_edge_10_celdas_operador.png) | Sí · [captura](NF-02_firefox_10_celdas_operador.png) |

**Resultado: las 10 pantallas funcionan en los tres navegadores.**

## Capturas idénticas entre Chrome y Edge

10 de las 10 capturas de Chrome y de Edge son idénticas byte por byte. Es lo esperado: los
dos navegadores usan el mismo motor (Chromium) y las mismas fuentes del contenedor, y la captura es
del contenido de la página, no de la ventana del navegador. Que sí se ejecutaron navegadores
distintos lo muestran la versión y la identificación (user agent) de la tabla de navegadores.

Las contraseñas se toman de `.env` a través de Docker Compose: no aparecen en el código, en las
capturas (los campos de contraseña muestran puntos) ni en este reporte. Al terminar, el propio
recorrido comprueba que ningún valor de `.env` quedó en el reporte ni en los nombres de los archivos.
