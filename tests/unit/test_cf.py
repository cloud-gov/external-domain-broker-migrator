import json

import pytest
from migrator import cf
from migrator.extensions import config
from migrator.models import CdnRoute
from migrator.migration import Migration
import requests_mock

from tests.lib.fake_cf import get_test_client


@pytest.fixture
def migration(clean_db, fake_cf_client):
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db, fake_cf_client)
    return migration


def test_get_client(fake_requests):
    # this test mostly just validates the test framework
    client = get_test_client(fake_requests)


def test_enable_service_plan_2(fake_requests, fake_cf_client):
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
    res = cf.enable_plan_for_org("foo", "bar", fake_cf_client)


def test_disable_service_plan_2(fake_requests, fake_cf_client):
    response_body = ""
    fake_requests.delete(
        "http://localhost/v2/service_plan_visibilities/new-plan-visibiliy-guid",
        text=response_body,
    )
    res = cf.disable_plan_for_org("new-plan-visibiliy-guid", fake_cf_client)


def test_get_space_for_instance(migration, fake_requests, fake_cf_client):
    response_body = """
    {
  "metadata": {
    "guid": "some-instance-id",
    "url": "/v2/service_instances/some-instance-id",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "name-1508",
    "service_guid": "a14baddf-1ccc-5299-0152-ab9s49de4422",
    "service_plan_guid": "779d2df0-9cdd-48e8-9781-ea05301cedb1",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "succeeded",
      "description": "service broker-provided description",
      "updated_at": "2016-06-08T16:41:29Z",
      "created_at": "2016-06-08T16:41:29Z"
    },
    "tags": [ ],
    "maintenance_info": {
      "version": "2.1.1",
      "description": "OS image update.Expect downtime."
    },
    "space_url": "/v2/spaces/my-space-guid",
    "service_url": "/v2/services/a14baddf-1ccc-5299-0152-ab9s49de4422",
    "service_plan_url": "/v2/service_plans/779d2df0-9cdd-48e8-9781-ea05301cedb1",
    "service_bindings_url": "/v2/service_instances/some-instance-id/service_bindings",
    "service_keys_url": "/v2/service_instances/some-instance-id/service_keys",
    "routes_url": "/v2/service_instances/some-instance-id/routes",
    "shared_from_url": "/v2/service_instances/some-instance-id/shared_from",
    "shared_to_url": "/v2/service_instances/some-instance-id/shared_to",
    "service_instance_parameters_url": "/v2/service_instances/some-instance-id/parameters"
  }
}
"""
    fake_requests.get(
        "http://localhost/v2/service_instances/some-service-instance-id",
        text=response_body,
    )
    assert (
        cf.get_space_id_for_service_instance_id(migration.instance_id, fake_cf_client)
        == "my-space-guid"
    )


def test_get_org_id_for_space_id(fake_cf_client, fake_requests):
    response_body = """
    {
  "guid": "my-space-guid",
  "created_at": "2017-02-01T01:33:58Z",
  "updated_at": "2017-02-01T01:33:58Z",
  "name": "my-space",
  "relationships": {
    "organization": {
      "data": {
        "guid": "my-org-guid"
      }
    },
    "quota": {
      "data": null
    }
  },
  "links": {
    "self": {
      "href": "http://localhost/v3/spaces/my-space-guid"
    },
    "features": {
      "href": "http://localhost/v3/spaces/my-space-guid/features"
    },
    "organization": {
      "href": "http://localhost/v3/organizations/my-org-guid"
    },
    "apply_manifest": {
      "href": "http://localhost/v3/spaces/my-space-guid/actions/apply_manifest",
      "method": "POST"
    }
  },
  "metadata": {
    "labels": {},
    "annotations": {}
  }
}
"""
    fake_requests.get("http://localhost/v3/spaces/my-space-guid", text=response_body)
    assert cf.get_org_id_for_space_id("my-space-guid", fake_cf_client) == "my-org-guid"


def test_get_all_space_ids_for_org_3(fake_cf_client, fake_requests):
    response_body = """
{
   "pagination": {
      "total_results": 2,
      "total_pages": 1,
      "first": {
         "href": "https://api.fr.cloud.gov/v3/spaces?organization_guids=my-org-guid&page=1&per_page=50"
      },
      "last": {
         "href": "https://api.fr.cloud.gov/v3/spaces?organization_guids=my-org-guid&page=1&per_page=50"
      },
      "next": null,
      "previous": null
   },
   "resources": [
     {
         "guid": "my-space-1-guid",
         "created_at": "2021-01-27T20:52:07Z",
         "updated_at": "2021-01-27T20:52:07Z",
         "name": "space-1",
         "relationships": {
            "organization": {
               "data": {
                  "guid": "my-org-guid"
               }
            },
            "quota": {
               "data": null
            }
         },
         "metadata": {
            "labels": {},
            "annotations": {}
         },
         "links": {
            "self": {
               "href": "https://api.fr.cloud.gov/v3/spaces/my-space-1-guid"
            },
            "organization": {
               "href": "https://api.fr.cloud.gov/v3/organizations/my-org-guid"
            },
            "features": {
               "href": "https://api.fr.cloud.gov/v3/spaces/my-space-1-guid/features"
            },
            "apply_manifest": {
               "href": "https://api.fr.cloud.gov/v3/spaces/my-space-1-guid/actions/apply_manifest",
               "method": "POST"
            }
         }
      },
      {
         "guid": "my-space-2-guid",
         "created_at": "2021-02-04T16:26:06Z",
         "updated_at": "2021-02-04T16:26:06Z",
         "name": "space-2",
         "relationships": {
            "organization": {
               "data": {
                  "guid": "my-org-guid"
               }
            },
            "quota": {
               "data": null
            }
         },
         "metadata": {
            "labels": {},
            "annotations": {}
         },
         "links": {
            "self": {
               "href": "https://api.fr.cloud.gov/v3/spaces/my-space-2-guid"
            },
            "organization": {
               "href": "https://api.fr.cloud.gov/v3/organizations/my-org-guid"
            },
            "features": {
               "href": "https://api.fr.cloud.gov/v3/spaces/my-space-2-guid/features"
            },
            "apply_manifest": {
               "href": "https://api.fr.cloud.gov/v3/spaces/my-space-2-guid/actions/apply_manifest",
               "method": "POST"
            }
         }
      }
   ]
}
    """

    fake_requests.get(
        "http://localhost/v3/spaces?organization_guids=my-org-guid", text=response_body
    )
    assert cf.get_all_space_ids_for_org("my-org-guid", fake_cf_client) == [
        "my-space-1-guid",
        "my-space-2-guid",
    ]
