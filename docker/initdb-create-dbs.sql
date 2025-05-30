-- Ensure we are connected to the default 'postgres' database initially
-- This is often the default, but explicit is good.
\connect postgres

-- Create the CDN database
CREATE DATABASE "local-development-cdn" OWNER postgres;
GRANT ALL PRIVILEGES ON DATABASE "local-development-cdn" TO postgres;

-- Create the Domain database
CREATE DATABASE "local-development-domain" OWNER postgres;
GRANT ALL PRIVILEGES ON DATABASE "local-development-domain" TO postgres;

-- Connect to the CDN database and load its schema
\connect local-development-cdn
\i /tmp/cdn-broker-schema.sql

-- Connect to the Domain database and load its schema
\connect local-development-domain
\i /tmp/domain-broker-schema.sql