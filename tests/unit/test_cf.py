import json

import pytest
from migrator import cf
from migrator.extensions import config
from migrator.models import CdnRoute
from migrator.migration import Migration
import requests_mock

from tests.lib.fake_cf import get_test_client


def test_get_client(fake_requests):
    # this test mostly just validates the test framework
    client = get_test_client(fake_requests)


def test_enable_service_plan(fake_requests, fake_cf_client):
    response_body = """{
  "type": "organization",
  "organizations": [
    {
      "guid": "bar",
      "name": "other_org"
    }
  ]
}}"""
    fake_requests.post(
        "http://localhost/v3/service_plans/foo/visibility", text=response_body
    )
    res = cf.enable_plan_for_org("foo", "bar", fake_cf_client)

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v3/service_plans/foo/visibility"


def test_enable_service_plan_2(fake_requests, fake_cf_client):
    response_body = """{
        "description": "This combination of ServicePlan and Organization is already taken: organization_id and service_plan_id unique",
        "error_code": "CF-ServicePlanVisibilityAlreadyExists",
        "code": 260002
    }
    """
    fake_requests.post(
        "http://localhost/v3/service_plans/foo/visibility",
        text=response_body,
        status_code=400,
    )

    # the real test here is that we don't raise an error
    res = cf.enable_plan_for_org("foo", "bar", fake_cf_client)

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v3/service_plans/foo/visibility"


def test_disable_service_plan_2(fake_requests, fake_cf_client):
    response_body = ""
    fake_requests.delete(
        "http://localhost/v3/service_plans/FAKE-MIGRATION-PLAN-GUID/visibility/test-org-id",
        text=response_body,
    )
    res = cf.disable_plan_for_org(
        "FAKE-MIGRATION-PLAN-GUID", "test-org-id", fake_cf_client
    )

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url
        == "http://localhost/v3/service_plans/FAKE-MIGRATION-PLAN-GUID/visibility/test-org-id"
    )


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
        "http://localhost/v2/service_instances/asdf-asdf", text=response_body
    )
    assert (
        cf.get_space_id_for_service_instance_id(migration.instance_id, fake_cf_client)
        == "my-space-guid"
    )

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v2/service_instances/asdf-asdf"


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

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v3/spaces/my-space-guid"


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

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v3/spaces?organization_guids=my-org-guid"
    )


def test_create_bare_migrator_service_instance_in_space(fake_cf_client, fake_requests):
    # creating a service instance looks like:
    # 1. POST /v3/service_instance, which returns a 204 with reference to a `job`
    # 2. GET the job reference, which returns a status and a reference to the service instance
    # 3. poll the job reference until it completes

    def create_param_matcher(request):
        domains_in = request.json().get("parameters", {}).get("domains", [])
        # use an assert for pytest
        assert sorted(domains_in) == sorted(["www0.example.gov", "www1.example.gov"])
        # return True for requests_mock
        return True

    fake_requests.post(
        "http://localhost/v3/service_instances",
        text="",
        headers={"Location": "http://localhost/v3/jobs/create-instance-job-guid"},
        additional_matcher=create_param_matcher,
    )

    job_guid = cf.create_bare_migrator_service_instance_in_space(
        "my-space-guid",
        "739e78F5-a919-46ef-9193-1293cc086c17",
        "external-domain-broker-migrator",
        ["www0.example.gov", "www1.example.gov"],
        fake_cf_client,
    )

    assert job_guid == "create-instance-job-guid"
    assert fake_requests.called
    assert (
        fake_requests.request_history[-1].url == "http://localhost/v3/service_instances"
    )


def test_wait_for_instance_ready(fake_cf_client, fake_requests):
    job_response_body_processing = """
    {
      "created_at": "2025-04-21T23:35:27Z",
      "errors": [],
      "guid": "create-instance-job-guid",
      "links": {
        "self": {
          "href": "https://api.fr.cloud.gov/v3/jobs/create-instance-job-guid"
        },
        "service_instances": {
          "href": "https://api.fr.cloud.gov/v3/service_instances/my-service-instance-id"
        }
      },
      "operation": "service_instance.create",
      "state": "PROCESSING",
      "updated_at": "2025-04-21T23:35:27Z",
      "warnings": []
    }
    """
    job_response_body_polling = """
    {
      "created_at": "2025-04-21T23:35:27Z",
      "errors": [],
      "guid": "create-instance-job-guid",
      "links": {
        "self": {
          "href": "https://api.fr.cloud.gov/v3/jobs/create-instance-job-id"
        },
        "service_instances": {
          "href": "https://api.fr.cloud.gov/v3/service_instances/my-service-instance-id"
        }
      },
      "operation": "service_instance.create",
      "state": "POLLING",
      "updated_at": "2025-04-21T23:35:29Z",
      "warnings": []
    }
    """
    job_response_body_complete = """
    {
      "created_at": "2025-04-21T23:35:27Z",
      "errors": [],
      "guid": "create-instance-job-guid",
      "links": {
        "self": {
          "href": "https://api.fr.cloud.gov/v3/jobs/create-instance-job-id"
        },
        "service_instances": {
          "href": "https://api.fr.cloud.gov/v3/service_instances/my-service-instance-id"
        }
      },
      "operation": "service_instance.create",
      "state": "COMPLETE",
      "updated_at": "2025-04-21T23:41:31Z",
      "warnings": []
    }
    """

    fake_requests.get(
        "http://localhost/v3/jobs/create-instance-job-id",
        text=job_response_body_processing,
    )
    fake_requests.get(
        "http://localhost/v3/jobs/create-instance-job-id",
        text=job_response_body_polling,
    )
    fake_requests.get(
        "http://localhost/v3/jobs/create-instance-job-id",
        text=job_response_body_polling,
    )
    fake_requests.get(
        "http://localhost/v3/jobs/create-instance-job-id",
        text=job_response_body_complete,
    )

    assert (
        cf.wait_for_service_instance_ready("create-instance-job-id", fake_cf_client)
        == "my-service-instance-id"
    )


def update_existing_cdn_domain_service_instance(fake_cf_client, fake_requests):
    response_body = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:30Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {
      "creds-key-41": "creds-val-41"
    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "update",
      "state": "in progress",
      "description": "",
      "updated_at": "2016-06-08T16:41:30Z",
      "created_at": "2016-06-08T16:41:30Z"
    },
    "tags": [

    ],
    "maintenance_info": {
      "version": "2.1.0",
      "description": "OS image update.\nExpect downtime."
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

    fake_requests.put(
        "http://localhost/v2/service_instances/my-migrator-instance", text=response_body
    )

    response = cf.update_existing_cdn_domain_service_instance(
        "my-space-guid",
        "739e78F5-a919-46ef-9193-1293cc086c17",
        "external-domain-broker-migrator",
        fake_cf_client,
    )

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )

    assert response["guid"] == "my-migrator-instance"
    assert response["state"] == "in progress"
    assert response["type"] == "update"


def test_purge_service_instance(fake_cf_client, fake_requests):
    response_body = """{
  "metadata": {
    "guid": "my-service-instance",
    "url": "/v2/service_instances/my-service-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "name-1502",
    "credentials": { },
    "service_plan_guid": "8ea19d29-2e20-469e-8b91-917a6410e2f2",
    "space_guid": "dd68a2ba-04a3-4125-99ea-643b96e07ef6",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "delete",
      "state": "complete",
      "description": "",
      "updated_at": "2016-06-08T16:41:29Z",
      "created_at": "2016-06-08T16:41:29Z"
    },
    "tags": [ ],
    "maintenance_info": {},
    "space_url": "/v2/spaces/dd68a2ba-04a3-4125-99ea-643b96e07ef6",
    "service_plan_url": "/v2/service_plans/8ea19d29-2e20-469e-8b91-917a6410e2f2",
    "service_bindings_url": "/v2/service_instances/1aaeb02d-16c3-4405-bc41-80e83d196dff/service_bindings",
    "service_keys_url": "/v2/service_instances/1aaeb02d-16c3-4405-bc41-80e83d196dff/service_keys",
    "routes_url": "/v2/service_instances/1aaeb02d-16c3-4405-bc41-80e83d196dff/routes",
    "shared_from_url": "/v2/service_instances/6da8d173-b409-4094-949f-3c1cc8a68503/shared_from",
    "shared_to_url": "/v2/service_instances/6da8d173-b409-4094-949f-3c1cc8a68503/shared_to"
  }

    } """

    fake_requests.delete(
        "http://localhost/v2/service_instances/my-service-instance?purge=true",
        text=response_body,
    )

    cf.purge_service_instance("my-service-instance", fake_cf_client)
    assert fake_requests.called
