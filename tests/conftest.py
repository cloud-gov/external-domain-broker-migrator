import re

import pytest
import requests_mock

from tests.lib.database import clean_db
from tests.lib.dns import dns
from tests.lib.fake_cf import fake_cf_client
from tests.lib.fake_cloudfront import cloudfront
from tests.lib.fake_iam import iam_commercial
from tests.lib.fake_route53 import route53
from migrator.models import CdnRoute
from migrator.migration import Migration


def pytest_configure(config):
    config.addinivalue_line("markers", "focus: Only run this test.")


def pytest_collection_modifyitems(items, config):
    """
    Focus on tests marked focus, if any.  Run all
    otherwise.
    """

    selected_items = []
    deselected_items = []

    focused = False

    for item in items:
        if item.get_closest_marker("focus"):
            focused = True
            selected_items.append(item)
        else:
            deselected_items.append(item)

    if focused:
        print("\nOnly running @pytest.mark.focus tests")
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


@pytest.fixture
def fake_requests():
    with requests_mock.Mocker(real_http=False) as m:
        # let dns stuff come through
        fake_dns_matcher = re.compile("http://localhost:8055/.*")
        m.register_uri(requests_mock.ANY, fake_dns_matcher, real_http=True)
        yield m


@pytest.fixture
def migration(clean_db, fake_cf_client, fake_requests):
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "asdf-asdf"
    response_body = """
{
  "metadata": {
    "guid": "asdf-asdf",
    "url": "/v2/service_instances/asdf-asdf",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "my-old-cdn",
    "credentials": { },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "succeeded",
      "description": "",
      "updated_at": "2016-06-08T16:41:26Z",
      "created_at": "2016-06-08T16:41:29Z"
    },
    "space_url": "/v2/spaces/my-space-guid",
    "service_plan_url": "/v2/service_plans/739e78F5-a919-46ef-9193-1293cc086c17",
    "service_bindings_url": "/v2/service_instances/my-migrator-instance/service_bindings",
    "service_keys_url": "/v2/service_instances/my-migrator-instance/service_keys",
    "routes_url": "/v2/service_instances/my-migrator-instance/routes",
    "shared_from_url": "/v2/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/shared_from",
    "shared_to_url": "/v2/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/shared_to"
  }
}
    """
    fake_requests.get(
        "http://localhost/v2/service_instances/asdf-asdf", text=response_body
    )
    migration = Migration(route, clean_db, fake_cf_client)
    return migration
