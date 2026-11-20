# Diccionario de datos — Autos Colombia (Iteraciones 1, 2 y 3)

Base de datos PostgreSQL 17, esquema `public`, con las migraciones Alembic **0001–0011**
aplicadas. Se armó a partir del esquema real exportado en [`modelo_fisico.sql`](modelo_fisico.sql)
(`pg_dump --schema-only`).

Convenciones:

- **PK**: llave primaria; **FK**: llave foránea; **UQ**: valor único.
- Todas las llaves primarias son `bigint GENERATED ALWAYS AS IDENTITY`: la base genera el número
  y no se puede escribir a mano.
- `timestamptz` = `timestamp with time zone`. Las fechas y horas se guardan en UTC con la
  hora del servidor y se muestran en America/Bogota.
- "No vacío" significa que el texto tiene al menos un carácter que no es espacio
  (`texto ~ '[^[:space:]]'`).
- Todas las FK usan `ON DELETE RESTRICT`: no se puede borrar una fila que otra tabla esté usando.
- La columna **Origen** indica qué migración creó la tabla o la restricción. Las 0001 y 0002
  son del profesor; de la 0003 a la 0005 son nuestras (Iteración 1); la 0006, la 0007 y la 0008
  también (Iteración 2), y de la 0009 a la 0011 (Iteración 3).
- Los montos son pesos colombianos enteros en columnas `integer` (tipo exacto, nunca de punto
  flotante; RNF-22).
- `NOT VALID` significa que la restricción se aplica a las filas nuevas y modificadas, pero
  no revisa las que ya existían cuando se creó. La migración 0008 valida los CHECK de celda
  (`ck_celda_tipo` y `ck_celda_codigo_formato`) en toda la tabla cuando todas las celdas los
  cumplen; si alguna no los cumple, quedan `NOT VALID` y la migración avisa qué códigos fallan.
  En esta base las 80 celdas cumplen, así que los dos están validados. La 0011 hace lo mismo con
  los CHECK de cliente de la 0009 (documento, nombre y teléfono); en una base nueva quedan validados.

## Relaciones

```text
cliente 1 ──< N vehiculo 1 ──< N mensualidad 1 ──o 1 pago >── 1 tarifa   (Iteración 3)
                vehiculo 1 ──< N estancia >── 1 celda
                operador 1 ──< N estancia            (operador de entrada y de salida)
                estancia 1 ──< N correccion_celda    (celda anterior y celda nueva → celda)
                estancia 1 ──< N novedad
                operador 1 ──< N correccion_celda, novedad
                operador 1 ──  1 cuenta_usuario      (la persona y su cuenta de acceso)
          cuenta_usuario 1 ──< N auditoria_cuenta    (cuenta auditada y cuenta que actuó)
                   celda 1 ──< N auditoria_celda >── 1 cuenta_usuario (cuenta que actuó)
          cuenta_usuario 1 ──< N pago, tarifa, cliente (quién registró, anuló o definió; D18)
```

Cada pago genera exactamente un periodo (`mensualidad.pago_id`, único). Los periodos anteriores a
la Iteración 3 no tienen pago (`pago_id` NULL) y siguen siendo válidos (D10).

| Tabla | Para qué sirve | Origen |
| --- | --- | --- |
| `cliente` | Propietario de uno o varios vehículos | 0003 (+ 0009, 0011) |
| `vehiculo` | Vehículo registrado y asociado a su cliente | 0001 (+ 0003) |
| `mensualidad` | Periodo de mensualidad de un vehículo (fin inclusivo) | 0003 (+ 0010) |
| `tarifa` | Tarifa mensual por tipo de vehículo; nunca se edita | 0009 |
| `pago` | Pago de una mensualidad; genera un periodo; solo pasa de VALIDO a ANULADO | 0010 |
| `celda` | Las celdas del parqueadero (80 sembradas) | 0001 (+ 0004, 0007) |
| `operador` | La persona: responsable de cada movimiento y dueña de una cuenta | 0001 (+ 0006) |
| `cuenta_usuario` | Credenciales, rol y estado de acceso de una persona | 0006 |
| `auditoria_cuenta` | Quién y cuándo creó, desactivó o reactivó una cuenta | 0006 |
| `auditoria_celda` | Quién y cuándo creó, editó, inhabilitó o rehabilitó una celda | 0007 |
| `estancia` | Una entrada y su salida (abierta mientras el vehículo está dentro) | 0002 |
| `correccion_celda` | Cambio de celda de una estancia abierta, con motivo | 0005 |
| `novedad` | Hecho registrado durante una estancia (rayón, golpe, …) | 0005 |
| `alembic_version` | Versión de migración aplicada (`0011`); la usa Alembic | Alembic |

## cliente

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `documento` | text | No | UQ (con el tipo) | Número de documento: 5 a 15 letras o números, en mayúsculas |
| `nombre` | text | No | | Nombre completo (3 a 80 caracteres) |
| `telefono` | text | No | | Teléfono de contacto (10 dígitos) |
| `correo` | text | Sí | | Correo electrónico (opcional) |
| `tipo_documento` | text | No | UQ (con el documento) | `CC`, `CE` o `PA`. Los clientes anteriores quedaron con `CC` (0009) |
| `registrado_en` | timestamptz | Sí | | Cuándo lo registró el Administrador. NULL = anterior a la Iteración 3 o semilla |
| `registrado_por_cuenta_id` | bigint | Sí | FK → `cuenta_usuario.id` | Quién lo registró (D18). NULL = anterior o semilla |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `cliente_pkey` | PRIMARY KEY | `id` | 0003 |
| `ck_cliente_documento_no_vacio` | CHECK | `documento` no vacío | 0003 |
| `ck_cliente_nombre_no_vacio` | CHECK | `nombre` no vacío | 0003 |
| `ck_cliente_telefono_no_vacio` | CHECK | `telefono` no vacío | 0003 |
| `ck_cliente_correo_formato` | CHECK | `correo IS NULL` o con forma `algo@dominio.ext` | 0003 |
| `uq_cliente_tipo_documento` | Índice único | (`tipo_documento`, `upper(documento)`): único por tipo y número, sin distinguir mayúsculas. Reemplaza al `uq_cliente_documento` de la 0003 | 0009 |
| `ck_cliente_tipo_documento` | CHECK | `tipo_documento` en (`CC`, `CE`, `PA`) | 0009 |
| `ck_cliente_documento_formato` | CHECK | `documento ~ '^[A-Z0-9]{5,15}$'` (NOT VALID; validado por la 0011 si todos cumplen) | 0009 |
| `ck_cliente_nombre_longitud` | CHECK | 3 a 80 caracteres, sin espacios al inicio ni al final (NOT VALID; validado por la 0011) | 0009 |
| `ck_cliente_telefono_formato` | CHECK | `telefono ~ '^[0-9]{10}$'` (NOT VALID; validado por la 0011) | 0009 |
| `ck_cliente_registro` | CHECK | Si tiene `registrado_por_cuenta_id`, tiene `registrado_en` | 0009 |
| `fk_cliente_registrado_por` | FOREIGN KEY | `registrado_por_cuenta_id` → `cuenta_usuario(id)`, ON DELETE RESTRICT | 0009 |

## vehiculo

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `placa` | text | No | UQ | Placa sin espacios ni guiones, en mayúsculas |
| `color` | text | No | | Color |
| `modelo` | integer | No | | Año del modelo |
| `marca` | text | No | | Marca |
| `tipo` | text | No | | `MOTO`, `AUTOMOVIL` o `CAMIONETA` |
| `cliente_id` | bigint | No | FK → `cliente.id` | Propietario (obligatorio) |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `vehiculo_pkey` | PRIMARY KEY | `id` | 0001 |
| `uq_vehiculo_placa` | UNIQUE | `placa` | 0001 |
| `fk_vehiculo_cliente` | FOREIGN KEY | `cliente_id` → `cliente(id)`, ON DELETE RESTRICT | 0003 |
| `ck_vehiculo_tipo` | CHECK | `tipo` en (`MOTO`, `AUTOMOVIL`, `CAMIONETA`) | 0001 |
| `ck_vehiculo_placa_no_vacia` | CHECK | `placa` no vacía | 0001 |
| `ck_vehiculo_placa_normalizada` | CHECK | `placa` en mayúsculas y sin espacios al inicio ni al final | 0001 |
| `ck_vehiculo_placa_formato` | CHECK | Moto: `^[A-Z]{3}[0-9]{2}[A-Z]$` (ABC12D); otro tipo: `^[A-Z]{3}[0-9]{3}$` (ABC123) | 0003 |
| `ck_vehiculo_modelo_anio` | CHECK | `1 <= modelo <= 9999` | 0001 |
| `ck_vehiculo_modelo_minimo` | CHECK | `modelo >= 1900` | 0003 |
| `ck_vehiculo_color_no_vacio` | CHECK | `color` no vacío | 0001 |
| `ck_vehiculo_marca_no_vacia` | CHECK | `marca` no vacía | 0001 |
| `ix_vehiculo_cliente` | Índice | `cliente_id` (vehículos de un cliente) | 0003 |

El tope de modelo **año actual + 1** cambia cada año, así que no se puede escribir como
CHECK fijo. Lo validan la API (`app/domain/reglas.py`) y el formulario.

## mensualidad

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `vehiculo_id` | bigint | No | FK → `vehiculo.id` | Vehículo al que pertenece (la mensualidad es por vehículo) |
| `fecha_inicio` | date | No | | Primer día del periodo |
| `fecha_fin` | date | No | | Último día del periodo, incluido. Periodos anteriores: mismo día del mes siguiente. Pagados desde la Iteración 3: día anterior a la misma fecha N meses después (D13) |
| `pago_id` | bigint | Sí | UQ, FK → `pago` | Pago que generó el periodo (1 a 1). NULL = periodo anterior a la Iteración 3 (D10) |
| `pago_estado` | text | Sí | FK → `pago` | Copia del estado del pago (`VALIDO` o `ANULADO`) que mantiene la propia base |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `mensualidad_pkey` | PRIMARY KEY | `id` | 0003 |
| `fk_mensualidad_vehiculo` | FOREIGN KEY | `vehiculo_id` → `vehiculo(id)`, ON DELETE RESTRICT | 0003 |
| `ck_mensualidad_fechas` | CHECK | `fecha_fin > fecha_inicio` | 0003 |
| `ix_mensualidad_vehiculo_fin` | Índice | (`vehiculo_id`, `fecha_fin`): buscar la mensualidad vigente | 0003 |
| `uq_mensualidad_pago` | UNIQUE | `pago_id`: un pago genera un solo periodo | 0010 |
| `fk_mensualidad_pago` | FOREIGN KEY | (`pago_id`, `pago_estado`) → `pago(id, estado)`, ON UPDATE CASCADE, ON DELETE RESTRICT. Al anular el pago, la base actualiza `pago_estado` en la misma sentencia | 0010 |
| `ck_mensualidad_pago` | CHECK | `(pago_id IS NULL) = (pago_estado IS NULL)` | 0010 |
| `ex_mensualidad_pagada_sin_superposicion` | EXCLUDE (GiST) | `vehiculo_id WITH =`, `daterange(fecha_inicio, fecha_fin, '[]') WITH &&`, `WHERE (pago_estado = 'VALIDO')`: dos periodos pagados y no anulados del mismo vehículo no se cruzan | 0010 |

Una mensualidad está vigente si `fecha_inicio <= hoy <= fecha_fin` y no está anulada
(`pago_estado` NULL o `VALIDO`), con "hoy" en Bogotá.

**Por qué la exclusión es parcial (RNF-23).** PostgreSQL no admite `EXCLUDE … NOT VALID`: la
restricción se revisa completa al crearla, y algunos periodos antiguos ya se tocan (en las
semillas, los dos de JKL321 comparten un día). Por eso solo cubre periodos pagados y no anulados.
Entre un periodo pagado y uno antiguo, la no superposición la garantiza el servicio bloqueando la
fila del vehículo (`SELECT … FOR UPDATE`). La migración 0010 avisa las superposiciones antiguas que
encuentra, sin modificarlas.

## tarifa

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `tipo_vehiculo` | text | No | | `MOTO`, `AUTOMOVIL` o `CAMIONETA` |
| `valor` | integer | No | | Valor mensual en pesos enteros |
| `vigente_desde` | timestamptz | No | | Desde cuándo rige (hora del servidor). La vigente de cada tipo es la más reciente |
| `definida_por_cuenta_id` | bigint | Sí | FK → `cuenta_usuario.id` | Quién la definió (D18). NULL = semillas |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `tarifa_pkey` | PRIMARY KEY | `id` | 0009 |
| `ck_tarifa_tipo_vehiculo` | CHECK | `tipo_vehiculo` en (`MOTO`, `AUTOMOVIL`, `CAMIONETA`) | 0009 |
| `ck_tarifa_valor` | CHECK | `valor BETWEEN 1000 AND 2000000` | 0009 |
| `uq_tarifa_tipo_desde` | UNIQUE | (`tipo_vehiculo`, `vigente_desde`) | 0009 |
| `uq_tarifa_id_tipo_valor` | UNIQUE | (`id`, `tipo_vehiculo`, `valor`): destino de la FK compuesta del pago | 0009 |
| `fk_tarifa_definida_por` | FOREIGN KEY | `definida_por_cuenta_id` → `cuenta_usuario(id)`, ON DELETE RESTRICT | 0009 |
| `tarifa_sin_cambios`, `tarifa_sin_vaciar` | TRIGGER | Rechazan UPDATE, DELETE y TRUNCATE (RNF-24, D12) | 0009 |

## pago

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `comprobante` | text | No | UQ | `RC-000001`…`RC-999999`, tomado de la secuencia `pago_comprobante_seq` |
| `meses` | smallint | No | | Meses que cubre (1 a 6) |
| `tarifa_id` | bigint | No | FK → `tarifa` | Tarifa con la que se cobró |
| `tipo_vehiculo` | text | No | FK → `tarifa` | Tipo con que se cobró (copia de la tarifa) |
| `valor_mensual` | integer | No | FK → `tarifa` | Valor mensual cobrado (copia de la tarifa) |
| `monto` | integer | No | | Total: `valor_mensual × meses`, en pesos enteros |
| `metodo` | text | No | | `EFECTIVO`, `TRANSFERENCIA` o `TARJETA` (informativo, D16) |
| `referencia` | text | Sí | | Obligatoria en transferencia y tarjeta (4 a 30 letras, números o guion); NULL en efectivo |
| `fecha` | timestamptz | No | | Hora del servidor al registrar |
| `registrado_por_cuenta_id` | bigint | No | FK → `cuenta_usuario.id` | Responsable: la cuenta de la sesión (RF-36) |
| `estado` | text | No | | `VALIDO` o `ANULADO` |
| `anulado_en` | timestamptz | Sí | | Cuándo se anuló |
| `anulado_por_cuenta_id` | bigint | Sí | FK → `cuenta_usuario.id` | Quién lo anuló (Administrador) |
| `motivo_anulacion` | text | Sí | | Por qué (10 a 200 caracteres) |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `pago_pkey` | PRIMARY KEY | `id` | 0010 |
| `uq_pago_comprobante` | UNIQUE | `comprobante` (RNF-23) | 0010 |
| `uq_pago_id_estado` | UNIQUE | (`id`, `estado`): destino de la FK compuesta de `mensualidad` | 0010 |
| `fk_pago_tarifa` | FOREIGN KEY | (`tarifa_id`, `tipo_vehiculo`, `valor_mensual`) → `tarifa(id, tipo_vehiculo, valor)`: la copia es la de una tarifa real | 0010 |
| `fk_pago_registrado_por`, `fk_pago_anulado_por` | FOREIGN KEY | → `cuenta_usuario(id)`, ON DELETE RESTRICT | 0010 |
| `ck_pago_comprobante_formato` | CHECK | `comprobante ~ '^RC-[0-9]{6}$'` | 0010 |
| `ck_pago_meses` | CHECK | `meses BETWEEN 1 AND 6` | 0010 |
| `ck_pago_monto` | CHECK | `monto = valor_mensual * meses` (D11) | 0010 |
| `ck_pago_metodo` | CHECK | `metodo` en (`EFECTIVO`, `TRANSFERENCIA`, `TARJETA`) | 0010 |
| `ck_pago_referencia` | CHECK | Efectivo: NULL; otro método: `IS NOT NULL` y `~ '^[A-Za-z0-9-]{4,30}$'` | 0010 |
| `ck_pago_estado` | CHECK | `estado` en (`VALIDO`, `ANULADO`) | 0010 |
| `ck_pago_anulacion` | CHECK | VALIDO: sin datos de anulación. ANULADO: con `anulado_en` (≥ `fecha`), `anulado_por_cuenta_id` y motivo de 10 a 200 caracteres sin espacios exteriores | 0010 |
| `ix_pago_fecha` | Índice | `fecha`: filtros por rango y resumen de recaudo | 0010 |
| `pago_sin_cambios`, `pago_sin_vaciar` | TRIGGER | Rechazan DELETE, TRUNCATE y todo UPDATE que no sea el paso único de VALIDO a ANULADO con sus datos de anulación (RNF-24) | 0010 |

## Triggers, funciones y extensión (Iteración 3)

| Objeto | Qué hace | Origen |
| --- | --- | --- |
| `tarifa_inmutable()` | Función de los triggers de `tarifa`: siempre rechaza con el código 23001 (`restrict_violation`) | 0009 |
| `pago_solo_anular()` | Función de los triggers de `pago`: deja pasar solo VALIDO → ANULADO sin cambiar ninguna otra columna fija | 0010 |
| `mensualidad_pagada_inmutable()` | Trigger `mensualidad_pagada_sin_cambios`: un periodo pagado no se borra ni cambia de fechas, vehículo o pago; deja pasar la cascada de `pago_estado`. Un periodo antiguo no se puede vincular a un pago | 0010 |
| `mensualidad_sin_vaciar()` | Trigger `mensualidad_pagada_sin_vaciar`: rechaza TRUNCATE si hay periodos pagados | 0010 |
| `btree_gist` | Extensión que permite combinar `=` y `&&` en la restricción de exclusión | 0010 |
| `pago_comprobante_seq` | Secuencia del comprobante (1 a 999999, sin ciclo), propiedad de `pago.comprobante` | 0010 |

Los periodos anteriores a la Iteración 3 (sin pago) no quedan afectados por estos triggers.

## celda

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `codigo` | text | No | UQ | Código visible: `C01`–`C99` (carro) y `M01`–`M99` (moto); se siembran C01–C70 y M01–M10 |
| `tipo` | text | No | | `CARRO` o `MOTO` |
| `disponible_desde` | timestamptz | Sí | | Desde cuándo está libre. `NULL` = nunca se ha usado. Sirve para asignar la que lleva más tiempo libre. Al rehabilitar la celda se pone la hora de la rehabilitación |
| `ubicacion` | text | Sí | | Dónde está la celda (opcional, hasta 60 caracteres) |
| `habilitada` | boolean | No | | `false` = inhabilitada: no se asigna a nuevas entradas. Por defecto `true`. Las celdas nunca se borran |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `celda_pkey` | PRIMARY KEY | `id` | 0001 |
| `uq_celda_codigo` | UNIQUE | `codigo` | 0001 |
| `ck_celda_codigo_no_vacio` | CHECK | `codigo` no vacío | 0001 |
| `ck_celda_codigo_normalizado` | CHECK | `codigo` en mayúsculas y sin espacios al inicio ni al final | 0001 |
| `ck_celda_tipo_no_vacio` | CHECK | `tipo` no vacío | 0001 |
| `ck_celda_tipo` | CHECK (`NOT VALID` hasta la 0008) | `tipo` en (`MOTO`, `CARRO`). La 0008 lo valida si todas las celdas cumplen | 0004 (+ 0008) |
| `ix_celda_tipo_disponible` | Índice | (`tipo`, `disponible_desde`): elegir la celda para asignar | 0004 |
| `ck_celda_ubicacion` | CHECK | `ubicacion` NULL, o de 1 a 60 caracteres sin espacios al inicio ni al final | 0007 |
| `ck_celda_codigo_formato` | CHECK (`NOT VALID` hasta la 0008) | `CARRO` con código `C01`–`C99`; `MOTO` con `M01`–`M99`. La 0008 lo valida si todas las celdas cumplen | 0007 (+ 0008) |
| `uq_celda_codigo_ci` | Índice único | `upper(codigo)`: único sin distinguir mayúsculas | 0007 |

El estado que ve el usuario se calcula: **inhabilitada** si `habilitada = false`; **ocupada**
si tiene una estancia abierta; si no, **libre**. Una celda "tiene historial" si aparece en
alguna estancia o en alguna corrección (como celda anterior o nueva); entonces su código y su
tipo ya no se pueden cambiar.

## operador

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `nombre` | text | No | | Nombre completo, por ejemplo "Marta Úsuga (Portería 1)" |
| `telefono` | text | Sí | | Teléfono. Opcional desde la 0006: el formulario de cuentas no lo pide |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `operador_pkey` | PRIMARY KEY | `id` | 0001 |
| `ck_operador_nombre_no_vacio` | CHECK | `nombre` no vacío | 0001 |
| `ck_operador_telefono_no_vacio` | CHECK | `telefono` no vacío (si se da) | 0001 |
| `ck_operador_nombre_longitud` | CHECK `NOT VALID` | `nombre` de 3 a 80 caracteres, sin espacios al inicio ni al final | 0006 |

En la Iteración 2 esta tabla representa a la **persona**; su acceso al sistema es la
`cuenta_usuario`. Se conservó el nombre `operador` para que las estancias, correcciones y
novedades de la EA1 sigan apuntando a la misma fila y conserven su responsable.

## cuenta_usuario

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `operador_id` | bigint | No | FK → `operador.id`, UQ | Persona dueña de la cuenta (una cuenta por persona) |
| `nombre_usuario` | text | No | UQ (sin mayúsculas) | Usuario para ingresar: 4 a 30 caracteres en minúsculas, dígitos, punto o guion bajo |
| `hash_contrasena` | text | No | | Hash bcrypt de la contraseña (costo 12 o más). La contraseña nunca se guarda |
| `rol` | text | No | | `ADMINISTRADOR` u `OPERADOR` |
| `activa` | boolean | No | | `false` = desactivada: no puede ingresar. Por defecto `true`. Las cuentas nunca se borran |
| `version_sesion` | integer | No | | Sube al desactivar la cuenta o cerrar sesión: los tokens con una versión anterior dejan de valer |
| `creada_en` | timestamptz | No | | Fecha de creación (por defecto `now()`) |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `cuenta_usuario_pkey` | PRIMARY KEY | `id` | 0006 |
| `fk_cuenta_usuario_operador` | FOREIGN KEY | `operador_id` → `operador(id)`, ON DELETE RESTRICT | 0006 |
| `uq_cuenta_usuario_operador` | UNIQUE | `operador_id` | 0006 |
| `uq_cuenta_usuario_nombre` | Índice único | `lower(nombre_usuario)`: único sin distinguir mayúsculas | 0006 |
| `ck_cuenta_usuario_nombre_formato` | CHECK | `nombre_usuario ~ '^[a-z0-9._]{4,30}$'` | 0006 |
| `ck_cuenta_usuario_rol` | CHECK | `rol` en (`ADMINISTRADOR`, `OPERADOR`) | 0006 |
| `ck_cuenta_usuario_hash_bcrypt` | CHECK | `hash_contrasena` con forma de hash bcrypt y costo de 12 a 39 | 0006 |
| `ck_cuenta_usuario_version_sesion` | CHECK | `version_sesion >= 0` | 0006 |

## auditoria_cuenta

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `cuenta_id` | bigint | No | FK → `cuenta_usuario.id` | Cuenta afectada |
| `actor_cuenta_id` | bigint | Sí | FK → `cuenta_usuario.id` | Cuenta que hizo el cambio. `NULL` = el sistema (semillas) |
| `fecha` | timestamptz | No | | Cuándo (por defecto `now()`) |
| `accion` | text | No | | `CREAR`, `DESACTIVAR` o `REACTIVAR` |
| `detalle` | text | Sí | | Descripción breve, máximo 500 caracteres |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `auditoria_cuenta_pkey` | PRIMARY KEY | `id` | 0006 |
| `fk_auditoria_cuenta_cuenta` | FOREIGN KEY | `cuenta_id` → `cuenta_usuario(id)`, ON DELETE RESTRICT | 0006 |
| `fk_auditoria_cuenta_actor` | FOREIGN KEY | `actor_cuenta_id` → `cuenta_usuario(id)`, ON DELETE RESTRICT | 0006 |
| `ck_auditoria_cuenta_accion` | CHECK | `accion` en (`CREAR`, `DESACTIVAR`, `REACTIVAR`) | 0006 |
| `ck_auditoria_cuenta_detalle` | CHECK | `detalle` NULL o de 500 caracteres o menos | 0006 |
| `ix_auditoria_cuenta_cuenta` | Índice | (`cuenta_id`, `fecha`): auditoría de una cuenta | 0006 |

## auditoria_celda

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `celda_id` | bigint | No | FK → `celda.id` | Celda afectada |
| `actor_cuenta_id` | bigint | Sí | FK → `cuenta_usuario.id` | Cuenta que hizo el cambio. `NULL` = el sistema (semillas) |
| `fecha` | timestamptz | No | | Cuándo (por defecto `now()`) |
| `accion` | text | No | | `CREAR`, `EDITAR`, `INHABILITAR` o `REHABILITAR` |
| `detalle` | text | Sí | | Qué cambió, por ejemplo «ubicación: — → Sótano 1» (máximo 500 caracteres) |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `auditoria_celda_pkey` | PRIMARY KEY | `id` | 0007 |
| `fk_auditoria_celda_celda` | FOREIGN KEY | `celda_id` → `celda(id)`, ON DELETE RESTRICT | 0007 |
| `fk_auditoria_celda_actor` | FOREIGN KEY | `actor_cuenta_id` → `cuenta_usuario(id)`, ON DELETE RESTRICT | 0007 |
| `ck_auditoria_celda_accion` | CHECK | `accion` en (`CREAR`, `EDITAR`, `INHABILITAR`, `REHABILITAR`) | 0007 |
| `ck_auditoria_celda_detalle` | CHECK | `detalle` NULL o de 500 caracteres o menos | 0007 |
| `ix_auditoria_celda_celda` | Índice | (`celda_id`, `fecha`): auditoría de una celda | 0007 |

## estancia

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `vehiculo_id` | bigint | No | FK → `vehiculo.id` | Vehículo que entró |
| `celda_id` | bigint | No | FK → `celda.id` | Celda actual (cambia si se corrige) |
| `entrada` | timestamptz | No | | Hora de entrada (por defecto `now()`, hora del servidor) |
| `salida` | timestamptz | Sí | | Hora de salida. `NULL` = el vehículo sigue dentro |
| `operador_entrada_id` | bigint | No | FK → `operador.id` | Quién registró la entrada |
| `operador_salida_id` | bigint | Sí | FK → `operador.id` | Quién registró la salida |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `estancia_pkey` | PRIMARY KEY | `id` | 0002 |
| `fk_estancia_vehiculo` | FOREIGN KEY | `vehiculo_id` → `vehiculo(id)`, ON DELETE RESTRICT | 0002 |
| `fk_estancia_celda` | FOREIGN KEY | `celda_id` → `celda(id)`, ON DELETE RESTRICT | 0002 |
| `fk_estancia_operador_entrada` | FOREIGN KEY | `operador_entrada_id` → `operador(id)`, ON DELETE RESTRICT | 0002 |
| `fk_estancia_operador_salida` | FOREIGN KEY | `operador_salida_id` → `operador(id)`, ON DELETE RESTRICT | 0002 |
| `ck_estancia_orden_fechas` | CHECK | `salida >= entrada` | 0002 |
| `ck_estancia_cierre_completo` | CHECK | `salida` y `operador_salida_id` son los dos nulos o los dos con valor | 0002 |
| `uq_estancia_vehiculo_abierta` | Índice único parcial | `vehiculo_id` WHERE `salida IS NULL`: un vehículo no puede tener dos estancias abiertas | 0002 |
| `uq_estancia_celda_abierta` | Índice único parcial | `celda_id` WHERE `salida IS NULL`: una celda no puede tener dos vehículos dentro | 0002 |
| `ix_estancia_vehiculo_entrada` | Índice | (`vehiculo_id`, `entrada`): historial por vehículo | 0002 |
| `ix_estancia_celda` | Índice | `celda_id`: saber si una celda tiene historial | 0007 |

## correccion_celda

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `estancia_id` | bigint | No | FK → `estancia.id` | Estancia corregida (debe estar abierta; lo valida el servicio) |
| `celda_anterior_id` | bigint | No | FK → `celda.id` | Celda donde estaba registrada |
| `celda_nueva_id` | bigint | No | FK → `celda.id` | Celda donde quedó |
| `operador_id` | bigint | No | FK → `operador.id` | Quién hizo la corrección |
| `fecha` | timestamptz | No | | Hora de la corrección (por defecto `now()`) |
| `motivo` | text | No | | Motivo obligatorio, máximo 200 caracteres |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `correccion_celda_pkey` | PRIMARY KEY | `id` | 0005 |
| `fk_correccion_celda_estancia` | FOREIGN KEY | `estancia_id` → `estancia(id)`, ON DELETE RESTRICT | 0005 |
| `fk_correccion_celda_anterior` | FOREIGN KEY | `celda_anterior_id` → `celda(id)`, ON DELETE RESTRICT | 0005 |
| `fk_correccion_celda_nueva` | FOREIGN KEY | `celda_nueva_id` → `celda(id)`, ON DELETE RESTRICT | 0005 |
| `fk_correccion_celda_operador` | FOREIGN KEY | `operador_id` → `operador(id)`, ON DELETE RESTRICT | 0005 |
| `ck_correccion_celda_distinta` | CHECK | `celda_anterior_id <> celda_nueva_id` | 0005 |
| `ck_correccion_celda_motivo` | CHECK | `motivo` no vacío y de 200 caracteres o menos | 0005 |
| `ix_correccion_celda_estancia` | Índice | `estancia_id`: correcciones de una estancia | 0005 |
| `ix_correccion_celda_anterior` | Índice | `celda_anterior_id`: saber si una celda tiene historial | 0007 |
| `ix_correccion_celda_nueva` | Índice | `celda_nueva_id`: saber si una celda tiene historial | 0007 |

## novedad

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `id` | bigint (identity) | No | PK | Identificador |
| `estancia_id` | bigint | No | FK → `estancia.id` | Estancia en la que ocurrió (debe estar abierta; lo valida el servicio) |
| `operador_id` | bigint | No | FK → `operador.id` | Quién la registró |
| `fecha` | timestamptz | No | | Hora del registro (por defecto `now()`) |
| `tipo` | text | No | | `RAYON`, `GOLPE`, `OBJETO_OLVIDADO` u `OTRO` |
| `descripcion` | text | No | | Descripción obligatoria, máximo 500 caracteres |

| Restricción | Tipo | Regla | Origen |
| --- | --- | --- | --- |
| `novedad_pkey` | PRIMARY KEY | `id` | 0005 |
| `fk_novedad_estancia` | FOREIGN KEY | `estancia_id` → `estancia(id)`, ON DELETE RESTRICT | 0005 |
| `fk_novedad_operador` | FOREIGN KEY | `operador_id` → `operador(id)`, ON DELETE RESTRICT | 0005 |
| `ck_novedad_tipo` | CHECK | `tipo` en (`RAYON`, `GOLPE`, `OBJETO_OLVIDADO`, `OTRO`) | 0005 |
| `ck_novedad_descripcion` | CHECK | `descripcion` no vacía y de 500 caracteres o menos | 0005 |
| `ix_novedad_estancia` | Índice | `estancia_id`: novedades de una estancia | 0005 |

## alembic_version

| Columna | Tipo | Nulo | Llave | Descripción |
| --- | --- | --- | --- | --- |
| `version_num` | varchar(32) | No | PK (`alembic_version_pkc`) | Última migración aplicada: `0011` |

## Reglas que no están en la base

Estas reglas dependen de la fecha de hoy o de otras filas, así que no se pueden escribir
como CHECK. Las validan los servicios del backend, dentro de transacciones con bloqueos:

- Solo entra un vehículo con mensualidad vigente hoy (en Bogotá) y no anulada.
- La celda asignada es del tipo del vehículo: MOTO → `MOTO`; AUTOMOVIL y CAMIONETA → `CARRO`.
- No se cambia el tipo de un vehículo que está dentro, ni el tipo de una celda ocupada.
- Las correcciones y novedades solo se registran sobre estancias abiertas. La celda nueva
  de una corrección debe estar libre y ser compatible.
- El modelo del vehículo no puede pasar del año actual + 1.

Reglas de estado de la Iteración 2 (RNF-16): se validan en Angular y en la API, dentro de una
transacción con bloqueo de filas, que es lo que impide que dos operaciones simultáneas las
incumplan:

- Una celda ocupada no se puede inhabilitar.
- El código y el tipo de una celda con historial, o que esté ocupada, no se pueden cambiar.
- Un administrador no puede desactivar su propia cuenta ni la del último administrador activo.

Reglas de la Iteración 3 que dependen de la fecha o de otras filas (servicio `app/services/pago.py`,
con bloqueo `FOR UPDATE` de la fila del vehículo):

- El nuevo periodo empieza el día siguiente al último fin no anulado si es hoy o posterior; si no,
  hoy (D13). Su fin no puede pasar de hoy + 12 meses.
- El monto es la tarifa vigente del tipo × meses (D11). Si no coincide con el que se confirmó en el
  resumen (`monto_confirmado`), el pago no se registra (409).
- Solo se anula el pago VÁLIDO del último periodo no anulado del vehículo (D14).
- Que todo pago tenga su periodo lo garantiza el servicio (se insertan en la misma transacción).

## Cómo regenerarlo

Con la pila levantada y las migraciones al día (`docker compose up -d`):

```bash
docker compose exec -T db pg_dump --schema-only --no-owner --no-privileges > docs/modelo_fisico.sql
```

`--no-owner` y `--no-privileges` quitan el usuario dueño y los permisos, que dependen de la
instalación. Así el archivo se puede cargar en cualquier PostgreSQL 17. El dump guardado
lleva además cuatro líneas de comentario al inicio que explican cómo se generó.
