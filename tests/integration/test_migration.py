import datetime

import pytest

from migrator.migration import (
    find_migrations,
    migration_for_instance_id,
    find_active_instances,
    Migration,
    DomainMigration,
    CdnMigration,
)
from migrator.models import CdnRoute, DomainRoute


def test_find_instances(clean_db):
    states = [
        "provisioned",
        "deprovisioned",
        "deprovisioning",
        "this-state-should-never-exist",
    ]
    for state in states:
        domain_route = DomainRoute()
        domain_route.state = state
        domain_route.instance_id = f"id-{state}"
        cdn_route = CdnRoute()
        cdn_route.state = state
        cdn_route.instance_id = f"id-{state}"
        clean_db.add(domain_route)
        clean_db.add(cdn_route)
    clean_db.commit()
    clean_db.close()
    instances = find_active_instances(clean_db)
    assert len(instances) == 2
    assert instances[0].state == "provisioned"
    assert instances[1].state == "provisioned"


def test_get_migrations(clean_db, fake_cf_client, fake_requests):
    # instances that should work
    dont_care_instance_response_body = """ {
        "entity": {
          "space_guid": "my-space-guid",
          "name": "my-instance-name"
        }
    } """

    # instance that should not work
    not_found_response = """
    {
        "description": "The service instance could not be found: nope",
        "error_code": "CF-ServiceInstanceNotFound",
        "code": 60004
    }"""
    fake_requests.get(
        "http://localhost/v2/service_instances/alb-1234",
        text=dont_care_instance_response_body,
    )
    fake_requests.get(
        "http://localhost/v2/service_instances/alb-5678",
        text=dont_care_instance_response_body,
    )
    fake_requests.get(
        "http://localhost/v2/service_instances/cdn-1234",
        text=dont_care_instance_response_body,
    )
    fake_requests.get(
        "http://localhost/v2/service_instances/cdn-5678",
        text=dont_care_instance_response_body,
    )

    # blow up on this one
    fake_requests.get(
        "http://localhost/v2/service_instances/bad-404",
        status_code=404,
        reason="Not Found",
        text=not_found_response,
    )

    domain_route0 = DomainRoute()
    domain_route0.state = "provisioned"
    domain_route0.instance_id = "alb-1234"
    domain_route1 = DomainRoute()
    domain_route1.state = "provisioned"
    domain_route1.instance_id = "alb-5678"
    cdn_route0 = CdnRoute()
    cdn_route0.state = "provisioned"
    cdn_route0.instance_id = "cdn-1234"
    cdn_route0.domain_external = "blah"
    cdn_route1 = CdnRoute()
    cdn_route1.state = "provisioned"
    cdn_route1.instance_id = "cdn-5678"
    cdn_route1.domain_external = "blah"
    bad_route0 = CdnRoute()
    bad_route0.state = "provisioned"
    bad_route0.instance_id = "bad-404"
    bad_route0.domain_external = "blah"
    clean_db.add(domain_route0)
    clean_db.add(domain_route1)
    clean_db.add(cdn_route0)
    clean_db.add(cdn_route1)
    clean_db.add(bad_route0)
    clean_db.commit()
    migrations = find_migrations(clean_db, fake_cf_client)
    assert len(migrations) == 4


def test_migration_for_instance_id(clean_db, fake_cf_client, fake_requests):
    # these stubs are just so we don't blow up later
    dont_care_instance_response_body = """ {
        "entity": {
          "space_guid": "my-space-guid",
          "name": "my-instance-name"
        }
    } """
    fake_requests.get(
        "http://localhost/v2/service_instances/alb-1234",
        text=dont_care_instance_response_body,
    )
    fake_requests.get(
        "http://localhost/v2/service_instances/alb-5678",
        text=dont_care_instance_response_body,
    )
    fake_requests.get(
        "http://localhost/v2/service_instances/cdn-1234",
        text=dont_care_instance_response_body,
    )
    fake_requests.get(
        "http://localhost/v2/service_instances/cdn-5678",
        text=dont_care_instance_response_body,
    )
    # end stubs

    domain_route0 = DomainRoute()
    domain_route0.state = "provisioned"
    domain_route0.instance_id = "alb-1234"
    domain_route1 = DomainRoute()
    domain_route1.state = "provisioned"
    domain_route1.instance_id = "alb-5678"
    cdn_route0 = CdnRoute()
    cdn_route0.state = "provisioned"
    cdn_route0.instance_id = "cdn-1234"
    cdn_route1 = CdnRoute()
    cdn_route1.state = "provisioned"
    cdn_route1.instance_id = "cdn-5678"
    clean_db.add(domain_route0)
    clean_db.add(domain_route1)
    clean_db.add(cdn_route0)
    clean_db.add(cdn_route1)
    clean_db.commit()
    migration = migration_for_instance_id("alb-5678", clean_db, fake_cf_client)
    assert isinstance(migration, DomainMigration)
    assert migration.route.instance_id == "alb-5678"


def test_validate_good_dns(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("_acme-challenge.www.example.com")
    dns.add_cname("www.example.com")
    migration.domains = ["www.example.com"]
    assert migration.has_valid_dns


def test_validate_bad_dns(clean_db, dns, fake_cf_client, migration):
    migration.domains = ["example.com"]
    assert not migration.has_valid_dns


def test_validate_mixed_good_and_bad_dns(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("_acme-challenge.www.example.com")
    dns.add_cname("www.example.com")
    migration.domains = ["www.example.com", "foo.example.com"]
    assert not migration.has_valid_dns


def test_validate_site_exists_acme_doesnt(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("www.example.com")
    migration.domains = ["www.example.com"]
    assert not migration.has_valid_dns


def test_validate_acme_exists_site_doesnt(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("_acme-challenge.www.example.com")
    migration.domains = ["www.example.com"]
    assert not migration.has_valid_dns


def test_validate_multiple_valid_dns(clean_db, dns, fake_cf_client, migration):
    dns.add_cname("_acme-challenge.www.example.com")
    dns.add_cname("_acme-challenge.foo.example.com")
    dns.add_cname("www.example.com")
    dns.add_cname("foo.example.com")
    migration.domains = ["www.example.com", "foo.example.com"]
    assert migration.has_valid_dns


def test_validate_multiple_valid_acme_no_good_site_dns(
    clean_db, dns, fake_cf_client, migration
):
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.example.com")
    migration.domains = ["example.com", "foo.example.com"]
    assert not migration.has_valid_dns


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
       # params = request.json()
       # plan = "FAKE-MIGRATION-PLAN-GUID"
       # return (
       #     params["organization_guid"] == "my-org-guid"
       #     and params["service_plan_guid"] == plan
       # )
       return True

    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    response_body = """
{
  "type": "organization",
  "organizations": [
    {
      "guid": "my-org-id",
      "name": "other_org"
    }
  ]
}
    """
    fake_requests.post(
        "http://localhost/v3/service_plans/FAKE-MIGRATION-PLAN-GUID/visibility",
        text=response_body,
        additional_matcher=service_plan_visibility_matcher,
    )

    migration.enable_migration_service_plan()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert last_request.url == "http://localhost/v3/service_plans/FAKE-MIGRATION-PLAN-GUID/visibility"


def test_migration_disables_plan_in_org(
    clean_db, fake_cf_client, fake_requests, migration
):
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    response_body_delete = ""
    fake_requests.delete(
        "http://localhost/v3/service_plans/FAKE-MIGRATION-PLAN-GUID/visibility/my-org-guid",
        text=response_body_delete,
    )

    migration.disable_migration_service_plan()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url
        == "http://localhost/v3/service_plans/FAKE-MIGRATION-PLAN-GUID/visibility/my-org-guid"
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
        "http://localhost/v2/service_instances/migrator-instance-id?accepts_incomplete=true",
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
        == "http://localhost/v2/service_instances/migrator-instance-id?accepts_incomplete=true"
    )
    assert fake_requests.request_history[-1].method == "GET"
    assert (
        fake_requests.request_history[-1].url
        == "http://localhost/v2/service_instances/migrator-instance-id"
    )


def test_migration_marks_route_migrated(clean_db, fake_cf_client, migration):
    migration.mark_complete()
    assert migration.route.state == "migrated"
