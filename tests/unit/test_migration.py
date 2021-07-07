import datetime

import pytest

from migrator.migration import find_active_instances, Migration
from migrator.models import CdnRoute


def test_find_instances(clean_db):
    states = [
        "provisioned",
        "deprovisioned",
        "deprovisioning",
        "this-state-should-never-exist",
    ]
    for state in states:
        route = CdnRoute()
        route.state = state
        route.instance_id = f"id-{state}"
        clean_db.add(route)
    clean_db.commit()
    clean_db.close()
    instances = find_active_instances(clean_db)
    assert len(instances) == 1
    assert instances[0].state == "provisioned"


def test_validate_good_dns(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("_acme-challenge.example.com")
    migration.domains = ["example.com"]
    assert migration.has_valid_dns


def test_validate_bad_dns(clean_db, dns, fake_cf_client, migration):
    migration.domains = ["example.com"]
    assert not migration.has_valid_dns


def test_validate_mixed_good_and_bad_dns(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("_acme-challenge.example.com")
    migration.domains = ["example.com", "foo.example.com"]
    assert not migration.has_valid_dns


def test_validate_multiple_valid_dns(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.example.com")
    migration.domains = ["example.com", "foo.example.com"]
    assert Migration.has_valid_dns


def test_migration_init(clean_db, fake_cf_client, fake_requests):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
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

    assert sorted(migration.domains) == sorted(["example.com", "foo.example.com"])
    assert migration.instance_id == "asdf-asdf"
    assert migration.cloudfront_distribution_id == "some-distribution-id"
    assert migration.instance_name == "my-old-cdn"


def test_migration_loads_cloudfront_config(
    clean_db, cloudfront, fake_cf_client, migration
):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="mycertificateid",
        origin_hostname="cloud.test",
        origin_path="",
        distribution_id="sample-distribution-id",
        status="active",
        custom_error_responses={
            "Quantity": 1,
            "Items": [
                {
                    "ErrorCode": 400,
                    "ResponsePagePath": "/errors/400.html",
                    "ResponseCode": "400",
                }
            ],
        },
    )
    migration.route.dist_id = "sample-distribution-id"
    assert migration.cloudfront_distribution_data is not None
    cloudfront.assert_no_pending_responses()
    assert migration.cloudfront_distribution_config is not None
    assert (
        migration.cloudfront_distribution_arn
        == "arn:aws:cloudfront::000000000000:distribution/sample-distribution-id"
    )
    assert migration.forward_cookie_policy == "all"
    assert migration.forwarded_cookies == []
    assert migration.forwarded_headers == ["HOST"]
    assert migration.custom_error_responses == {"400": "/errors/400.html"}
    assert migration.origin_hostname == "cloud.test"
    assert migration.origin_path == ""
    assert migration.origin_protocol_policy == "https-only"
    assert migration.iam_certificate_id == "mycertificateid"


def test_migration_loads_cloudfront_config_with_no_error_reponses(
    clean_db, cloudfront, fake_cf_client, migration
):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="",
        distribution_id="sample-distribution-id",
        status="active",
        custom_error_responses={"Quantity": 0},
    )
    migration.route.dist_id = "sample-distribution-id"
    assert migration.cloudfront_distribution_data is not None
    cloudfront.assert_no_pending_responses()
    assert migration.cloudfront_distribution_config is not None
    assert (
        migration.cloudfront_distribution_arn
        == "arn:aws:cloudfront::000000000000:distribution/sample-distribution-id"
    )
    assert migration.forward_cookie_policy == "all"
    assert migration.forwarded_cookies == []
    assert migration.forwarded_headers == ["HOST"]
    assert migration.custom_error_responses == {}
    assert migration.origin_hostname == "cloud.test"
    assert migration.origin_path == ""
    assert migration.origin_protocol_policy == "https-only"


@pytest.mark.parametrize(
    "input_,expected",
    [
        ({"Quantity": 0}, {}),
        (
            {
                "Quantity": 2,
                "Items": [
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/four-oh-four",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 300,
                    },
                    {
                        "ErrorCode": 500,
                        "ResponsePagePath": "/five-hundred",
                        "ResponseCode": "500",
                        "ErrorCachingMinTTL": 300,
                    },
                ],
            },
            {"404": "/four-oh-four", "500": "/five-hundred"},
        ),
        (
            {
                "Quantity": 1,
                "Items": [
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/four-oh-four",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 300,
                    }
                ],
            },
            {"404": "/four-oh-four"},
        ),
    ],
)
def test_cloudfront_error_response_to_edb_error_response(input_, expected):
    assert expected == Migration.parse_cloudfront_error_response(input_)


def test_migration_create_internal_dns(clean_db, route53, fake_cf_client, migration):
    migration.route.dist_id = "sample-distribution-id"
    change_id = route53.expect_create_ALIAS_and_return_change_id(
        "example.gov.domains.cloud.test", "example.cloudfront.net"
    )
    route53.expect_wait_for_change_insync(change_id)
    migration.upsert_dns()


def test_migration_gets_space_id(clean_db, fake_cf_client, fake_requests, migration):
    response_body = """ {
        "metadata": {
          "guid": "asdf-asdf",
          "url": "/v2/service_instances/asdf-asdf",
          "created_at": "2016-06-08T16:41:29Z",
          "updated_at": "2016-06-08T16:41:26Z"
        },
        "entity": {
          "name": "name-1508",
          "service_guid": "a14baddf-1ccc-5299-0152-ab9s49de4422",
          "service_plan_guid": "779d2df0-9cdd-48e8-9781-ea05301cedb1",
          "space_guid": "my-space-guid",
          "type": "managed_service_instance",
          "space_url": "/v2/spaces/my-space-guid",
          "service_url": "/v2/services/a14baddf-1ccc-5299-0152-ab9s49de4422",
          "service_plan_url": "/v2/service_plans/779d2df0-9cdd-48e8-9781-ea05301cedb1",
          "service_bindings_url": "/v2/service_instances/asdf-asdf/service_bindings",
          "service_keys_url": "/v2/service_instances/asdf-asdf/service_keys",
          "routes_url": "/v2/service_instances/asdf-asdf/routes",
          "shared_from_url": "/v2/service_instances/asdf-asdf/shared_from",
          "shared_to_url": "/v2/service_instances/asdf-asdf/shared_to",
          "service_instance_parameters_url": "/v2/service_instances/asdf-asdf/parameters"
        }
    } """
    fake_requests.get(
        "http://localhost/v2/service_instances/asdf-asdf", text=response_body
    )
    assert migration.space_id == "my-space-guid"


def test_migration_gets_org_id(clean_db, fake_cf_client, fake_requests, migration):
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
    migration._space_id = "my-space-guid"
    assert migration.org_id == "my-org-guid"


def test_migration_enables_plan_in_org(
    clean_db, fake_cf_client, fake_requests, migration
):
    def service_plan_visibility_matcher(request):
        params = request.json()
        plan = "739e78F5-a919-46ef-9193-1293cc086c17"
        return (
            params["organization_guid"] == "my-org-guid"
            and params["service_plan_guid"] == plan
        )

    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    response_body = """
{
  "metadata": {
    "guid": "my-service-plan-visibility",
    "url": "/v2/service_plan_visibilities/my-service-plan-visibility",
    "created_at": "2016-06-08T16:41:31Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "organization_guid": "my-org-guid",
    "service_plan_url": "/v2/service_plans/ab5780a9-ac8e-4412-9496-4512e865011a",
    "organization_url": "/v2/organizations/my-org-guid"
  }
}
    """
    fake_requests.post(
        "http://localhost/v2/service_plan_visibilities",
        text=response_body,
        additional_matcher=service_plan_visibility_matcher,
    )

    migration.enable_migration_service_plan()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v2/service_plan_visibilities"


def test_migration_disables_plan_in_org(
    clean_db, fake_cf_client, fake_requests, migration
):
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    response_body_get = """
{
   "total_results": 1,
   "total_pages": 1,
   "prev_url": null,
   "next_url": null,
   "resources": [
      {
         "metadata": {
            "guid": "my-service-plan-visibility",
            "url": "/v2/service_plan_visibilities/my-service-plan-visibility",
            "created_at": "2021-02-22T21:15:57Z",
            "updated_at": "2021-02-22T21:15:57Z"
         },
         "entity": {
            "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
            "organization_guid": "my-org-guid",
            "service_plan_url": "/v2/service_plans/739e78F5-a919-46ef-9193-1293cc086c17",
            "organization_url": "/v2/organizations/my-org-guid"
         }
      }
   ]
}
    """
    fake_requests.get(
        "http://localhost/v2/service_plan_visibilities?q=organization_guid:my-org-guid&q=service_plan_guid:739e78F5-a919-46ef-9193-1293cc086c17",
        text=response_body_get,
    )

    response_body_delete = ""
    fake_requests.delete(
        "http://localhost/v2/service_plan_visibilities/my-service-plan-visibility",
        text=response_body_delete,
    )

    migration.disable_migration_service_plan()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url
        == "http://localhost/v2/service_plan_visibilities/my-service-plan-visibility"
    )


def test_create_bare_migrator_instance_in_org_space_success(
    clean_db, fake_cf_client, fake_requests, migration
):
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    response_body_create_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "in progress",
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
    fake_requests.post(
        "http://localhost/v2/service_instances", text=response_body_create_instance
    )

    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
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
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    migration.create_bare_migrator_instance_in_org_space()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_create_bare_migrator_instance_in_org_space_failure(
    clean_db, fake_cf_client, fake_requests, migration
):
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    response_body_create_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "in progress",
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
    fake_requests.post(
        "http://localhost/v2/service_instances", text=response_body_create_instance
    )

    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "failed",
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
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    with pytest.raises(Exception):
        migration.create_bare_migrator_instance_in_org_space()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_create_bare_migrator_instance_in_org_space_timeout_failure(
    clean_db, fake_cf_client, fake_requests, migration
):
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    response_body_create_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "in progress",
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
    fake_requests.post(
        "http://localhost/v2/service_instances", text=response_body_create_instance
    )

    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "in progress",
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
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    with pytest.raises(Exception):
        migration.create_bare_migrator_instance_in_org_space()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )

    # one for the name fetch, one for the post, 2 for the status checks
    assert len(fake_requests.request_history) == 4


def test_update_existing_cdn_domain(clean_db, fake_cf_client, fake_requests, migration):
    def update_instance_matcher(request):
        body = request.json()
        name = body.get("name")
        service_plan_guid = body.get("service_plan_guid")
        params = body.get("parameters", {})
        assert name is None
        assert service_plan_guid == "1cc78b0c-c296-48f5-9182-0b38404f79ef"
        assert params["origin"] == "example.gov"
        assert params["path"] == "/example-gov"
        assert params["forwarded_cookies"] == ["white-listed-name"]
        assert params["forward_cookie_policy"] == "whitelist"
        assert params["forwarded_headers"] == ["white-listed-name-header"]
        assert params["insecure_origin"] == False
        assert params["cloudfront_distribution_id"] == "sample-distribution-id"
        assert (
            params["cloudfront_distribution_arn"]
            == "aws:arn:cloudfront:my-cloudfront-distribution"
        )
        assert params["iam_server_certificate_name"] == "my-server-cert"
        assert params["iam_server_certificate_id"] == "my-server-cert-id"
        assert params["iam_server_certificate_arn"] == "aws:arn:iam:my-server-cert"
        error_config = params["error_responses"]
        assert error_config.get("500") == "/five-hundred"
        assert error_config.get("404") == "/four-oh-four"

        # the matcher API from requests_mock actually wants us to return False for a failed match
        # and True for a good match. We use assertions instead so the error is meaningful, but we
        # need to return True when we are done anyway
        return True

    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"
    migration.external_domain_broker_service_instance = "my-migrator-instance"
    migration._cloudfront_distribution_data = {
        "Id": "my-cloudfront-distribution",
        "ARN": "aws:arn:cloudfront:my-cloudfront-distribution",
        "DistributionConfig": {
            "Origins": {
                "Items": [
                    {
                        "Id": "my-custom-domain-id",
                        "DomainName": "example.gov",
                        "OriginPath": "/example-gov",
                        "S3OriginConfig": None,
                        "CustomOriginConfig": {"OriginProtocolPolicy": "https-only"},
                    }
                ]
            },
            "DefaultCacheBehavior": {
                "ForwardedValues": {
                    "QueryString": False,
                    "Cookies": {
                        "Forward": "whitelist",
                        "WhitelistedNames": {
                            "Quantity": 1,
                            "Items": ["white-listed-name"],
                        },
                    },
                    "Headers": {"Quantity": 1, "Items": ["white-listed-name-header"]},
                }
            },
            "CustomErrorResponses": {
                "Quantity": 2,
                "Items": [
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/four-oh-four",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 300,
                    },
                    {
                        "ErrorCode": 500,
                        "ResponsePagePath": "/five-hundred",
                        "ResponseCode": "500",
                        "ErrorCachingMinTTL": 300,
                    },
                ],
            },
            "ViewerCertificate": {
                "IAMCertificateId": "my-server-cert-id",
                "Certificate": "my-cloudfront-cert",
            },
        },
    }
    migration._iam_server_certificate_data = {
        "Path": "/",
        "ServerCertificateName": "my-server-cert",
        "ServerCertificateId": "my-server-cert-id",
        "Arn": "aws:arn:iam:my-server-cert",
        "UploadDate": datetime.date(2021, 1, 1),
        "Expiration": datetime.date(2022, 1, 1),
    }

    response_body_update_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

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
    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "update",
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

    fake_requests.put(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_update_instance,
        additional_matcher=update_instance_matcher,
    )

    fake_requests.get(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    migration.update_existing_cdn_domain()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_update_existing_cdn_domain_failure(
    clean_db, fake_cf_client, fake_requests, migration
):
    migration.route.dist_id = "some-distribution-id"
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"
    migration.external_domain_broker_service_instance = "my-migrator-instance"
    migration._cloudfront_distribution_data = {
        "Id": "my-cloudfront-distribution",
        "ARN": "aws:arn:cloudfront:my-cloudfront-distribution",
        "DistributionConfig": {
            "Origins": {
                "Items": [
                    {
                        "Id": "my-custom-domain-id",
                        "DomainName": "example.gov",
                        "OriginPath": "example.gov",
                        "S3OriginConfig": None,
                        "CustomOriginConfig": {"OriginProtocolPolicy": "https-only"},
                    }
                ]
            },
            "DefaultCacheBehavior": {
                "ForwardedValues": {
                    "QueryString": False,
                    "Cookies": {
                        "Forward": "whitelist",
                        "WhitelistedNames": {
                            "Quantity": 1,
                            "Items": ["white-listed-name"],
                        },
                    },
                    "Headers": {"Quantity": 1, "Items": ["white-listed-name-header"]},
                }
            },
            "CustomErrorResponses": {
                "Quantity": 2,
                "Items": [
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/four-oh-four",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 300,
                    },
                    {
                        "ErrorCode": 500,
                        "ResponsePagePath": "/five-hundred",
                        "ResponseCode": "500",
                        "ErrorCachingMinTTL": 300,
                    },
                ],
            },
            "ViewerCertificate": {
                "IAMCertificateId": "my-cloudfront-cert-id",
                "ACMCertificateArn": "aws:arn:acm:my-cloudfront-cert",
                "Certificate": "my-cloudfront-cert",
            },
        },
    }
    migration._iam_server_certificate_data = {
        "Path": "/",
        "ServerCertificateName": "my-server-cert",
        "ServerCertificateId": "my-server-cert-id",
        "Arn": "aws:arn:iam:my-server-cert",
        "UploadDate": datetime.date(2021, 1, 1),
        "Expiration": datetime.date(2022, 1, 1),
    }

    response_body_update_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

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
    fake_requests.put(
        "http://localhost/v2/service_instances", text=response_body_update_instance
    )

    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "update",
      "state": "failed",
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

    fake_requests.put(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_update_instance,
    )

    fake_requests.get(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    with pytest.raises(Exception):
        migration.update_existing_cdn_domain()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_update_existing_cdn_domain_timeout_failure(
    clean_db, fake_cf_client, fake_requests, migration
):
    migration.route.dist_id = "some-distribution-id"
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"
    migration.external_domain_broker_service_instance = "my-migrator-instance"
    migration._cloudfront_distribution_data = {
        "Id": "my-cloudfront-distribution",
        "ARN": "aws:arn:cloudfront:my-cloudfront-distribution",
        "DistributionConfig": {
            "Origins": {
                "Items": [
                    {
                        "Id": "my-custom-domain-id",
                        "DomainName": "example.gov",
                        "OriginPath": "example.gov",
                        "S3OriginConfig": None,
                        "CustomOriginConfig": {"OriginProtocolPolicy": "https-only"},
                    }
                ]
            },
            "DefaultCacheBehavior": {
                "ForwardedValues": {
                    "QueryString": False,
                    "Cookies": {
                        "Forward": "whitelist",
                        "WhitelistedNames": {
                            "Quantity": 1,
                            "Items": ["white-listed-name"],
                        },
                    },
                    "Headers": {"Quantity": 1, "Items": ["white-listed-name-header"]},
                }
            },
            "CustomErrorResponses": {
                "Quantity": 2,
                "Items": [
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/four-oh-four",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 300,
                    },
                    {
                        "ErrorCode": 500,
                        "ResponsePagePath": "/five-hundred",
                        "ResponseCode": "500",
                        "ErrorCachingMinTTL": 300,
                    },
                ],
            },
            "ViewerCertificate": {
                "IAMCertificateId": "my-cloudfront-cert-id",
                "ACMCertificateArn": "aws:arn:acm:my-cloudfront-cert",
                "Certificate": "my-cloudfront-cert",
            },
        },
    }
    migration._iam_server_certificate_data = {
        "Path": "/",
        "ServerCertificateName": "my-server-cert",
        "ServerCertificateId": "my-server-cert-id",
        "Arn": "aws:arn:iam:my-server-cert",
        "UploadDate": datetime.date(2021, 1, 1),
        "Expiration": datetime.date(2022, 1, 1),
    }

    response_body_update_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

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
    fake_requests.put(
        "http://localhost/v2/service_instances", text=response_body_update_instance
    )

    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

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

    fake_requests.put(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_update_instance,
    )

    fake_requests.get(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    with pytest.raises(Exception):
        migration.update_existing_cdn_domain()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_find_iam_server_certificate_data_finding_result(
    clean_db, iam_commercial, fake_cf_client, migration
):
    """ tests finding a result in multiple pages
    should also be an effective test of finding the result in one page"""
    migration._cloudfront_distribution_data = {
        "DistributionConfig": {
            "ViewerCertificate": {"IAMCertificateId": "my-server-certificate-id"}
        }
    }

    # one page of results without the right one
    iam_commercial.expect_list_server_certificates(
        "not-my-server-certificate-name",
        "not-my-server-certificate-id",
        "/cloudfront/",
        is_truncated=True,
    )
    # one page of results with the right certificate
    iam_commercial.expect_list_server_certificates(
        "my-server-certificate-name",
        "my-server-certificate-id",
        "/cloudfront/",
        marker_in="1",
        is_truncated=False,
    )
    assert migration.iam_certificate_name == "my-server-certificate-name"


def test_find_iam_server_certificate_data_without_finding_result(
    clean_db, iam_commercial, fake_cf_client, migration
):
    """ tests paging without finding results """
    migration._cloudfront_distribution_data = {
        "DistributionConfig": {
            "ViewerCertificate": {"IAMCertificateId": "my-server-certificate-id"}
        }
    }

    # one page of results without the right one
    iam_commercial.expect_list_server_certificates(
        "not-my-server-certificate-name",
        "not-my-server-certificate-id",
        "/cloudfront/",
        is_truncated=True,
    )
    # second page of results without the right one
    iam_commercial.expect_list_server_certificates(
        "not-my-server-certificate-name",
        "not-my-server-certificate-id",
        "/cloudfront/",
        marker_in="1",
        is_truncated=False,
    )
    assert migration.iam_server_certificate_data is None


def test_migration_renames_instance(clean_db, fake_cf_client, migration, fake_requests):
    # the migration fixture gives us the name "my-old-cdn"
    def name_matcher(request):
        assert request.json().get("name") == "my-old-cdn"
        assert request.json().get("parameters") == {}
        assert request.json().get("plan_guid") == None
        return True

    response_body_update_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": { },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "update",
      "state": "in progress",
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
    fake_requests.put(
        "http://localhost/v2/service_instances", text=response_body_update_instance
    )

    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
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
      "type": "update",
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

    fake_requests.put(
        "http://localhost/v2/service_instances/migrator-instance-id",
        text=response_body_update_instance,
        additional_matcher=name_matcher,
    )

    fake_requests.get(
        "http://localhost/v2/service_instances/migrator-instance-id",
        text=response_body_check_instance,
    )

    migration.external_domain_broker_service_instance = "migrator-instance-id"
    migration.update_instance_name()

    assert fake_requests.request_history[-2].method == "PUT"
    assert (
        fake_requests.request_history[-2].url
        == "http://localhost/v2/service_instances/migrator-instance-id"
    )
    assert fake_requests.request_history[-1].method == "GET"
    assert (
        fake_requests.request_history[-1].url
        == "http://localhost/v2/service_instances/migrator-instance-id"
    )


def test_migration_marks_route_migrated(clean_db, fake_cf_client, migration):
    migration.mark_complete()
    assert migration.route.state == "migrated"


def test_migration_migrates_happy_path(
    clean_db, fake_cf_client, iam_commercial, route53, cloudfront, dns, fake_requests
):
    """
    Migrate should:
    - enable the migration plan
    - create a migration instance
    - wait for the migration instance to be created
    - call update on the migration instance
    - wait for the update to complete
    - mark the old instance migrated
    - call purge on the old instance
    - disable the migration plan
    """
    service_instance_data_response_body = """
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
        "http://localhost/v2/service_instances/asdf-asdf",
        text=service_instance_data_response_body,
    )
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.com"
    migration = Migration(route, clean_db, fake_cf_client)

    # load caches so we can slim this test down.
    # We've already tested calls and lazy-loading elsewhere, so we can skip the mocks here
    migration._space_id = "my-space-id"
    migration._org_id = "my-org-id"
    migration._cloudfront_distribution_data = {
        "Id": "my-cloudfront-distribution",
        "ARN": "aws:arn:cloudfront:my-cloudfront-distribution",
        "DistributionConfig": {
            "Origins": {
                "Items": [
                    {
                        "Id": "my-custom-domain-id",
                        "DomainName": "example.gov",
                        "OriginPath": "example.gov",
                        "S3OriginConfig": None,
                        "CustomOriginConfig": {"OriginProtocolPolicy": "https-only"},
                    }
                ]
            },
            "DefaultCacheBehavior": {
                "ForwardedValues": {
                    "QueryString": False,
                    "Cookies": {
                        "Forward": "whitelist",
                        "WhitelistedNames": {
                            "Quantity": 1,
                            "Items": ["white-listed-name"],
                        },
                    },
                    "Headers": {"Quantity": 1, "Items": ["white-listed-name-header"]},
                }
            },
            "CustomErrorResponses": {
                "Quantity": 2,
                "Items": [
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/four-oh-four",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 300,
                    },
                    {
                        "ErrorCode": 500,
                        "ResponsePagePath": "/five-hundred",
                        "ResponseCode": "500",
                        "ErrorCachingMinTTL": 300,
                    },
                ],
            },
            "ViewerCertificate": {
                "IAMCertificateId": "my-cloudfront-cert-id",
                "ACMCertificateArn": "aws:arn:acm:my-cloudfront-cert",
                "Certificate": "my-cloudfront-cert",
            },
        },
    }
    migration._iam_server_certificate_data = {
        "Path": "/",
        "ServerCertificateName": "my-server-cert",
        "ServerCertificateId": "my-server-cert-id",
        "Arn": "aws:arn:iam:my-server-cert",
        "UploadDate": datetime.date(2021, 1, 1),
        "Expiration": datetime.date(2022, 1, 1),
    }

    domains = ["example.gov", "foo.com"]
    create_service_plan_visibility_response_body = """
    {
  "metadata": {
    "guid": "new-plan-visibility-guid",
    "url": "/v2/service_plan_visibilities/new-plan-visibility-guid",
    "created_at": "2016-06-08T16:41:31Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "service_plan_guid": "foo",
    "organization_guid": "bar",
    "service_plan_url": "/v2/service_plans/foo",
    "organization_url": "/v2/organizations/bar"
  }
}
"""
    fake_requests.post(
        "http://localhost/v2/service_plan_visibilities",
        text=create_service_plan_visibility_response_body,
    )

    create_service_instance_response_body = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": {

    },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "create",
      "state": "in progress",
      "description": "",
      "updated_at": "2016-06-08T16:41:26Z",
      "created_at": "2016-06-08T16:41:29Z"
    },
    "space_url": "/v2/spaces/my-space-1-guid",
    "service_plan_url": "/v2/service_plans/739e78F5-a919-46ef-9193-1293cc086c17",
    "service_bindings_url": "/v2/service_instances/my-migrator-instance/service_bindings",
    "service_keys_url": "/v2/service_instances/my-migrator-instance/service_keys",
    "routes_url": "/v2/service_instances/my-migrator-instance/routes",
    "shared_from_url": "/v2/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/shared_from",
    "shared_to_url": "/v2/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/shared_to"
  }
}"""

    fake_requests.post(
        "http://localhost/v2/service_instances",
        text=create_service_instance_response_body,
    )

    service_instance_create_check_response_body = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
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
}"""

    fake_requests.get(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=service_instance_create_check_response_body,
    )
    update_service_instance_response_body = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:30Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": { },
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
    "tags": [ ],
    "maintenance_info": {
      "version": "2.1.0",
      "description": "OS image update. Expect downtime."
    },
    "space_url": "/v2/spaces/my-space-guid",
    "service_plan_url": "/v2/service_plans/739e78F5-a919-46ef-9193-1293cc086c17",
    "service_bindings_url": "/v2/service_instances/my-migrator-instance/service_bindings",
    "service_keys_url": "/v2/service_instances/my-migrator-instance/service_keys",
    "routes_url": "/v2/service_instances/my-migrator-instance/routes",
    "shared_from_url": "/v2/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/shared_from",
    "shared_to_url": "/v2/service_instances/0d632575-bb06-4ea5-bb19-a451a9644d92/shared_to"
  }
}"""

    fake_requests.put(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=update_service_instance_response_body,
    )
    service_instance_update_check_response_body = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": { },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "update",
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
}"""

    fake_requests.get(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=service_instance_update_check_response_body,
    )
    service_visibilities_response = """
{
   "total_results": 1,
   "total_pages": 1,
   "prev_url": null,
   "next_url": null,
   "resources": [
      {
         "metadata": {
            "guid": "my-service-plan-visibility",
            "url": "/v2/service_plan_visibilities/my-service-plan-visibility",
            "created_at": "2021-02-22T21:15:57Z",
            "updated_at": "2021-02-22T21:15:57Z"
         },
         "entity": {
            "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
            "organization_guid": "my-org-guid",
            "service_plan_url": "/v2/service_plans/739e78F5-a919-46ef-9193-1293cc086c17",
            "organization_url": "/v2/organizations/my-org-guid"
         }
      }
   ]
}
    """
    fake_requests.get(
        "http://localhost/v2/service_plan_visibilities?q=organization_guid:my-org-id&q=service_plan_guid:739e78F5-a919-46ef-9193-1293cc086c17",
        text=service_visibilities_response,
    )
    response_body = ""
    fake_requests.delete(
        "http://localhost/v2/service_plan_visibilities/my-service-plan-visibility",
        text=response_body,
    )

    purge_service_instance_body = """{
  "metadata": {
    "guid": "asdf-asdf",
    "url": "/v2/service_instances/asdf-asdf",
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
        "http://localhost/v2/service_instances/asdf-asdf?purge=true", text=response_body
    )

    response_body_update_instance_name = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
    "created_at": "2016-06-08T16:41:29Z",
    "updated_at": "2016-06-08T16:41:26Z"
  },
  "entity": {
    "name": "external-domain-broker-migrator",
    "credentials": { },
    "service_plan_guid": "739e78F5-a919-46ef-9193-1293cc086c17",
    "space_guid": "my-space-guid",
    "gateway_data": null,
    "dashboard_url": null,
    "type": "managed_service_instance",
    "last_operation": {
      "type": "update",
      "state": "in progress",
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
    response_body_check_instance = """
{
  "metadata": {
    "guid": "my-migrator-instance",
    "url": "/v2/service_instances/my-migrator-instance",
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
      "type": "update",
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

    def name_matcher(request):
        return request.json().get("name") == "my-old-cdn"

    fake_requests.put(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_update_instance_name,
        additional_matcher=name_matcher,
    )

    fake_requests.get(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    migration.migrate()

    assert fake_requests.called
    history = [request.url for request in fake_requests.request_history]

    assert (
        fake_requests.request_history[3].url
        == "http://localhost/v2/service_plan_visibilities"
    )
    assert fake_requests.request_history[3].method == "POST"

    assert (
        fake_requests.request_history[4].url == "http://localhost/v2/service_instances"
    )
    assert fake_requests.request_history[4].method == "POST"
    assert (
        fake_requests.request_history[5].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )
    assert fake_requests.request_history[5].method == "GET"
    assert (
        fake_requests.request_history[6].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )
    assert fake_requests.request_history[6].method == "PUT"
    assert (
        fake_requests.request_history[7].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )
    assert fake_requests.request_history[7].method == "GET"
    assert (
        fake_requests.request_history[8].url
        == "http://localhost/v2/service_plan_visibilities?q=organization_guid%3Amy-org-id&q=service_plan_guid%3A739e78F5-a919-46ef-9193-1293cc086c17"
    )
    assert fake_requests.request_history[8].method == "GET"
    assert (
        fake_requests.request_history[9].url
        == "http://localhost/v2/service_plan_visibilities/my-service-plan-visibility"
    )
    assert fake_requests.request_history[9].method == "DELETE"

    assert (
        fake_requests.request_history[10].url
        == "http://localhost/v2/service_instances/asdf-asdf?purge=true"
    )
    assert fake_requests.request_history[10].method == "DELETE"

    assert fake_requests.request_history[11].method == "PUT"
    assert (
        fake_requests.request_history[11].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )
    assert fake_requests.request_history[12].method == "GET"
    assert (
        fake_requests.request_history[12].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )

    assert route.state == "migrated"
