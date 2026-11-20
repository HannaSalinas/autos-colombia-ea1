"""Modelos iniciales. Importar este módulo no crea tablas ni abre conexiones."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Identity, Index, Integer,
    SmallInteger, Text, UniqueConstraint, func, text, true,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates

from app.domain.pagos import (
    DOCUMENTO_MAXIMO, DOCUMENTO_MINIMO, MESES_MAXIMO, MESES_MINIMO, METODOS_PAGO, MOTIVO_ANULACION_MAXIMO,
    MOTIVO_ANULACION_MINIMO, REFERENCIA_MAXIMA, REFERENCIA_MINIMA, TARIFA_MAXIMA, TARIFA_MINIMA, TIPOS_DOCUMENTO,
    TIPOS_VEHICULO,
)
from app.domain.reglas import (
    DESCRIPCION_MAXIMA, MODELO_MINIMO, MOTIVO_MAXIMO, NOMBRE_MAXIMO, NOMBRE_MINIMO, ROLES, TIPOS_NOVEDAD, TOTAL_CELDAS,
    UBICACION_MAXIMA, USUARIO_MAXIMO, USUARIO_MINIMO, normalizar_placa, required_text,
)

TIPOS_CELDA = set(TOTAL_CELDAS)


class Base(DeclarativeBase):
    pass


class Cliente(Base):
    """Propietario de uno o varios vehículos. Agregado en la migración 0003."""
    __tablename__ = "cliente"
    __table_args__ = (
        CheckConstraint("documento ~ '[^[:space:]]'", name="ck_cliente_documento_no_vacio"),
        CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_cliente_nombre_no_vacio"),
        CheckConstraint("telefono ~ '[^[:space:]]'", name="ck_cliente_telefono_no_vacio"),
        CheckConstraint("correo IS NULL OR correo ~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'",
                        name="ck_cliente_correo_formato"),
        # Agregados en la migración 0009 (Iteración 3). Los de formato nacen NOT VALID: no revisan
        # clientes antiguos, sí los nuevos y los modificados. La 0011 los valida si todos cumplen.
        CheckConstraint("tipo_documento IN (" + ", ".join(f"'{t}'" for t in TIPOS_DOCUMENTO) + ")",
                        name="ck_cliente_tipo_documento"),
        CheckConstraint("registrado_por_cuenta_id IS NULL OR registrado_en IS NOT NULL", name="ck_cliente_registro"),
        CheckConstraint(f"documento ~ '^[A-Z0-9]{{{DOCUMENTO_MINIMO},{DOCUMENTO_MAXIMO}}}$'",
                        name="ck_cliente_documento_formato", postgresql_not_valid=True),
        CheckConstraint(f"char_length(nombre) BETWEEN {NOMBRE_MINIMO} AND {NOMBRE_MAXIMO} "
                        "AND nombre !~ '^[[:space:]]|[[:space:]]$'",
                        name="ck_cliente_nombre_longitud", postgresql_not_valid=True),
        CheckConstraint("telefono ~ '^[0-9]{10}$'", name="ck_cliente_telefono_formato", postgresql_not_valid=True),
        # Único por tipo y número, sin distinguir mayúsculas (reemplaza a uq_cliente_documento de la 0003).
        Index("uq_cliente_tipo_documento", "tipo_documento", text("upper(documento)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    documento: Mapped[str] = mapped_column(Text, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    telefono: Mapped[str] = mapped_column(Text, nullable=False)
    correo: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Migración 0009. Los clientes anteriores quedaron con CC; registrado_* es NULL para los anteriores
    # a la Iteración 3 y los de las semillas (D18: el propio registro guarda quién y cuándo).
    # default solo en Python (código interno: semillas y pruebas). La API exige el tipo explícito y en la
    # base no hay DEFAULT: un INSERT directo sin tipo de documento falla.
    tipo_documento: Mapped[str] = mapped_column(Text, nullable=False, default="CC")
    registrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registrado_por_cuenta_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cuenta_usuario.id", name="fk_cliente_registrado_por", ondelete="RESTRICT"),
        nullable=True,
    )

    @validates("documento", "nombre", "telefono")
    def validate_text(self, key: str, value: str) -> str:
        return required_text(value, key)


class Vehiculo(Base):
    __tablename__ = "vehiculo"
    __table_args__ = (
        UniqueConstraint("placa", name="uq_vehiculo_placa"),
        CheckConstraint("placa ~ '[^[:space:]]'", name="ck_vehiculo_placa_no_vacia"),
        CheckConstraint("placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_vehiculo_placa_normalizada"),
        CheckConstraint("color ~ '[^[:space:]]'", name="ck_vehiculo_color_no_vacio"),
        CheckConstraint("marca ~ '[^[:space:]]'", name="ck_vehiculo_marca_no_vacia"),
        CheckConstraint("modelo BETWEEN 1 AND 9999", name="ck_vehiculo_modelo_anio"),
        CheckConstraint("tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')", name="ck_vehiculo_tipo"),
        # Agregadas en la migración 0003.
        CheckConstraint(
            "(tipo = 'MOTO' AND placa ~ '^[A-Z]{3}[0-9]{2}[A-Z]$') OR "
            "(tipo <> 'MOTO' AND placa ~ '^[A-Z]{3}[0-9]{3}$')",
            name="ck_vehiculo_placa_formato",
        ),
        CheckConstraint(f"modelo >= {MODELO_MINIMO}", name="ck_vehiculo_modelo_minimo"),
        Index("ix_vehiculo_cliente", "cliente_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    placa: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    marca: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    cliente_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cliente.id", name="fk_vehiculo_cliente", ondelete="RESTRICT"), nullable=False
    )

    cliente: Mapped[Cliente] = relationship()

    @validates("placa", "color", "marca", "tipo")
    def validate_text(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if key == "placa":
            return normalizar_placa(value)
        if key == "tipo" and value not in {"MOTO", "AUTOMOVIL", "CAMIONETA"}:
            raise ValueError("tipo debe ser MOTO, AUTOMOVIL o CAMIONETA.")
        return value

    @validates("modelo")
    def validate_modelo(self, key: str, value: int) -> int:
        # El tope "año actual + 1" depende de la fecha: lo valida la API (app.domain.reglas).
        if type(value) is not int or not MODELO_MINIMO <= value <= 9999:
            raise ValueError(f"modelo debe ser un año entero entre {MODELO_MINIMO} y 9999.")
        return value


class Celda(Base):
    __tablename__ = "celda"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_celda_codigo"),
        CheckConstraint("codigo ~ '[^[:space:]]'", name="ck_celda_codigo_no_vacio"),
        CheckConstraint("codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_celda_codigo_normalizado"),
        CheckConstraint("tipo ~ '[^[:space:]]'", name="ck_celda_tipo_no_vacio"),
        # Agregados en la migración 0004. NOT VALID: no revisa celdas antiguas, sí las nuevas.
        # La 0008 valida ck_celda_tipo y ck_celda_codigo_formato si todas las celdas existentes cumplen.
        CheckConstraint("tipo IN ('MOTO', 'CARRO')", name="ck_celda_tipo", postgresql_not_valid=True),
        Index("ix_celda_tipo_disponible", "tipo", "disponible_desde"),
        # Agregados en la migración 0007.
        CheckConstraint(f"ubicacion IS NULL OR (char_length(ubicacion) BETWEEN 1 AND {UBICACION_MAXIMA} "
                        "AND ubicacion !~ '^[[:space:]]|[[:space:]]$')", name="ck_celda_ubicacion"),
        CheckConstraint("(tipo = 'CARRO' AND codigo ~ '^C(0[1-9]|[1-9][0-9])$') OR "
                        "(tipo = 'MOTO' AND codigo ~ '^M(0[1-9]|[1-9][0-9])$')",
                        name="ck_celda_codigo_formato", postgresql_not_valid=True),
        Index("uq_celda_codigo_ci", text("upper(codigo)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    # Momento en que quedó libre por última vez. NULL = nunca se ha usado (se asigna primero).
    disponible_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Migración 0007. Una celda inhabilitada no se asigna; nunca se elimina (D4).
    ubicacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    habilitada: Mapped[bool] = mapped_column(Boolean, server_default=true(), nullable=False)

    @validates("codigo", "tipo")
    def validate_text(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if key == "tipo":
            value = value.upper()
            if value not in TIPOS_CELDA:
                raise ValueError("tipo de celda debe ser MOTO o CARRO.")
            return value
        return value.upper()


class Operador(Base):
    """La persona. Desde la Iteración 2 su acceso al sistema es una CuentaUsuario (migración 0006)."""
    __tablename__ = "operador"
    __table_args__ = (
        CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_operador_nombre_no_vacio"),
        CheckConstraint("telefono ~ '[^[:space:]]'", name="ck_operador_telefono_no_vacio"),
        # Agregado en la migración 0006. NOT VALID: no revisa personas antiguas, sí las nuevas.
        CheckConstraint(f"char_length(nombre) BETWEEN {NOMBRE_MINIMO} AND {NOMBRE_MAXIMO} "
                        "AND nombre !~ '^[[:space:]]|[[:space:]]$'",
                        name="ck_operador_nombre_longitud", postgresql_not_valid=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    # Opcional desde la migración 0006: si no se asigna queda NULL; si se asigna, no puede estar vacío.
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)

    @validates("nombre", "telefono")
    def validate_text(self, key: str, value: str) -> str:
        return required_text(value, key)


class CuentaUsuario(Base):
    """Credenciales, rol y estado de acceso de una persona. Migración 0006.

    La contraseña nunca se guarda: solo su hash bcrypt (costo >= 12, lo exige un CHECK).
    version_sesion se incrementa al desactivar la cuenta o cerrar sesión: invalida los tokens viejos.
    """
    __tablename__ = "cuenta_usuario"
    __table_args__ = (
        UniqueConstraint("operador_id", name="uq_cuenta_usuario_operador"),
        CheckConstraint(f"nombre_usuario ~ '^[a-z0-9._]{{{USUARIO_MINIMO},{USUARIO_MAXIMO}}}$'",
                        name="ck_cuenta_usuario_nombre_formato"),
        CheckConstraint("rol IN (" + ", ".join(f"'{r}'" for r in ROLES) + ")", name="ck_cuenta_usuario_rol"),
        CheckConstraint(r"hash_contrasena ~ '^\$2[aby]\$(1[2-9]|[23][0-9])\$[./A-Za-z0-9]{53}$'",
                        name="ck_cuenta_usuario_hash_bcrypt"),
        CheckConstraint("version_sesion >= 0", name="ck_cuenta_usuario_version_sesion"),
        # Único sin distinguir mayúsculas (RNF-17).
        Index("uq_cuenta_usuario_nombre", text("lower(nombre_usuario)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    operador_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_cuenta_usuario_operador", ondelete="RESTRICT"), nullable=False
    )
    nombre_usuario: Mapped[str] = mapped_column(Text, nullable=False)
    hash_contrasena: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[str] = mapped_column(Text, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, server_default=true(), nullable=False)
    version_sesion: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    persona: Mapped[Operador] = relationship()


class AuditoriaCuenta(Base):
    """Quién y cuándo creó, desactivó o reactivó una cuenta (RF-31). Migración 0006."""
    __tablename__ = "auditoria_cuenta"
    __table_args__ = (
        CheckConstraint("accion IN ('CREAR', 'DESACTIVAR', 'REACTIVAR')", name="ck_auditoria_cuenta_accion"),
        CheckConstraint("detalle IS NULL OR char_length(detalle) <= 500", name="ck_auditoria_cuenta_detalle"),
        Index("ix_auditoria_cuenta_cuenta", "cuenta_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cuenta_usuario.id", name="fk_auditoria_cuenta_cuenta", ondelete="RESTRICT"),
        nullable=False,
    )
    # NULL = lo hizo el sistema (semillas).
    actor_cuenta_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cuenta_usuario.id", name="fk_auditoria_cuenta_actor", ondelete="RESTRICT"),
        nullable=True,
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)


class Estancia(Base):
    __tablename__ = "estancia"
    __table_args__ = (
        CheckConstraint("salida >= entrada", name="ck_estancia_orden_fechas"),
        CheckConstraint(
            "(salida IS NULL) = (operador_salida_id IS NULL)",
            name="ck_estancia_cierre_completo",
        ),
        Index("uq_estancia_vehiculo_abierta", "vehiculo_id", unique=True,
              postgresql_where=text("salida IS NULL")),
        Index("uq_estancia_celda_abierta", "celda_id", unique=True,
              postgresql_where=text("salida IS NULL")),
        Index("ix_estancia_vehiculo_entrada", "vehiculo_id", "entrada"),
        Index("ix_estancia_celda", "celda_id"),   # migración 0007: historial de la celda
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehiculo.id", name="fk_estancia_vehiculo", ondelete="RESTRICT"), nullable=False
    )
    celda_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_estancia_celda", ondelete="RESTRICT"), nullable=False
    )
    entrada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operador_entrada_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_estancia_operador_entrada", ondelete="RESTRICT"), nullable=False
    )
    operador_salida_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_estancia_operador_salida", ondelete="RESTRICT"), nullable=True
    )

    vehiculo: Mapped[Vehiculo] = relationship()
    celda: Mapped[Celda] = relationship()
    operador_entrada: Mapped[Operador] = relationship(foreign_keys=[operador_entrada_id])
    operador_salida: Mapped[Operador | None] = relationship(foreign_keys=[operador_salida_id])

    def esta_abierta(self) -> bool:
        return self.salida is None

    def cerrar(self, fecha_salida: datetime, operador: Operador) -> None:
        """Valida y asigna el cierre; el servicio debe gestionar flush y commit."""
        if not self.esta_abierta():
            raise ValueError("La estancia ya está cerrada.")
        if not isinstance(fecha_salida, datetime) or fecha_salida.utcoffset() is None:
            raise ValueError("La fecha de salida debe tener zona horaria.")
        if not isinstance(self.entrada, datetime) or self.entrada.utcoffset() is None:
            raise ValueError("La entrada debe estar cargada y tener zona horaria antes de cerrar.")
        if fecha_salida.astimezone(timezone.utc) < self.entrada.astimezone(timezone.utc):
            raise ValueError("La salida no puede ser anterior a la entrada.")
        if not isinstance(operador, Operador) or operador.id is None:
            raise ValueError("El operador de salida debe tener un id asignado.")
        self.salida = fecha_salida
        self.operador_salida = operador
        self.operador_salida_id = operador.id


class Mensualidad(Base):
    """Periodo de mensualidad de un vehículo (fin inclusivo). Agregada en la migración 0003.

    Iteración 3 (migración 0010): cada pago genera su periodo (pago_id, 1 a 1). Los periodos
    anteriores no tienen pago (pago_id NULL) y siguen siendo válidos (D10). pago_estado es una copia
    del estado del pago que mantiene la base (FK compuesta con ON UPDATE CASCADE).
    """
    __tablename__ = "mensualidad"
    __table_args__ = (
        CheckConstraint("fecha_fin > fecha_inicio", name="ck_mensualidad_fechas"),
        Index("ix_mensualidad_vehiculo_fin", "vehiculo_id", "fecha_fin"),
        # Agregados en la migración 0010.
        UniqueConstraint("pago_id", name="uq_mensualidad_pago"),
        ForeignKeyConstraint(["pago_id", "pago_estado"], ["pago.id", "pago.estado"], name="fk_mensualidad_pago",
                             onupdate="CASCADE", ondelete="RESTRICT"),
        CheckConstraint("(pago_id IS NULL) = (pago_estado IS NULL)", name="ck_mensualidad_pago"),
        # Exclusión PARCIAL: dos periodos pagados y no anulados del mismo vehículo no se cruzan. Los
        # periodos antiguos no entran: algunos ya se tocan y PostgreSQL no admite EXCLUDE NOT VALID.
        ExcludeConstraint(("vehiculo_id", "="), (text("daterange(fecha_inicio, fecha_fin, '[]')"), "&&"),
                          name="ex_mensualidad_pagada_sin_superposicion", using="gist",
                          where=text("pago_estado = 'VALIDO'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehiculo.id", name="fk_mensualidad_vehiculo", ondelete="RESTRICT"), nullable=False
    )
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    pago_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pago_estado: Mapped[str | None] = mapped_column(Text, nullable=True)

    vehiculo: Mapped[Vehiculo] = relationship()


class CorreccionCelda(Base):
    """Registro de cada cambio de celda de una estancia abierta. Agregado en la migración 0005."""
    __tablename__ = "correccion_celda"
    __table_args__ = (
        CheckConstraint("celda_anterior_id <> celda_nueva_id", name="ck_correccion_celda_distinta"),
        CheckConstraint(f"motivo ~ '[^[:space:]]' AND char_length(motivo) <= {MOTIVO_MAXIMO}",
                        name="ck_correccion_celda_motivo"),
        Index("ix_correccion_celda_estancia", "estancia_id"),
        Index("ix_correccion_celda_anterior", "celda_anterior_id"),   # migración 0007
        Index("ix_correccion_celda_nueva", "celda_nueva_id"),         # migración 0007
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estancia_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("estancia.id", name="fk_correccion_celda_estancia", ondelete="RESTRICT"), nullable=False
    )
    celda_anterior_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_correccion_celda_anterior", ondelete="RESTRICT"), nullable=False
    )
    celda_nueva_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_correccion_celda_nueva", ondelete="RESTRICT"), nullable=False
    )
    operador_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_correccion_celda_operador", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)

    celda_anterior: Mapped[Celda] = relationship(foreign_keys=[celda_anterior_id])
    celda_nueva: Mapped[Celda] = relationship(foreign_keys=[celda_nueva_id])


class Novedad(Base):
    """Novedad sobre un vehículo (rayón, golpe, objeto olvidado...) durante su estancia. Migración 0005."""
    __tablename__ = "novedad"
    __table_args__ = (
        CheckConstraint("tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_NOVEDAD) + ")", name="ck_novedad_tipo"),
        CheckConstraint(f"descripcion ~ '[^[:space:]]' AND char_length(descripcion) <= {DESCRIPCION_MAXIMA}",
                        name="ck_novedad_descripcion"),
        Index("ix_novedad_estancia", "estancia_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estancia_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("estancia.id", name="fk_novedad_estancia", ondelete="RESTRICT"), nullable=False
    )
    operador_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_novedad_operador", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)


class AuditoriaCelda(Base):
    """Quién y cuándo creó, editó, inhabilitó o rehabilitó una celda (RF-31). Migración 0007."""
    __tablename__ = "auditoria_celda"
    __table_args__ = (
        CheckConstraint("accion IN ('CREAR', 'EDITAR', 'INHABILITAR', 'REHABILITAR')",
                        name="ck_auditoria_celda_accion"),
        CheckConstraint("detalle IS NULL OR char_length(detalle) <= 500", name="ck_auditoria_celda_detalle"),
        Index("ix_auditoria_celda_celda", "celda_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    celda_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_auditoria_celda_celda", ondelete="RESTRICT"), nullable=False
    )
    # NULL = lo hizo el sistema (semillas).
    actor_cuenta_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cuenta_usuario.id", name="fk_auditoria_celda_actor", ondelete="RESTRICT"),
        nullable=True,
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)


class Tarifa(Base):
    """Tarifa mensual por tipo de vehículo (D12). Migración 0009.

    Nunca se edita ni se elimina: cada cambio crea una tarifa nueva, vigente desde ese momento. Lo
    garantiza el trigger tarifa_sin_cambios de la base (RNF-24). La vigente es la más reciente.
    """
    __tablename__ = "tarifa"
    __table_args__ = (
        CheckConstraint("tipo_vehiculo IN (" + ", ".join(f"'{t}'" for t in TIPOS_VEHICULO) + ")",
                        name="ck_tarifa_tipo_vehiculo"),
        CheckConstraint(f"valor BETWEEN {TARIFA_MINIMA} AND {TARIFA_MAXIMA}", name="ck_tarifa_valor"),
        UniqueConstraint("tipo_vehiculo", "vigente_desde", name="uq_tarifa_tipo_desde"),
        UniqueConstraint("id", "tipo_vehiculo", "valor", name="uq_tarifa_id_tipo_valor"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tipo_vehiculo: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[int] = mapped_column(Integer, nullable=False)   # pesos enteros (RNF-22)
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                    nullable=False)
    # NULL = la definieron las semillas.
    definida_por_cuenta_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cuenta_usuario.id", name="fk_tarifa_definida_por", ondelete="RESTRICT"),
        nullable=True,
    )


class Pago(Base):
    """Pago de la mensualidad de un vehículo (RF-36). Migración 0010.

    Genera exactamente un periodo (mensualidad.pago_id). Nunca se edita ni se elimina: solo pasa una
    vez de VALIDO a ANULADO, con quién, cuándo y por qué (D14, D18). Lo garantiza el trigger
    pago_sin_cambios de la base (RNF-24). El comprobante RC-000001 lo numera una secuencia de la base.
    """
    __tablename__ = "pago"
    __table_args__ = (
        ForeignKeyConstraint(["tarifa_id", "tipo_vehiculo", "valor_mensual"],
                             ["tarifa.id", "tarifa.tipo_vehiculo", "tarifa.valor"], name="fk_pago_tarifa",
                             ondelete="RESTRICT"),
        UniqueConstraint("comprobante", name="uq_pago_comprobante"),
        UniqueConstraint("id", "estado", name="uq_pago_id_estado"),
        CheckConstraint("comprobante ~ '^RC-[0-9]{6}$'", name="ck_pago_comprobante_formato"),
        CheckConstraint(f"meses BETWEEN {MESES_MINIMO} AND {MESES_MAXIMO}", name="ck_pago_meses"),
        CheckConstraint("monto = valor_mensual * meses", name="ck_pago_monto"),
        CheckConstraint("metodo IN (" + ", ".join(f"'{m}'" for m in METODOS_PAGO) + ")", name="ck_pago_metodo"),
        # NULL ~ patrón da NULL y un CHECK con NULL pasa: por eso el IS NOT NULL explícito.
        CheckConstraint("(metodo = 'EFECTIVO' AND referencia IS NULL) OR (metodo <> 'EFECTIVO' AND referencia IS NOT NULL "
                        f"AND referencia ~ '^[A-Za-z0-9-]{{{REFERENCIA_MINIMA},{REFERENCIA_MAXIMA}}}$')",
                        name="ck_pago_referencia"),
        CheckConstraint("estado IN ('VALIDO', 'ANULADO')", name="ck_pago_estado"),
        CheckConstraint(
            "(estado = 'VALIDO' AND anulado_en IS NULL AND anulado_por_cuenta_id IS NULL AND motivo_anulacion IS NULL) "
            "OR (estado = 'ANULADO' AND anulado_en IS NOT NULL AND anulado_por_cuenta_id IS NOT NULL "
            f"AND motivo_anulacion IS NOT NULL AND char_length(motivo_anulacion) BETWEEN {MOTIVO_ANULACION_MINIMO} "
            f"AND {MOTIVO_ANULACION_MAXIMO} AND motivo_anulacion !~ '^[[:space:]]|[[:space:]]$' AND anulado_en >= fecha)",
            name="ck_pago_anulacion"),
        Index("ix_pago_fecha", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    comprobante: Mapped[str] = mapped_column(
        Text, nullable=False,
        server_default=text("('RC-'::text || lpad((nextval('pago_comprobante_seq'::regclass))::text, 6, '0'::text))"),
    )
    meses: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tarifa_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tipo_vehiculo: Mapped[str] = mapped_column(Text, nullable=False)   # el tipo con que se cobró
    valor_mensual: Mapped[int] = mapped_column(Integer, nullable=False)
    monto: Mapped[int] = mapped_column(Integer, nullable=False)        # pesos enteros (RNF-22)
    metodo: Mapped[str] = mapped_column(Text, nullable=False)
    referencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    registrado_por_cuenta_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cuenta_usuario.id", name="fk_pago_registrado_por", ondelete="RESTRICT"), nullable=False
    )
    estado: Mapped[str] = mapped_column(Text, server_default="VALIDO", nullable=False)
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    anulado_por_cuenta_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cuenta_usuario.id", name="fk_pago_anulado_por", ondelete="RESTRICT"), nullable=True
    )
    motivo_anulacion: Mapped[str | None] = mapped_column(Text, nullable=True)
