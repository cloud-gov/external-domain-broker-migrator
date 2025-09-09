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


def test_get_space_for_instance(fake_requests, fake_cf_client):
    response_body = """
   {
  "guid": "asdf-asdf",
  "created_at": "2020-03-10T15:49:29Z",
  "updated_at": "2020-03-10T15:49:29Z",
  "name": "my-managed-instance",
  "tags": [],
  "type": "managed",
  "maintenance_info": {
    "version": "1.0.0"
  },
  "upgrade_available": false,
  "dashboard_url": "https://service-broker.example.org/dashboard",
  "last_operation": {
    "type": "create",
    "state": "succeeded",
    "description": "Operation succeeded",
    "updated_at": "2020-03-10T15:49:32Z",
    "created_at": "2020-03-10T15:49:29Z"
  },
  "relationships": {
    "service_plan": {
      "data": {
        "guid": "5358d122-638e-11ea-afca-bf6e756684ac"
      }
    },
    "space": {
      "data": {
        "guid": "my-space-guid"
      }
    }
  },
  "metadata": {
    "labels": {},
    "annotations": {}
  },
  "links": {
    "self": {
      "href": "https://api.example.org/v3/service_instances/asdf-asdf"
    },
    "service_plan": {
      "href": "https://api.example.org/v3/service_plans/5358d122-638e-11ea-afca-bf6e756684ac"
    },
    "space": {
      "href": "https://api.example.org/v3/spaces/my-space-guid"
    },
    "parameters": {
      "href": "https://api.example.org/v3/service_instances/asdf-asdf/parameters"
    },
    "shared_spaces": {
      "href": "https://api.example.org/v3/service_instances/asdf-asdf/relationships/shared_spaces"
    },
    "service_credential_bindings": {
      "href": "https://api.example.org/v3/service_credential_bindings?service_instance_guids=asdf-asdf"
    },
    "service_route_bindings": {
      "href": "https://api.example.org/v3/service_route_bindings?service_instance_guids=asdf-asdf"
    }
  }
}
"""
    fake_requests.get(
        "http://localhost/v3/service_instances/asdf-asdf", text=response_body
    )
    assert (
        cf.get_space_id_for_service_instance_id("asdf-asdf", fake_cf_client)
        == "my-space-guid"
    )

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v3/service_instances/asdf-asdf"


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
        cf.wait_for_service_instance_create("create-instance-job-id", fake_cf_client)
        == "my-service-instance-id"
    )


def test_wait_for_job_complete(fake_cf_client, fake_requests):
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

    response = cf.wait_for_job_complete("create-instance-job-id", fake_cf_client)
    assert response["state"] == "COMPLETE"
    assert (
        response["links"]["service_instances"]["href"]
        == "https://api.fr.cloud.gov/v3/service_instances/my-service-instance-id"
    )


def test_wait_for_job_complete_but_it_fails(fake_cf_client, fake_requests):
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
    job_response_body_failed = """
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
      "state": "FAILED",
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
        text=job_response_body_failed,
    )

    with pytest.raises(Exception, match="Job failed"):
        cf.wait_for_job_complete("create-instance-job-id", fake_cf_client)


def test_update_existing_cdn_domain_service_instance(fake_cf_client, fake_requests):
    def update_param_matcher(request):
        json_ = request.json()
        params = json_.get("parameters", {})
        # use an assert for pytest
        assert "param1" in params
        # return True for requests_mock
        return True

    fake_requests.patch(
        "http://localhost/v3/service_instances/my-migrator-instance",
        text="",
        headers={"Location": "http://localhost/v3/jobs/job-id"},
        additional_matcher=update_param_matcher,
    )

    response = cf.update_existing_cdn_domain_service_instance(
        "my-migrator-instance",
        {"param1": "value1"},
        fake_cf_client,
    )

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v3/service_instances/my-migrator-instance"
    )
    assert response == "job-id"


def test_purge_service_instance(fake_cf_client, fake_requests: requests_mock.Mocker):
    response_body = """{
  "guid": "my-service-instance",
  "created_at": "2016-06-08T16:41:29Z",
  "updated_at": "2016-06-08T16:41:26Z",
  "name": "name-1502",
  "tags": [ ],
  "type": "managed_service_instance",
  "maintenance_info": {},
  "dashboard_url": null,
  "last_operation": {
    "type": "delete",
    "state": "complete",
    "description": "",
    "updated_at": "2016-06-08T16:41:29Z",
    "created_at": "2016-06-08T16:41:29Z"
  },
  "relationships": {
    "service_plan": {
      "data": {
        "guid": "8ea19d29-2e20-469e-8b91-917a6410e2f2"
      }
    },
    "space": {
      "data": {
        "guid": "dd68a2ba-04a3-4125-99ea-643b96e07ef6"
      }
    }
  },
  "links": {
    "self": {
      "href":  "/v3/service_instances/my-service-instance"
    },
    "service_plan": {
      "href": "/v3/service_plans/8ea19d29-2e20-469e-8b91-917a6410e2f2"
    },
    "space": {
      "href": "/v3/spaces/dd68a2ba-04a3-4125-99ea-643b96e07ef6"
    },
    "shared_spaces": {
      "href": "/v3/service_instances/6da8d173-b409-4094-949f-3c1cc8a68503/relationships/shared_spaces"
    },
    "service_credential_bindings": {
      "href": "/v3/service_credential_bindings?service_instance_guids=1aaeb02d-16c3-4405-bc41-80e83d196dff"
    },
    "service_route_bindings": {
      "href": "/v3/service_route_bindings?service_isntance_guids=1aaeb02d-16c3-4405-bc41-80e83d196dff"
    }
  }
 } """

    fake_requests.delete(
        "http://localhost/v3/service_instances/my-service-instance",
        text=response_body,
    )

    response_body = """{
        "description": "Resource not found",
        "error_code": "CF-ResourceNotFound",
        "code": 10010
    }
    """

    fake_requests.get(
        "http://localhost/v3/service_instances/my-service-instance",
        text=response_body,
        status_code=404,
    )

    cf.purge_service_instance("my-service-instance", fake_cf_client)
    assert fake_requests.called


def test_purge_service_instance_retries(
    fake_cf_client, fake_requests: requests_mock.Mocker
):
    fake_requests.delete(
        "http://localhost/v3/service_instances/my-service-instance", status_code=200
    )

    not_found_response = """{
        "description": "Resource not found",
        "error_code": "CF-ResourceNotFound",
        "code": 10010
    }
    """

    fake_requests.register_uri(
        "GET",
        "http://localhost/v3/service_instances/my-service-instance",
        [
            {"status_code": 200},
            {"status_code": 404, "text": not_found_response},
        ],
    )

    cf.purge_service_instance("my-service-instance", fake_cf_client)
    assert fake_requests.called
    assert len(fake_requests.request_history) == 3


def test_purge_service_instance_gives_up_after_maximum_retries(
    fake_cf_client, fake_requests: requests_mock.Mocker
):
    fake_requests.delete(
        "http://localhost/v3/service_instances/my-service-instance", status_code=200
    )

    fake_requests.register_uri(
        "GET",
        "http://localhost/v3/service_instances/my-service-instance",
        [
            {"status_code": 200},
            {"status_code": 200},
        ],
    )

    with pytest.raises(RuntimeError):
        cf.purge_service_instance("my-service-instance", fake_cf_client)

    assert fake_requests.called
    assert len(fake_requests.request_history) == 3
