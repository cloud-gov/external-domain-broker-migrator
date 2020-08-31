--
-- PostgreSQL database dump
--

-- Dumped from database version 11.5
-- Dumped by pg_dump version 11.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: acme_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acme_user (
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    id integer NOT NULL,
    email character varying NOT NULL,
    uri character varying NOT NULL,
    private_key_pem character varying NOT NULL,
    registration_json text
);


--
-- Name: acme_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acme_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acme_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acme_user_id_seq OWNED BY public.acme_user.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: certificate; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificate (
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    id integer NOT NULL,
    service_instance_id character varying NOT NULL,
    subject_alternative_names jsonb,
    leaf_pem text,
    expires_at timestamp with time zone,
    private_key_pem character varying,
    csr_pem text,
    fullchain_pem text,
    iam_server_certificate_id character varying,
    iam_server_certificate_name character varying,
    iam_server_certificate_arn character varying,
    order_json text
);


--
-- Name: certificate_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.certificate_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: certificate_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.certificate_id_seq OWNED BY public.certificate.id;


--
-- Name: challenge; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.challenge (
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    id integer NOT NULL,
    domain character varying NOT NULL,
    validation_domain character varying NOT NULL,
    validation_contents text NOT NULL,
    body_json text,
    answered boolean,
    certificate_id integer NOT NULL
);


--
-- Name: challenge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.challenge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: challenge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.challenge_id_seq OWNED BY public.challenge.id;


--
-- Name: operation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operation (
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    id integer NOT NULL,
    service_instance_id character varying NOT NULL,
    state character varying DEFAULT 'in progress'::character varying NOT NULL,
    action character varying NOT NULL,
    canceled_at timestamp with time zone,
    step_description character varying
);


--
-- Name: operation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.operation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: operation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.operation_id_seq OWNED BY public.operation.id;


--
-- Name: service_instance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_instance (
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    id character varying(36) NOT NULL,
    acme_user_id integer,
    domain_names jsonb,
    cloudfront_distribution_arn character varying,
    cloudfront_distribution_id character varying,
    cloudfront_origin_hostname character varying,
    cloudfront_origin_path character varying,
    route53_change_ids jsonb,
    deactivated_at timestamp with time zone,
    instance_type text,
    alb_arn character varying,
    domain_internal character varying,
    alb_listener_arn character varying,
    route53_alias_hosted_zone character varying,
    forward_cookie_policy character varying,
    forwarded_cookies jsonb,
    forwarded_headers jsonb,
    origin_protocol_policy character varying,
    current_certificate_id integer,
    new_certificate_id integer,
    previous_alb_arn character varying,
    previous_alb_listener_arn character varying,
    error_responses jsonb
);


--
-- Name: acme_user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acme_user ALTER COLUMN id SET DEFAULT nextval('public.acme_user_id_seq'::regclass);


--
-- Name: certificate id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate ALTER COLUMN id SET DEFAULT nextval('public.certificate_id_seq'::regclass);


--
-- Name: challenge id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenge ALTER COLUMN id SET DEFAULT nextval('public.challenge_id_seq'::regclass);


--
-- Name: operation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operation ALTER COLUMN id SET DEFAULT nextval('public.operation_id_seq'::regclass);


--
-- Name: acme_user acme_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acme_user
    ADD CONSTRAINT acme_user_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: certificate certificate_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate
    ADD CONSTRAINT certificate_pkey PRIMARY KEY (id);


--
-- Name: challenge challenge_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenge
    ADD CONSTRAINT challenge_pkey PRIMARY KEY (id);


--
-- Name: operation operation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operation
    ADD CONSTRAINT operation_pkey PRIMARY KEY (id);


--
-- Name: service_instance service_instance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_instance
    ADD CONSTRAINT service_instance_pkey PRIMARY KEY (id);


--
-- Name: certificate certificate_service_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate
    ADD CONSTRAINT certificate_service_instance_id_fkey FOREIGN KEY (service_instance_id) REFERENCES public.service_instance(id);


--
-- Name: challenge challenge_certificate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenge
    ADD CONSTRAINT challenge_certificate_id_fkey FOREIGN KEY (certificate_id) REFERENCES public.certificate(id);


--
-- Name: service_instance fk__service_instance__certificate__current_certificate_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_instance
    ADD CONSTRAINT fk__service_instance__certificate__current_certificate_id FOREIGN KEY (current_certificate_id) REFERENCES public.certificate(id);


--
-- Name: service_instance fk__service_instance__certificate__new_certificate_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_instance
    ADD CONSTRAINT fk__service_instance__certificate__new_certificate_id FOREIGN KEY (new_certificate_id) REFERENCES public.certificate(id);


--
-- Name: operation operation_service_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operation
    ADD CONSTRAINT operation_service_instance_id_fkey FOREIGN KEY (service_instance_id) REFERENCES public.service_instance(id);


--
-- Name: service_instance service_instance_acme_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_instance
    ADD CONSTRAINT service_instance_acme_user_id_fkey FOREIGN KEY (acme_user_id) REFERENCES public.acme_user(id);


--
-- PostgreSQL database dump complete
--

