--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.22
-- Dumped by pg_dump version 13.3 (Ubuntu 13.3-1.pgdg18.04+1)

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

SET default_tablespace = '';

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
-- Name: alb_proxies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alb_proxies (
    alb_arn text NOT NULL,
    alb_dns_name text,
    listener_arn text
);


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
    route_guid text,
    domain text,
    cert_url text,
    certificate bytea,
    arn text,
    name text,
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
    route_guid text NOT NULL,
    state text DEFAULT 'in progress'::text NOT NULL,
    action text DEFAULT 'renew'::text NOT NULL,
    certificate_id integer
);


--
-- Name: operations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.operations_id_seq
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
    guid text NOT NULL,
    state text NOT NULL,
    domains text[],
    challenge_json bytea,
    user_data_id integer,
    alb_proxy_arn text,
    acme_user_id integer
);


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
-- Name: user_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_data ALTER COLUMN id SET DEFAULT nextval('public.user_data_id_seq'::regclass);


--
-- Name: alb_proxies alb_proxies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alb_proxies
    ADD CONSTRAINT alb_proxies_pkey PRIMARY KEY (alb_arn);


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
    ADD CONSTRAINT routes_pkey PRIMARY KEY (guid);


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
-- Name: idx_routes_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routes_state ON public.routes USING btree (state);


--
-- Name: idx_user_data_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_data_deleted_at ON public.user_data USING btree (deleted_at);


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
-- Name: operations fk_operations_route_guid_routes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operations
    ADD CONSTRAINT fk_operations_route_guid_routes FOREIGN KEY (route_guid) REFERENCES public.routes(guid);


--
-- Name: routes fk_routes_acme_user_id_acme_user_v2; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT fk_routes_acme_user_id_acme_user_v2 FOREIGN KEY (acme_user_id) REFERENCES public.acme_user_v2(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: -
--

REVOKE ALL ON SCHEMA public FROM rdsadmin;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO domains_broker;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--
