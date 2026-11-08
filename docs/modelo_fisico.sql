-- Modelo físico de la base de datos de Autos Colombia (Iteraciones 1 y 2).
-- Esquema real exportado del contenedor, con las migraciones 0001–0008 aplicadas:
--   docker compose exec -T db pg_dump --schema-only --no-owner --no-privileges > docs/modelo_fisico.sql
-- Las líneas \restrict / \unrestrict las agrega pg_dump (PostgreSQL 17.6 o superior) como protección de psql.
--
-- PostgreSQL database dump
--

\restrict yD8mmha9kEpJHvgSSiPv5x42oggpjPbGR1UdVpcLzDyjZ6P7GXidSc4chVJpiCb

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
    CONSTRAINT ck_cliente_correo_formato CHECK (((correo IS NULL) OR (correo ~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'::text))),
    CONSTRAINT ck_cliente_documento_no_vacio CHECK ((documento ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_nombre_no_vacio CHECK ((nombre ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_telefono_no_vacio CHECK ((telefono ~ '[^[:space:]]'::text))
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
    CONSTRAINT ck_mensualidad_fechas CHECK ((fecha_fin > fecha_inicio))
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
-- Name: celda uq_celda_codigo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.celda
    ADD CONSTRAINT uq_celda_codigo UNIQUE (codigo);


--
-- Name: cliente uq_cliente_documento; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT uq_cliente_documento UNIQUE (documento);


--
-- Name: cuenta_usuario uq_cuenta_usuario_operador; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_usuario
    ADD CONSTRAINT uq_cuenta_usuario_operador UNIQUE (operador_id);


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
-- Name: ix_vehiculo_cliente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vehiculo_cliente ON public.vehiculo USING btree (cliente_id);


--
-- Name: uq_celda_codigo_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_celda_codigo_ci ON public.celda USING btree (upper(codigo));


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
-- Name: vehiculo fk_vehiculo_cliente; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculo
    ADD CONSTRAINT fk_vehiculo_cliente FOREIGN KEY (cliente_id) REFERENCES public.cliente(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict yD8mmha9kEpJHvgSSiPv5x42oggpjPbGR1UdVpcLzDyjZ6P7GXidSc4chVJpiCb

