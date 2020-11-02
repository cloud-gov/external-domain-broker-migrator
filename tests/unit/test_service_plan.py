import json

import pytest
from migrator.extensions import get_cf_client
from migrator import service_plan
import requests_mock


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
                    "uaa": dict(href="https://uaa.localhost"),
                    "network_policy_v0": dict(
                        href="https://api.localhost/networking/v0/external"
                    ),
                    "network_policy_v1": dict(
                        href="https://api.localhost/networking/v1/external"
                    ),
                }
            )
        ),
    )
    fake_requests.post(
        "http://login.localhost/oauth/token",
        text=json.dumps(
            dict(access_token="access-token", refresh_token="refresh-token")
        ),
    )
    client = get_cf_client()
    return client


def test_get_client(fake_requests):
    # this test mostly just validates the test framework
    client = get_test_client(fake_requests)


def test_enable_service_plan_2(fake_requests):
    client = get_test_client(fake_requests)
    response_body = """{
  "metadata": {
    "guid": "new-plan-visibiliy-guid",
    "url": "/v2/service_plan_visibilities/new-plan-visibiliy-guid",
    "created_at": "2016-06-08T16:41:31Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "service_plan_guid": "foo",
    "organization_guid": "bar",
    "service_plan_url": "/v2/service_plans/foo",
    "organization_url": "/v2/organizations/bar"
  }
}"""
    fake_requests.post(
        "http://localhost/v2/service_plan_visibilities", text=response_body
    )
    res = service_plan.enable_plan_for_org("foo", "bar", client)
