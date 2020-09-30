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
                    "uri": "cdn-db-uri",
                    "username": "cdn-db-username",
                },
                "instance_name": "rds-cdn-broker",
                "label": "aws-rds",
                "name": "rds-cdn-broker",
                "plan": "medium-psql",
                "tags": ["database", "RDS"],
            },
            {
                "credentials": {
                    "db_name": "external-domain-db-name",
                    "host": "external-domain-db-host",
                    "password": "external-domain-db-password",
                    "port": "external-domain-db-port",
                    "uri": "external-domain-db-uri",
                    "username": "external-domain-db-username",
                },
                "instance_name": "external-domain-broker-psql",
                "label": "aws-rds",
                "name": "external-domain-broker-psql",
                "plan": "medium-psql",
                "tags": ["database", "RDS"],
            },
        ]
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
    monkeypatch.setenv("DATABASE_ENCRYPTION_KEY", "NOT_A_REAL_SECRET_KEY")
    monkeypatch.setenv("ROUTE53_HOSTED_ZONE_ID", "FAKEZONEID")


@pytest.mark.parametrize("env", ["local", "development", "staging", "production"])
def test_config_doesnt_explode(env, monkeypatch, mocked_env):
    monkeypatch.setenv("ENV", env)
    config = config_from_env()
    assert config.ENV == env


@pytest.mark.parametrize("env", ["development", "staging", "production"])
def test_config_gets_credentials(env, monkeypatch, mocked_env):
    monkeypatch.setenv("ENV", env)
    config = config_from_env()
    assert config.CDN_BROKER_DATABASE_URI == "cdn-db-uri"
    assert config.EXTERNAL_DOMAIN_BROKER_DATABASE_URI == "external-domain-db-uri"
    assert config.AWS_COMMERCIAL_REGION == "us-west-1"
    assert config.AWS_COMMERCIAL_ACCESS_KEY_ID == "ASIANOTAREALKEY"
    assert config.AWS_COMMERCIAL_SECRET_ACCESS_KEY == "NOT_A_REAL_SECRET_KEY"
    assert config.ROUTE53_ZONE_ID == "FAKEZONEID"
