--
-- PostgreSQL database dump
--

-- Dumped from database version 12.7
-- Dumped by pg_dump version 14.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: hstore; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS hstore WITH SCHEMA public;


--
-- Name: EXTENSION hstore; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION hstore IS 'data type for storing sets of (key, value) pairs';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acme_user_v2; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acme_user_v2 (
    id integer NOT NULL,
    email character varying NOT NULL,
    uri character varying NOT NULL,
    private_key_pem text,
    registration_json text
);


--
-- Name: acme_user_v2_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acme_user_v2_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acme_user_v2_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acme_user_v2_id_seq OWNED BY public.acme_user_v2.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificates (
    id integer NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone,
    route_id integer,
    domain text,
    cert_url text,
    certificate bytea,
    expires timestamp with time zone,
    private_key_pem character varying,
    csr_pem text,
    order_json text,
    fullchain_pem text,
    leaf_pem text,
    iam_server_certificate_id text,
    iam_server_certificate_name text,
    iam_server_certificate_arn text
);


--
-- Name: certificates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.certificates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: certificates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.certificates_id_seq OWNED BY public.certificates.id;


--
-- Name: challenges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.challenges (
    id integer NOT NULL,
    certificate_id integer NOT NULL,
    domain character varying NOT NULL,
    validation_path character varying NOT NULL,
    validation_contents text NOT NULL,
    body_json text,
    answered boolean
);


--
-- Name: challenges_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.challenges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: challenges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.challenges_id_seq OWNED BY public.challenges.id;


--
-- Name: operations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operations (
    id integer NOT NULL,
    route_id integer NOT NULL,
    state text DEFAULT 'in progress'::text NOT NULL,
    action text DEFAULT 'renew'::text NOT NULL,
    certificate_id integer
);


--
-- Name: operations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.operations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: operations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.operations_id_seq OWNED BY public.operations.id;


--
-- Name: routes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.routes (
    id integer NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone,
    instance_id text NOT NULL,
    state text NOT NULL,
    domain_external text,
    domain_internal text,
    dist_id text,
    origin text,
    path text,
    insecure_origin boolean,
    challenge_json bytea,
    user_data_id integer,
    acme_user_id integer
);


--
-- Name: routes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.routes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: routes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.routes_id_seq OWNED BY public.routes.id;


--
-- Name: user_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_data (
    id integer NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone,
    email text NOT NULL,
    reg bytea,
    key bytea
);


--
-- Name: user_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_data_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_data_id_seq OWNED BY public.user_data.id;


--
-- Name: acme_user_v2 id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acme_user_v2 ALTER COLUMN id SET DEFAULT nextval('public.acme_user_v2_id_seq'::regclass);


--
-- Name: certificates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates ALTER COLUMN id SET DEFAULT nextval('public.certificates_id_seq'::regclass);


--
-- Name: challenges id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenges ALTER COLUMN id SET DEFAULT nextval('public.challenges_id_seq'::regclass);


--
-- Name: operations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operations ALTER COLUMN id SET DEFAULT nextval('public.operations_id_seq'::regclass);


--
-- Name: routes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes ALTER COLUMN id SET DEFAULT nextval('public.routes_id_seq'::regclass);


--
-- Name: user_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_data ALTER COLUMN id SET DEFAULT nextval('public.user_data_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: certificates certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT certificates_pkey PRIMARY KEY (id);


--
-- Name: acme_user_v2 pk_acme_user_v2; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acme_user_v2
    ADD CONSTRAINT pk_acme_user_v2 PRIMARY KEY (id);


--
-- Name: challenges pk_challenges; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenges
    ADD CONSTRAINT pk_challenges PRIMARY KEY (id);


--
-- Name: operations pk_operations; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operations
    ADD CONSTRAINT pk_operations PRIMARY KEY (id);


--
-- Name: routes routes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_pkey PRIMARY KEY (id);


--
-- Name: user_data user_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_data
    ADD CONSTRAINT user_data_pkey PRIMARY KEY (id);


--
-- Name: idx_certificates_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certificates_deleted_at ON public.certificates USING btree (deleted_at);


--
-- Name: idx_certificates_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certificates_expires ON public.certificates USING btree (expires);


--
-- Name: idx_routes_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routes_deleted_at ON public.routes USING btree (deleted_at);


--
-- Name: idx_routes_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routes_instance_id ON public.routes USING btree (instance_id);


--
-- Name: idx_routes_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routes_state ON public.routes USING btree (state);


--
-- Name: idx_user_data_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_data_deleted_at ON public.user_data USING btree (deleted_at);


--
-- Name: uix_routes_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uix_routes_instance_id ON public.routes USING btree (instance_id);


--
-- Name: challenges fk_challenges_certificate_id_certificates; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenges
    ADD CONSTRAINT fk_challenges_certificate_id_certificates FOREIGN KEY (certificate_id) REFERENCES public.certificates(id);


--
-- Name: operations fk_operations_certificate_id_certificates; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operations
    ADD CONSTRAINT fk_operations_certificate_id_certificates FOREIGN KEY (certificate_id) REFERENCES public.certificates(id);


--
-- Name: operations fk_operations_route_id_routes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operations
    ADD CONSTRAINT fk_operations_route_id_routes FOREIGN KEY (route_id) REFERENCES public.routes(id);


--
-- Name: routes fk_routes_acme_user_id_acme_user_v2; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT fk_routes_acme_user_id_acme_user_v2 FOREIGN KEY (acme_user_id) REFERENCES public.acme_user_v2(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: -
--

GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--


