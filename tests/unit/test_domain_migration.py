import datetime

import pytest

from migrator.models import DomainRoute, DomainAlbProxy, DomainCertificate
from migrator.migration import DomainMigration


@pytest.fixture
def domain_route(clean_db):
    proxy = DomainAlbProxy()
    proxy.alb_arn = "arn:123"
    proxy.alb_dns_name = "foo.example.com"
    proxy.listener_arn = "arn:234"

    route = DomainRoute()
    route.state = "provisioned"
    route.domains = ["www0.example.gov", "www1.example.gov"]
    route.instance_id = "asdf-asdf"
    route.alb_proxy = proxy

    certificate = DomainCertificate()
    certificate.route = route
    certificate.iam_server_certificate_name = "my-cert-name"
    certificate.iam_server_certificate_arn = "my-cert-arn"
    certificate.iam_server_certificate_id = "my-cert-id"
    return route


@pytest.fixture
def domain_migration(clean_db, fake_cf_client, fake_requests, domain_route):
    return subtest_migration_instantiable(
        clean_db, fake_cf_client, fake_requests, domain_route
    )


def test_gets_certificate_data(domain_migration):
    assert domain_migration.iam_certificate_id == "my-cert-id"


def test_gets_active_cert(clean_db, domain_migration):
    route = domain_migration.route
    cert = route.certificates[0]
    cert.expires = datetime.datetime.now()

    certificate0 = DomainCertificate()
    certificate0.route = route
    certificate0.iam_server_certificate_name = "my-cert-name-0"
    certificate0.iam_server_certificate_arn = "my-cert-arn-0"
    certificate0.iam_server_certificate_id = "my-cert-id-0"
    certificate0.expires = datetime.datetime.now() + datetime.timedelta(days=1)

    certificate1 = DomainCertificate()
    certificate1.route = route
    certificate1.iam_server_certificate_name = "my-cert-name-2"
    certificate1.iam_server_certificate_arn = "my-cert-arn-2"
    certificate1.iam_server_certificate_id = "my-cert-id-2"
    certificate1.expires = datetime.datetime.now() - datetime.timedelta(days=1)

    clean_db.add(route)
    clean_db.add(cert)
    clean_db.add(certificate0)
    clean_db.add(certificate1)
    clean_db.commit()
    clean_db.expunge_all()
    route = clean_db.query(DomainRoute).filter_by(instance_id="asdf-asdf").first()
    domain_migration.route = route
    assert (
        domain_migration.current_certificate.iam_server_certificate_arn
        == "my-cert-arn-0"
    )


def subtest_migration_instantiable(
    clean_db, fake_cf_client, fake_requests, domain_route
):
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
    migration = DomainMigration(domain_route, clean_db, fake_cf_client)

    assert fake_requests.called
    assert fake_requests.request_history[0].method == "GET"
    assert (
        fake_requests.request_history[0].url
        == "http://localhost/v2/service_instances/asdf-asdf"
    )
    # reset the mock in subtests to make it easier to reason about
    fake_requests.reset_mock()
    return migration


def test_domain_migration_migrates(
    clean_db, fake_cf_client, fake_requests, domain_route
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
    migration = subtest_migration_instantiable(
        clean_db, fake_cf_client, fake_requests, domain_route
    )

    # load caches so we can slim this test down.
    # We've already tested calls and lazy-loading elsewhere, so we can skip the mocks here
    migration._space_id = "my-space-id"
    migration._org_id = "my-org-id"
    migration._iam_server_certificate_data = {
        "Path": "/",
        "ServerCertificateName": "my-cert-name",
        "ServerCertificateId": "my-cert-id",
        "Arn": "aws:arn:iam:my-cert-name",
        "UploadDate": datetime.date(2021, 1, 1),
        "Expiration": datetime.date(2022, 1, 1),
    }

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
            "credentials": { },
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
    }
    """

    def create_param_matcher(request):
        domains_in = request.json().get("parameters", {}).get("domains", [])
        assert sorted(domains_in) == sorted(["www0.example.gov", "www1.example.gov"])
        return True

    fake_requests.post(
        "http://localhost/v2/service_instances",
        text=create_service_instance_response_body,
        additional_matcher=create_param_matcher,
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

    def update_instance_matcher(request):
        body = request.json()
        name = body.get("name")
        service_plan_guid = body.get("service_plan_guid")
        params = body.get("parameters", {})
        if name is None:
            # the service plan update
            assert params.get("iam_server_certificate_name") == "my-cert-name"
            assert params.get("iam_server_certificate_id") == "my-cert-id"
            assert params.get("iam_server_certificate_arn") == "my-cert-arn"
            assert params.get("domain_internal") == "foo.example.com"
            assert params.get("alb_arn") == "arn:123"
            assert params.get("alb_listener_arn") == "arn:234"
            assert params.get("hosted_zone_id") == "FAKEZONEIDFORALBS"
            return service_plan_guid == "FAKE-DOMAIN-PLAN-GUID"
        else:
            # the name update
            return params == {}

    fake_requests.put(
        "http://localhost/v2/service_instances/my-migrator-instance?accepts_incomplete=true",
        text=update_service_instance_response_body,
        additional_matcher=update_instance_matcher,
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
        "http://localhost/v2/service_plan_visibilities?q=organization_guid:my-org-id&q=service_plan_guid:FAKE-MIGRATION-PLAN-GUID",
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

    }"""

    fake_requests.delete(
        "http://localhost/v2/service_instances/asdf-asdf?purge=true",
        text=purge_service_instance_body,
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

    fake_requests.get(
        "http://localhost/v2/service_instances/my-migrator-instance",
        text=response_body_check_instance,
    )

    migration.migrate()

    # enable service plan
    assert (
        fake_requests.request_history[0].url
        == "http://localhost/v2/service_plan_visibilities"
    )
    assert fake_requests.request_history[0].method == "POST"

    # create service instance
    assert (
        fake_requests.request_history[1].url
        == "http://localhost/v2/service_instances?accepts_incomplete=true"
    )
    assert fake_requests.request_history[1].method == "POST"

    # wait for service instance
    assert (
        fake_requests.request_history[2].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )
    assert fake_requests.request_history[2].method == "GET"

    # update service instance
    assert (
        fake_requests.request_history[3].url
        == "http://localhost/v2/service_instances/my-migrator-instance?accepts_incomplete=true"
    )
    assert fake_requests.request_history[3].method == "PUT"
    # wait for instance
    assert (
        fake_requests.request_history[4].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )
    assert fake_requests.request_history[4].method == "GET"

    # find service plan visibility
    assert (
        fake_requests.request_history[5].url
        == "http://localhost/v2/service_plan_visibilities?q=organization_guid%3Amy-org-id&q=service_plan_guid%3AFAKE-MIGRATION-PLAN-GUID"
    )
    assert fake_requests.request_history[5].method == "GET"

    # delete service plan visibility
    assert (
        fake_requests.request_history[6].url
        == "http://localhost/v2/service_plan_visibilities/my-service-plan-visibility"
    )
    assert fake_requests.request_history[6].method == "DELETE"

    # purge old instance
    assert (
        fake_requests.request_history[7].url
        == "http://localhost/v2/service_instances/asdf-asdf?purge=true"
    )
    assert fake_requests.request_history[7].method == "DELETE"

    # rename new instance
    assert fake_requests.request_history[8].method == "PUT"
    assert (
        fake_requests.request_history[8].url
        == "http://localhost/v2/service_instances/my-migrator-instance?accepts_incomplete=true"
    )

    # check rename status
    assert fake_requests.request_history[9].method == "GET"
    assert (
        fake_requests.request_history[9].url
        == "http://localhost/v2/service_instances/my-migrator-instance"
    )

    # make sure we're all done
    assert migration.route.state == "migrated"
