import datetime
import re

import pytest
import requests_mock

from tests.lib.database import clean_db
from tests.lib.dns import dns
from tests.lib.fake_cf import fake_cf_client
from tests.lib.fake_cloudfront import cloudfront
from tests.lib.fake_route53 import route53
from migrator.models import CdnRoute, CdnCertificate
from migrator.migration import CdnMigration, Migration


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
def cdn_migration(clean_db, fake_cf_client, fake_requests):
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "asdf-asdf"
    certificate0 = CdnCertificate()
    certificate0.route = route
    certificate0.iam_server_certificate_name = "my-cert-name-0"
    certificate0.iam_server_certificate_arn = "my-cert-arn-0"
    certificate0.iam_server_certificate_id = "my-cert-id-0"
    certificate0.expires = datetime.datetime.now() + datetime.timedelta(days=1)

    certificate1 = CdnCertificate()
    certificate1.route = route
    certificate1.iam_server_certificate_name = "my-cert-name-2"
    certificate1.iam_server_certificate_arn = "my-cert-arn-2"
    certificate1.iam_server_certificate_id = "my-cert-id-2"
    certificate1.expires = datetime.datetime.now() - datetime.timedelta(days=1)
    response_body = """
{
  "guid": "asdf-asdf",
  "created_at": "2016-06-08T16:41:29Z",
  "updated_at": "2016-06-08T16:41:26Z"
  "name": "my-old-cdn",
  "type": "managed",
  "dashboard_url": null,
  "last_operation": {
     "type": "create",
     "state": "succeeded",
     "description": "",
     "updated_at": "2016-06-08T16:41:26Z",
     "created_at": "2016-06-08T16:41:29Z"
  },
  "relationships": {
    "service_plan": {
      "data": {
        "guid": "739e78F5-a919-46ef-9193-1293cc086c17"
      }
    },
    "space": {
      "data" :{
        "guid": "my-space-guid"
      }
    }
  },
  "links": {
      "self": {
        "href": "/v3/service_instances/asdf-asdf"
      },
      "service_plan": {
        "href": "/v3/service_plans/739e78F5-a919-46ef-9193-1293cc086c17"
      },
      "space": {
        "href": "/v3/spaces/my-space-guid"
      },
      "shared_spaces": {
        "href": "/v3/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/relationships/shared_spaces"
      },
      "service_credentials_bindings": {
        "href": "/v3/service_credential_bindings?service_instance_guids=my-migrator-instance/credentials"
      },
      "service_routes_bindings": {
        "href": "/v3/service_route_bindings?service_instance_guids=my-migrator-instance"
      }
    }
  }
}
    """
    fake_requests.get(
        "http://localhost/v3/service_instances/asdf-asdf", text=response_body
    )
    clean_db.add_all([route, certificate0, certificate1])
    clean_db.commit()
    migration = CdnMigration(route, clean_db, fake_cf_client)
    return migration


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
  "guid": "asdf-asdf",
  "created_at": "2016-06-08T16:41:29Z",
  "updated_at": "2016-06-08T16:41:26Z",
  "name": "my-old-cdn",
  "type": "managed_service_instance",
  "dashboard_url": null,
  "last_operation": {
    "type": "create",
    "state": "succeeded",
    "description": "",
    "updated_at": "2016-06-08T16:41:26Z",
    "created_at": "2016-06-08T16:41:29Z"
  },
  "relationship": {
    "service_plan": {
      "data": {
        "guid": "739e78F5-a919-46ef-9193-1293cc086c17"
      }
    }
    "space": {
      "data": {
        "guid": "my-space-guid"  
      }
    }
  }
  "links": {
    "service_plan" {
      "href": "/v3/service_plans/739e78F5-a919-46ef-9193-1293cc086c17",
    },
    "space": {
      "href": "/v3/spaces/my-space-guid"
    },
    "shared_spaces": {
      "href": "/v3/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/shared_from"
    },
    "service_credential_bindings": {
      "href": "/v3/service_instances/credential_service_bindings?service_instance_guidskkk=my-migrator-instance/service_bindings"
    },
    "service_route_bindings": {
      "href": "/v3/service_route_bindings?service_instance_guids=my-migrator-instance/routes"
    },
  }
  
}
    """
    fake_requests.get(
        "http://localhost/v3/service_instances/asdf-asdf", text=response_body
    )
    migration = CdnMigration(route, clean_db, fake_cf_client)
    return migration
