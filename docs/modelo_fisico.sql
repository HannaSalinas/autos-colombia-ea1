-- Modelo físico de la base de datos de Autos Colombia (Iteraciones 1, 2 y 3).
-- Esquema real exportado del contenedor, con las migraciones 0001–0011 aplicadas:
--   docker compose exec -T db pg_dump --schema-only --no-owner --no-privileges > docs/modelo_fisico.sql
-- Las líneas \restrict / \unrestrict las agrega pg_dump (PostgreSQL 17.6 o superior) como protección de psql.
--
-- PostgreSQL database dump
--

\restrict Xd1mHnToKMLkpAdAubeVyy6uLCkJi6FAxES8JxhjGB4NPH5TaMWUgzQfxdQa2xV

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: mensualidad_pagada_inmutable(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mensualidad_pagada_inmutable() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.pago_id IS NOT NULL THEN
            RAISE EXCEPTION 'Un periodo pagado no se elimina: para dejarlo sin efecto se anula su pago.'
                USING ERRCODE = '23001';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.pago_id IS NULL AND NEW.pago_id IS NOT NULL THEN
        RAISE EXCEPTION 'Un periodo existente no se puede vincular a un pago: cada pago genera su propio periodo.'
            USING ERRCODE = '23001';
    END IF;
    -- Lo único que cambia en un periodo pagado es la copia del estado de su pago (ON UPDATE CASCADE).
    IF OLD.pago_id IS NOT NULL
       AND (NEW.vehiculo_id, NEW.fecha_inicio, NEW.fecha_fin, NEW.pago_id)
           IS DISTINCT FROM (OLD.vehiculo_id, OLD.fecha_inicio, OLD.fecha_fin, OLD.pago_id) THEN
        RAISE EXCEPTION 'Un periodo pagado no se edita: para corregirlo se anula su pago y se registra otro.'
            USING ERRCODE = '23001';
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: mensualidad_sin_vaciar(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mensualidad_sin_vaciar() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM mensualidad WHERE pago_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Un periodo pagado no se elimina: para dejarlo sin efecto se anula su pago.'
            USING ERRCODE = '23001';
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: pago_solo_anular(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pago_solo_anular() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.estado = 'VALIDO' AND NEW.estado = 'ANULADO'
           AND (NEW.id, NEW.comprobante, NEW.meses, NEW.tarifa_id, NEW.tipo_vehiculo, NEW.valor_mensual, NEW.monto, NEW.metodo, NEW.referencia, NEW.fecha, NEW.registrado_por_cuenta_id)
               IS NOT DISTINCT FROM (OLD.id, OLD.comprobante, OLD.meses, OLD.tarifa_id, OLD.tipo_vehiculo, OLD.valor_mensual, OLD.monto, OLD.metodo, OLD.referencia, OLD.fecha, OLD.registrado_por_cuenta_id) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'Un pago no se edita ni se elimina: solo puede pasar una vez de VALIDO a ANULADO, con sus datos de anulación.'
        USING ERRCODE = '23001';
END;
$$;


--
-- Name: tarifa_inmutable(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.tarifa_inmutable() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'Las tarifas no se editan ni se eliminan: para cambiar el valor se crea una tarifa nueva.'
        USING ERRCODE = '23001';
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: auditoria_celda; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auditoria_celda (
    id bigint NOT NULL,
    celda_id bigint NOT NULL,
    actor_cuenta_id bigint,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    accion text NOT NULL,
    detalle text,
    CONSTRAINT ck_auditoria_celda_accion CHECK ((accion = ANY (ARRAY['CREAR'::text, 'EDITAR'::text, 'INHABILITAR'::text, 'REHABILITAR'::text]))),
    CONSTRAINT ck_auditoria_celda_detalle CHECK (((detalle IS NULL) OR (char_length(detalle) <= 500)))
);


--
-- Name: auditoria_celda_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auditoria_celda ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.auditoria_celda_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auditoria_cuenta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auditoria_cuenta (
    id bigint NOT NULL,
    cuenta_id bigint NOT NULL,
    actor_cuenta_id bigint,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    accion text NOT NULL,
    detalle text,
    CONSTRAINT ck_auditoria_cuenta_accion CHECK ((accion = ANY (ARRAY['CREAR'::text, 'DESACTIVAR'::text, 'REACTIVAR'::text]))),
    CONSTRAINT ck_auditoria_cuenta_detalle CHECK (((detalle IS NULL) OR (char_length(detalle) <= 500)))
);


--
-- Name: auditoria_cuenta_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auditoria_cuenta ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.auditoria_cuenta_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: celda; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.celda (
    id bigint NOT NULL,
    codigo text NOT NULL,
    tipo text NOT NULL,
    disponible_desde timestamp with time zone,
    ubicacion text,
    habilitada boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_celda_codigo_formato CHECK ((((tipo = 'CARRO'::text) AND (codigo ~ '^C(0[1-9]|[1-9][0-9])$'::text)) OR ((tipo = 'MOTO'::text) AND (codigo ~ '^M(0[1-9]|[1-9][0-9])$'::text)))),
    CONSTRAINT ck_celda_codigo_no_vacio CHECK ((codigo ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_celda_codigo_normalizado CHECK ((codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$'::text, ''::text, 'g'::text)))),
    CONSTRAINT ck_celda_tipo CHECK ((tipo = ANY (ARRAY['MOTO'::text, 'CARRO'::text]))),
    CONSTRAINT ck_celda_tipo_no_vacio CHECK ((tipo ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_celda_ubicacion CHECK (((ubicacion IS NULL) OR (((char_length(ubicacion) >= 1) AND (char_length(ubicacion) <= 60)) AND (ubicacion !~ '^[[:space:]]|[[:space:]]$'::text))))
);


--
-- Name: celda_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.celda ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.celda_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cliente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cliente (
    id bigint NOT NULL,
    documento text NOT NULL,
    nombre text NOT NULL,
    telefono text NOT NULL,
    correo text,
    tipo_documento text NOT NULL,
    registrado_en timestamp with time zone,
    registrado_por_cuenta_id bigint,
    CONSTRAINT ck_cliente_correo_formato CHECK (((correo IS NULL) OR (correo ~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'::text))),
    CONSTRAINT ck_cliente_documento_formato CHECK ((documento ~ '^[A-Z0-9]{5,15}$'::text)),
    CONSTRAINT ck_cliente_documento_no_vacio CHECK ((documento ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_nombre_longitud CHECK ((((char_length(nombre) >= 3) AND (char_length(nombre) <= 80)) AND (nombre !~ '^[[:space:]]|[[:space:]]$'::text))),
    CONSTRAINT ck_cliente_nombre_no_vacio CHECK ((nombre ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_registro CHECK (((registrado_por_cuenta_id IS NULL) OR (registrado_en IS NOT NULL))),
    CONSTRAINT ck_cliente_telefono_formato CHECK ((telefono ~ '^[0-9]{10}$'::text)),
    CONSTRAINT ck_cliente_telefono_no_vacio CHECK ((telefono ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_tipo_documento CHECK ((tipo_documento = ANY (ARRAY['CC'::text, 'CE'::text, 'PA'::text])))
);


--
-- Name: cliente_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cliente ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cliente_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: correccion_celda; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.correccion_celda (
    id bigint NOT NULL,
    estancia_id bigint NOT NULL,
    celda_anterior_id bigint NOT NULL,
    celda_nueva_id bigint NOT NULL,
    operador_id bigint NOT NULL,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    motivo text NOT NULL,
    CONSTRAINT ck_correccion_celda_distinta CHECK ((celda_anterior_id <> celda_nueva_id)),
    CONSTRAINT ck_correccion_celda_motivo CHECK (((motivo ~ '[^[:space:]]'::text) AND (char_length(motivo) <= 200)))
);


--
-- Name: correccion_celda_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.correccion_celda ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.correccion_celda_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cuenta_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cuenta_usuario (
    id bigint NOT NULL,
    operador_id bigint NOT NULL,
    nombre_usuario text NOT NULL,
    hash_contrasena text NOT NULL,
    rol text NOT NULL,
    activa boolean DEFAULT true NOT NULL,
    version_sesion integer DEFAULT 0 NOT NULL,
    creada_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_cuenta_usuario_hash_bcrypt CHECK ((hash_contrasena ~ '^\$2[aby]\$(1[2-9]|[23][0-9])\$[./A-Za-z0-9]{53}$'::text)),
    CONSTRAINT ck_cuenta_usuario_nombre_formato CHECK ((nombre_usuario ~ '^[a-z0-9._]{4,30}$'::text)),
    CONSTRAINT ck_cuenta_usuario_rol CHECK ((rol = ANY (ARRAY['ADMINISTRADOR'::text, 'OPERADOR'::text]))),
    CONSTRAINT ck_cuenta_usuario_version_sesion CHECK ((version_sesion >= 0))
);


--
-- Name: cuenta_usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cuenta_usuario ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cuenta_usuario_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: estancia; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.estancia (
    id bigint NOT NULL,
    vehiculo_id bigint NOT NULL,
    celda_id bigint NOT NULL,
    entrada timestamp with time zone DEFAULT now() NOT NULL,
    salida timestamp with time zone,
    operador_entrada_id bigint NOT NULL,
    operador_salida_id bigint,
    CONSTRAINT ck_estancia_cierre_completo CHECK (((salida IS NULL) = (operador_salida_id IS NULL))),
    CONSTRAINT ck_estancia_orden_fechas CHECK ((salida >= entrada))
);


--
-- Name: estancia_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.estancia ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.estancia_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: mensualidad; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mensualidad (
    id bigint NOT NULL,
    vehiculo_id bigint NOT NULL,
    fecha_inicio date NOT NULL,
    fecha_fin date NOT NULL,
    pago_id bigint,
    pago_estado text,
    CONSTRAINT ck_mensualidad_fechas CHECK ((fecha_fin > fecha_inicio)),
    CONSTRAINT ck_mensualidad_pago CHECK (((pago_id IS NULL) = (pago_estado IS NULL)))
);


--
-- Name: mensualidad_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.mensualidad ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.mensualidad_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: novedad; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.novedad (
    id bigint NOT NULL,
    estancia_id bigint NOT NULL,
    operador_id bigint NOT NULL,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    tipo text NOT NULL,
    descripcion text NOT NULL,
    CONSTRAINT ck_novedad_descripcion CHECK (((descripcion ~ '[^[:space:]]'::text) AND (char_length(descripcion) <= 500))),
    CONSTRAINT ck_novedad_tipo CHECK ((tipo = ANY (ARRAY['RAYON'::text, 'GOLPE'::text, 'OBJETO_OLVIDADO'::text, 'OTRO'::text])))
);


--
-- Name: novedad_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.novedad ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.novedad_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: operador; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operador (
    id bigint NOT NULL,
    nombre text NOT NULL,
    telefono text,
    CONSTRAINT ck_operador_nombre_no_vacio CHECK ((nombre ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_operador_telefono_no_vacio CHECK ((telefono ~ '[^[:space:]]'::text))
);


--
-- Name: operador_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.operador ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.operador_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: pago; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pago (
    id bigint NOT NULL,
    comprobante text NOT NULL,
    meses smallint NOT NULL,
    tarifa_id bigint NOT NULL,
    tipo_vehiculo text NOT NULL,
    valor_mensual integer NOT NULL,
    monto integer NOT NULL,
    metodo text NOT NULL,
    referencia text,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    registrado_por_cuenta_id bigint NOT NULL,
    estado text DEFAULT 'VALIDO'::text NOT NULL,
    anulado_en timestamp with time zone,
    anulado_por_cuenta_id bigint,
    motivo_anulacion text,
    CONSTRAINT ck_pago_anulacion CHECK ((((estado = 'VALIDO'::text) AND (anulado_en IS NULL) AND (anulado_por_cuenta_id IS NULL) AND (motivo_anulacion IS NULL)) OR ((estado = 'ANULADO'::text) AND (anulado_en IS NOT NULL) AND (anulado_por_cuenta_id IS NOT NULL) AND (motivo_anulacion IS NOT NULL) AND ((char_length(motivo_anulacion) >= 10) AND (char_length(motivo_anulacion) <= 200)) AND (motivo_anulacion !~ '^[[:space:]]|[[:space:]]$'::text) AND (anulado_en >= fecha)))),
    CONSTRAINT ck_pago_comprobante_formato CHECK ((comprobante ~ '^RC-[0-9]{6}$'::text)),
    CONSTRAINT ck_pago_estado CHECK ((estado = ANY (ARRAY['VALIDO'::text, 'ANULADO'::text]))),
    CONSTRAINT ck_pago_meses CHECK (((meses >= 1) AND (meses <= 6))),
    CONSTRAINT ck_pago_metodo CHECK ((metodo = ANY (ARRAY['EFECTIVO'::text, 'TRANSFERENCIA'::text, 'TARJETA'::text]))),
    CONSTRAINT ck_pago_monto CHECK ((monto = (valor_mensual * meses))),
    CONSTRAINT ck_pago_referencia CHECK ((((metodo = 'EFECTIVO'::text) AND (referencia IS NULL)) OR ((metodo <> 'EFECTIVO'::text) AND (referencia IS NOT NULL) AND (referencia ~ '^[A-Za-z0-9-]{4,30}$'::text))))
);


--
-- Name: pago_comprobante_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pago_comprobante_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1;


--
-- Name: pago_comprobante_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pago_comprobante_seq OWNED BY public.pago.comprobante;


--
-- Name: pago_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.pago ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.pago_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tarifa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tarifa (
    id bigint NOT NULL,
    tipo_vehiculo text NOT NULL,
    valor integer NOT NULL,
    vigente_desde timestamp with time zone DEFAULT now() NOT NULL,
    definida_por_cuenta_id bigint,
    CONSTRAINT ck_tarifa_tipo_vehiculo CHECK ((tipo_vehiculo = ANY (ARRAY['MOTO'::text, 'AUTOMOVIL'::text, 'CAMIONETA'::text]))),
    CONSTRAINT ck_tarifa_valor CHECK (((valor >= 1000) AND (valor <= 2000000)))
);


--
-- Name: tarifa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.tarifa ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.tarifa_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: vehiculo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehiculo (
    id bigint NOT NULL,
    placa text NOT NULL,
    color text NOT NULL,
    modelo integer NOT NULL,
    marca text NOT NULL,
    tipo text NOT NULL,
    cliente_id bigint NOT NULL,
    CONSTRAINT ck_vehiculo_color_no_vacio CHECK ((color ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_vehiculo_marca_no_vacia CHECK ((marca ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_vehiculo_modelo_anio CHECK (((modelo >= 1) AND (modelo <= 9999))),
    CONSTRAINT ck_vehiculo_modelo_minimo CHECK ((modelo >= 1900)),
    CONSTRAINT ck_vehiculo_placa_formato CHECK ((((tipo = 'MOTO'::text) AND (placa ~ '^[A-Z]{3}[0-9]{2}[A-Z]$'::text)) OR ((tipo <> 'MOTO'::text) AND (placa ~ '^[A-Z]{3}[0-9]{3}$'::text)))),
    CONSTRAINT ck_vehiculo_placa_no_vacia CHECK ((placa ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_vehiculo_placa_normalizada CHECK ((placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$'::text, ''::text, 'g'::text)))),
    CONSTRAINT ck_vehiculo_tipo CHECK ((tipo = ANY (ARRAY['MOTO'::text, 'AUTOMOVIL'::text, 'CAMIONETA'::text])))
);


--
-- Name: vehiculo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.vehiculo ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.vehiculo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: pago comprobante; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago ALTER COLUMN comprobante SET DEFAULT ('RC-'::text || lpad((nextval('public.pago_comprobante_seq'::regclass))::text, 6, '0'::text));


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: auditoria_celda auditoria_celda_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_celda
    ADD CONSTRAINT auditoria_celda_pkey PRIMARY KEY (id);


--
-- Name: auditoria_cuenta auditoria_cuenta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_cuenta
    ADD CONSTRAINT auditoria_cuenta_pkey PRIMARY KEY (id);


--
-- Name: celda celda_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celda
    ADD CONSTRAINT celda_pkey PRIMARY KEY (id);


--
-- Name: operador ck_operador_nombre_longitud; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.operador
    ADD CONSTRAINT ck_operador_nombre_longitud CHECK ((((char_length(nombre) >= 3) AND (char_length(nombre) <= 80)) AND (nombre !~ '^[[:space:]]|[[:space:]]$'::text))) NOT VALID;


--
-- Name: cliente cliente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT cliente_pkey PRIMARY KEY (id);


--
-- Name: correccion_celda correccion_celda_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correccion_celda
    ADD CONSTRAINT correccion_celda_pkey PRIMARY KEY (id);


--
-- Name: cuenta_usuario cuenta_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_usuario
    ADD CONSTRAINT cuenta_usuario_pkey PRIMARY KEY (id);


--
-- Name: estancia estancia_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT estancia_pkey PRIMARY KEY (id);


--
-- Name: mensualidad ex_mensualidad_pagada_sin_superposicion; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensualidad
    ADD CONSTRAINT ex_mensualidad_pagada_sin_superposicion EXCLUDE USING gist (vehiculo_id WITH =, daterange(fecha_inicio, fecha_fin, '[]'::text) WITH &&) WHERE ((pago_estado = 'VALIDO'::text));


--
-- Name: mensualidad mensualidad_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensualidad
    ADD CONSTRAINT mensualidad_pkey PRIMARY KEY (id);


--
-- Name: novedad novedad_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.novedad
    ADD CONSTRAINT novedad_pkey PRIMARY KEY (id);


--
-- Name: operador operador_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operador
    ADD CONSTRAINT operador_pkey PRIMARY KEY (id);


--
-- Name: pago pago_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT pago_pkey PRIMARY KEY (id);


--
-- Name: tarifa tarifa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarifa
    ADD CONSTRAINT tarifa_pkey PRIMARY KEY (id);


--
-- Name: celda uq_celda_codigo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celda
    ADD CONSTRAINT uq_celda_codigo UNIQUE (codigo);


--
-- Name: cuenta_usuario uq_cuenta_usuario_operador; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_usuario
    ADD CONSTRAINT uq_cuenta_usuario_operador UNIQUE (operador_id);


--
-- Name: mensualidad uq_mensualidad_pago; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensualidad
    ADD CONSTRAINT uq_mensualidad_pago UNIQUE (pago_id);


--
-- Name: pago uq_pago_comprobante; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT uq_pago_comprobante UNIQUE (comprobante);


--
-- Name: pago uq_pago_id_estado; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT uq_pago_id_estado UNIQUE (id, estado);


--
-- Name: tarifa uq_tarifa_id_tipo_valor; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarifa
    ADD CONSTRAINT uq_tarifa_id_tipo_valor UNIQUE (id, tipo_vehiculo, valor);


--
-- Name: tarifa uq_tarifa_tipo_desde; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarifa
    ADD CONSTRAINT uq_tarifa_tipo_desde UNIQUE (tipo_vehiculo, vigente_desde);


--
-- Name: vehiculo uq_vehiculo_placa; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculo
    ADD CONSTRAINT uq_vehiculo_placa UNIQUE (placa);


--
-- Name: vehiculo vehiculo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculo
    ADD CONSTRAINT vehiculo_pkey PRIMARY KEY (id);


--
-- Name: ix_auditoria_celda_celda; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditoria_celda_celda ON public.auditoria_celda USING btree (celda_id, fecha);


--
-- Name: ix_auditoria_cuenta_cuenta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditoria_cuenta_cuenta ON public.auditoria_cuenta USING btree (cuenta_id, fecha);


--
-- Name: ix_celda_tipo_disponible; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_celda_tipo_disponible ON public.celda USING btree (tipo, disponible_desde);


--
-- Name: ix_correccion_celda_anterior; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_correccion_celda_anterior ON public.correccion_celda USING btree (celda_anterior_id);


--
-- Name: ix_correccion_celda_estancia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_correccion_celda_estancia ON public.correccion_celda USING btree (estancia_id);


--
-- Name: ix_correccion_celda_nueva; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_correccion_celda_nueva ON public.correccion_celda USING btree (celda_nueva_id);


--
-- Name: ix_estancia_celda; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_estancia_celda ON public.estancia USING btree (celda_id);


--
-- Name: ix_estancia_vehiculo_entrada; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_estancia_vehiculo_entrada ON public.estancia USING btree (vehiculo_id, entrada);


--
-- Name: ix_mensualidad_vehiculo_fin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensualidad_vehiculo_fin ON public.mensualidad USING btree (vehiculo_id, fecha_fin);


--
-- Name: ix_novedad_estancia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_novedad_estancia ON public.novedad USING btree (estancia_id);


--
-- Name: ix_pago_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pago_fecha ON public.pago USING btree (fecha);


--
-- Name: ix_vehiculo_cliente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vehiculo_cliente ON public.vehiculo USING btree (cliente_id);


--
-- Name: uq_celda_codigo_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_celda_codigo_ci ON public.celda USING btree (upper(codigo));


--
-- Name: uq_cliente_tipo_documento; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cliente_tipo_documento ON public.cliente USING btree (tipo_documento, upper(documento));


--
-- Name: uq_cuenta_usuario_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cuenta_usuario_nombre ON public.cuenta_usuario USING btree (lower(nombre_usuario));


--
-- Name: uq_estancia_celda_abierta; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_estancia_celda_abierta ON public.estancia USING btree (celda_id) WHERE (salida IS NULL);


--
-- Name: uq_estancia_vehiculo_abierta; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_estancia_vehiculo_abierta ON public.estancia USING btree (vehiculo_id) WHERE (salida IS NULL);


--
-- Name: mensualidad mensualidad_pagada_sin_cambios; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER mensualidad_pagada_sin_cambios BEFORE DELETE OR UPDATE ON public.mensualidad FOR EACH ROW EXECUTE FUNCTION public.mensualidad_pagada_inmutable();


--
-- Name: mensualidad mensualidad_pagada_sin_vaciar; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER mensualidad_pagada_sin_vaciar BEFORE TRUNCATE ON public.mensualidad FOR EACH STATEMENT EXECUTE FUNCTION public.mensualidad_sin_vaciar();


--
-- Name: pago pago_sin_cambios; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER pago_sin_cambios BEFORE DELETE OR UPDATE ON public.pago FOR EACH ROW EXECUTE FUNCTION public.pago_solo_anular();


--
-- Name: pago pago_sin_vaciar; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER pago_sin_vaciar BEFORE TRUNCATE ON public.pago FOR EACH STATEMENT EXECUTE FUNCTION public.pago_solo_anular();


--
-- Name: tarifa tarifa_sin_cambios; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tarifa_sin_cambios BEFORE DELETE OR UPDATE ON public.tarifa FOR EACH ROW EXECUTE FUNCTION public.tarifa_inmutable();


--
-- Name: tarifa tarifa_sin_vaciar; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tarifa_sin_vaciar BEFORE TRUNCATE ON public.tarifa FOR EACH STATEMENT EXECUTE FUNCTION public.tarifa_inmutable();


--
-- Name: auditoria_celda fk_auditoria_celda_actor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_celda
    ADD CONSTRAINT fk_auditoria_celda_actor FOREIGN KEY (actor_cuenta_id) REFERENCES public.cuenta_usuario(id) ON DELETE RESTRICT;


--
-- Name: auditoria_celda fk_auditoria_celda_celda; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_celda
    ADD CONSTRAINT fk_auditoria_celda_celda FOREIGN KEY (celda_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- Name: auditoria_cuenta fk_auditoria_cuenta_actor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_cuenta
    ADD CONSTRAINT fk_auditoria_cuenta_actor FOREIGN KEY (actor_cuenta_id) REFERENCES public.cuenta_usuario(id) ON DELETE RESTRICT;


--
-- Name: auditoria_cuenta fk_auditoria_cuenta_cuenta; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_cuenta
    ADD CONSTRAINT fk_auditoria_cuenta_cuenta FOREIGN KEY (cuenta_id) REFERENCES public.cuenta_usuario(id) ON DELETE RESTRICT;


--
-- Name: cliente fk_cliente_registrado_por; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT fk_cliente_registrado_por FOREIGN KEY (registrado_por_cuenta_id) REFERENCES public.cuenta_usuario(id) ON DELETE RESTRICT;


--
-- Name: correccion_celda fk_correccion_celda_anterior; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correccion_celda
    ADD CONSTRAINT fk_correccion_celda_anterior FOREIGN KEY (celda_anterior_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- Name: correccion_celda fk_correccion_celda_estancia; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correccion_celda
    ADD CONSTRAINT fk_correccion_celda_estancia FOREIGN KEY (estancia_id) REFERENCES public.estancia(id) ON DELETE RESTRICT;


--
-- Name: correccion_celda fk_correccion_celda_nueva; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correccion_celda
    ADD CONSTRAINT fk_correccion_celda_nueva FOREIGN KEY (celda_nueva_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- Name: correccion_celda fk_correccion_celda_operador; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correccion_celda
    ADD CONSTRAINT fk_correccion_celda_operador FOREIGN KEY (operador_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- Name: cuenta_usuario fk_cuenta_usuario_operador; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_usuario
    ADD CONSTRAINT fk_cuenta_usuario_operador FOREIGN KEY (operador_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- Name: estancia fk_estancia_celda; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_celda FOREIGN KEY (celda_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- Name: estancia fk_estancia_operador_entrada; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_operador_entrada FOREIGN KEY (operador_entrada_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- Name: estancia fk_estancia_operador_salida; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_operador_salida FOREIGN KEY (operador_salida_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- Name: estancia fk_estancia_vehiculo; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_vehiculo FOREIGN KEY (vehiculo_id) REFERENCES public.vehiculo(id) ON DELETE RESTRICT;


--
-- Name: mensualidad fk_mensualidad_pago; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensualidad
    ADD CONSTRAINT fk_mensualidad_pago FOREIGN KEY (pago_id, pago_estado) REFERENCES public.pago(id, estado) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: mensualidad fk_mensualidad_vehiculo; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensualidad
    ADD CONSTRAINT fk_mensualidad_vehiculo FOREIGN KEY (vehiculo_id) REFERENCES public.vehiculo(id) ON DELETE RESTRICT;


--
-- Name: novedad fk_novedad_estancia; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.novedad
    ADD CONSTRAINT fk_novedad_estancia FOREIGN KEY (estancia_id) REFERENCES public.estancia(id) ON DELETE RESTRICT;


--
-- Name: novedad fk_novedad_operador; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.novedad
    ADD CONSTRAINT fk_novedad_operador FOREIGN KEY (operador_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- Name: pago fk_pago_anulado_por; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT fk_pago_anulado_por FOREIGN KEY (anulado_por_cuenta_id) REFERENCES public.cuenta_usuario(id) ON DELETE RESTRICT;


--
-- Name: pago fk_pago_registrado_por; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT fk_pago_registrado_por FOREIGN KEY (registrado_por_cuenta_id) REFERENCES public.cuenta_usuario(id) ON DELETE RESTRICT;


--
-- Name: pago fk_pago_tarifa; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT fk_pago_tarifa FOREIGN KEY (tarifa_id, tipo_vehiculo, valor_mensual) REFERENCES public.tarifa(id, tipo_vehiculo, valor) ON DELETE RESTRICT;


--
-- Name: tarifa fk_tarifa_definida_por; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarifa
    ADD CONSTRAINT fk_tarifa_definida_por FOREIGN KEY (definida_por_cuenta_id) REFERENCES public.cuenta_usuario(id) ON DELETE RESTRICT;


--
-- Name: vehiculo fk_vehiculo_cliente; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculo
    ADD CONSTRAINT fk_vehiculo_cliente FOREIGN KEY (cliente_id) REFERENCES public.cliente(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict Xd1mHnToKMLkpAdAubeVyy6uLCkJi6FAxES8JxhjGB4NPH5TaMWUgzQfxdQa2xV

