import json

import pytest
from migrator.config import config_from_env


@pytest.fixture()
def vcap_application():
    data = {
        "application_id": "my-app-id",
        "application_name": "my-app-name",
        "application_uris": [],
        "application_version": "my-app-version",
        "cf_api": "cf-api",
        "name": "my-app-name",
        "organization_name": "my-org-name",
        "space_name": "my-space-name",
        "process_type": "web",
        "uris": [],
        "version": "my-app-version",
    }

    return json.dumps(data)


@pytest.fixture()
def vcap_services():
    data = {
        "aws-rds": [
            {
                "credentials": {
                    "db_name": "cdn-db-name",
                    "host": "cdn-db-host",
                    "password": "cdn-db-password",
                    "port": "cdn-db-port",
                    "uri": "postgres://cdn-db-uri",
                    "username": "cdn-db-username",
                },
                "instance_name": "rds-cdn-broker",
                "label": "aws-rds",
                "name": "rds-cdn-broker",
                "plan": "medium-psql",
                "tags": ["database", "RDS"],
            }
        ],
        "user-provided": [
            {
                "credentials": {
                    "db_name": "alb-db-name",
                    "host": "alb-db-host",
                    "password": "alb-db-password",
                    "port": "alb-db-port",
                    "uri": "postgresql://alb-db-uri",
                    "username": "alb-db-username",
                },
                "instance_name": "rds-domain-broker",
                "label": "aws-rds",
                "name": "rds-domain-broker",
                "tags": ["database", "RDS"],
            }
        ],
    }

    return json.dumps(data)


@pytest.fixture()
def mocked_env(vcap_application, vcap_services, monkeypatch):
    monkeypatch.setenv("VCAP_APPLICATION", vcap_application)
    monkeypatch.setenv("VCAP_SERVICES", vcap_services)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("DNS_ROOT_DOMAIN", "cloud.test")
    monkeypatch.setenv("AWS_COMMERCIAL_REGION", "us-west-1")
    monkeypatch.setenv("AWS_COMMERCIAL_ACCESS_KEY_ID", "ASIANOTAREALKEY")
    monkeypatch.setenv("AWS_COMMERCIAL_SECRET_ACCESS_KEY", "NOT_A_REAL_SECRET_KEY")
    monkeypatch.setenv("ROUTE53_HOSTED_ZONE_ID", "FAKEZONEID")
    monkeypatch.setenv("ALB_HOSTED_ZONE_ID", "FAKEZONEIDFORALBS")
    monkeypatch.setenv("CF_USERNAME", "fake_cf_username")
    monkeypatch.setenv("CF_PASSWORD", "fake_cf_password")
    monkeypatch.setenv("CF_API_ENDPOINT", "https://localhost")
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_USER", "my-user@example.com")
    monkeypatch.setenv("SMTP_PASS", "this-password-is-invalid")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.com")
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    monkeypatch.setenv("SMTP_CERT", "A_REAL_CERT_WOULD_BE_LONGER_THAN_THIS")
    monkeypatch.setenv("MIGRATION_PLAN_ID", "A_MIGRATION_PLAN_ID")
    monkeypatch.setenv("CDN_PLAN_ID", "A_CDN_PLAN_ID")
    monkeypatch.setenv("DOMAIN_PLAN_ID", "A_DOMAIN_PLAN_ID")
    monkeypatch.setenv("DOMAIN_DATABASE_ENCRYPTION_KEY", "DOMAIN_KEY")
    monkeypatch.setenv("CDN_DATABASE_ENCRYPTION_KEY", "CDN_KEY")


@pytest.mark.parametrize("env", ["local", "development", "staging", "production"])
def test_config_doesnt_explode(env, monkeypatch, mocked_env):
    monkeypatch.setenv("ENV", env)
    config = config_from_env()
    assert config.ENV == env


@pytest.mark.parametrize("env", ["development", "staging", "production"])
def test_config_gets_credentials(env, monkeypatch, mocked_env):
    monkeypatch.setenv("ENV", env)
    config = config_from_env()
    assert config.CDN_BROKER_DATABASE_URI == "postgresql://cdn-db-uri"
    assert config.DOMAIN_BROKER_DATABASE_URI == "postgresql://alb-db-uri"
    assert config.AWS_COMMERCIAL_REGION == "us-west-1"
    assert config.AWS_COMMERCIAL_ACCESS_KEY_ID == "ASIANOTAREALKEY"
    assert config.AWS_COMMERCIAL_SECRET_ACCESS_KEY == "NOT_A_REAL_SECRET_KEY"
    assert config.ROUTE53_ZONE_ID == "FAKEZONEID"
    assert config.CF_USERNAME == "fake_cf_username"
    assert config.CF_PASSWORD == "fake_cf_password"
    assert config.CF_API_ENDPOINT == "https://localhost"
    assert config.ALB_HOSTED_ZONE_ID == "FAKEZONEIDFORALBS"
    assert config.CLOUDFRONT_HOSTED_ZONE_ID == "Z2FDTNDATAQYW2"
    assert config.MIGRATION_PLAN_ID == "A_MIGRATION_PLAN_ID"
    assert config.CDN_PLAN_ID == "A_CDN_PLAN_ID"
    assert config.DOMAIN_PLAN_ID == "A_DOMAIN_PLAN_ID"
    assert config.DOMAIN_DATABASE_ENCRYPTION_KEY == "DOMAIN_KEY"
    assert config.CDN_DATABASE_ENCRYPTION_KEY == "CDN_KEY"


@pytest.mark.parametrize("env", ["production", "staging", "development"])
def test_config_sets_smtp_variables(env, monkeypatch, mocked_env):
    monkeypatch.setenv("ENV", env)

    config = config_from_env()

    assert config.SMTP_FROM == "no-reply@example.com"
    assert config.SMTP_USER == "my-user@example.com"
    assert config.SMTP_PASS == "this-password-is-invalid"
    assert config.SMTP_HOST == "127.0.0.1"
    assert config.SMTP_PORT == 1025
    assert config.SMTP_CERT == "A_REAL_CERT_WOULD_BE_LONGER_THAN_THIS"
    assert config.SMTP_TO == "alerts@example.com"
