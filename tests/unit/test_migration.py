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


def test_validate_good_dns(clean_db, dns, fake_cf_client):
    dns.add_cname("_acme-challenge.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com"
    migration = Migration(route, clean_db, fake_cf_client)
    assert migration.has_valid_dns


def test_validate_bad_dns(clean_db, dns, fake_cf_client):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com"
    migration = Migration(route, clean_db, fake_cf_client)
    assert not migration.has_valid_dns


def test_validate_mixed_good_and_bad_dns(clean_db, dns, fake_cf_client):
    dns.add_cname("_acme-challenge.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    migration = Migration(route, clean_db, fake_cf_client)
    assert not migration.has_valid_dns


def test_validate_multiple_valid_dns(clean_db, dns, fake_cf_client):
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    migration = Migration(route, clean_db, fake_cf_client)
    assert Migration.has_valid_dns


def test_migration_init(clean_db, fake_cf_client):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
    assert sorted(migration.domains) == sorted(["example.com", "foo.example.com"])
    assert migration.instance_id == "asdf-asdf"
    assert migration.cloudfront_distribution_id == "some-distribution-id"


def test_migration_loads_cloudfront_config(clean_db, cloudfront, fake_cf_client):
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
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.dist_id = "sample-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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
    clean_db, cloudfront, fake_cf_client
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
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.dist_id = "sample-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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


def test_migration_create_internal_dns(clean_db, route53, fake_cf_client):
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db, fake_cf_client)
    change_id = route53.expect_create_ALIAS_and_return_change_id(
        "example.gov.domains.cloud.test", "example.cloudfront.net"
    )
    route53.expect_wait_for_change_insync(change_id)
    migration.upsert_dns()


def test_migration_gets_space_id(clean_db, fake_cf_client, fake_requests):
    response_body = """ {
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
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
    assert migration.space_id == "my-space-guid"


def test_migration_gets_org_id(clean_db, fake_cf_client, fake_requests):
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
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
    migration._space_id = "my-space-guid"
    assert migration.org_id == "my-org-guid"


def test_migration_enables_plan_in_org(clean_db, fake_cf_client, fake_requests):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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
        "http://localhost/v2/service_plan_visibilities", text=response_body
    )

    migration.enable_migration_service_plan()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v2/service_plan_visibilities"


def test_migration_disables_plan_in_org(clean_db, fake_cf_client, fake_requests):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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
    clean_db, fake_cf_client, fake_requests
):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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
    clean_db, fake_cf_client, fake_requests
):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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
    clean_db, fake_cf_client, fake_requests
):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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

    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )

    # one for the post, 2 for the status checks
    assert len(fake_requests.request_history) == 3


def test_update_existing_cdn_domain(clean_db, fake_cf_client, fake_requests):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "my-route-instance-id"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db, fake_cf_client)
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
                    },
                ]
            },
            "DefaultCacheBehavior": {
                "ForwardedValues": {
                    "QueryString": False,
                    "Cookies": {
                        "Forward": "whitelist",
                        "WhitelistedNames": {
                            "Quantity": 1,
                            "Items": [
                                "white-listed-name",
                            ],
                        },
                    },
                    "Headers": {
                        "Quantity": 1,
                        "Items": [
                            "white-listed-name-header",
                        ],
                    },
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
