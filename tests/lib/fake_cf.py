import json

import pytest
from migrator import cf
from migrator.extensions import config


def get_test_client(fake_requests):
    fake_requests.get(
        "http://localhost/info",
        text=json.dumps(
            dict(
                authorization_endpoint="http://login.localhost",
                token_endpoint="http://token.localhost",
            )
        ),
    )
    fake_requests.get(
        "http://localhost/",
        text=json.dumps(
            dict(
                links={
                    "self": dict(href="localhost"),
                    "cloud_controller_v2": dict(
                        href="localhost/v2", meta=dict(version="2.141.0")
                    ),
                    "cloud_controller_v3": dict(
                        href="localhost/v3", meta=dict(version="3.76.0")
                    ),
                    "logging": None,
                    "log_stream": None,
                    "app_ssh": dict(href="ssh.localhost:80"),
                    "uaa": dict(href="http://uaa.localhost"),
                    "network_policy_v0": dict(
                        href="http://api.localhost/networking/v0/external"
                    ),
                    "network_policy_v1": dict(
                        href="http://api.localhost/networking/v1/external"
                    ),
                }
            )
        ),
    )
    fake_requests.post(
        "http://uaa.localhost/oauth/token",
        text=json.dumps(
            dict(access_token="access-token", refresh_token="refresh-token")
        ),
    )
    client = cf.get_cf_client(config)
    return client


@pytest.fixture
def fake_cf_client(fake_requests):
    client = get_test_client(fake_requests)
    fake_requests.reset_mock()  # this makes it way easier for tests to make assertions
    return client
