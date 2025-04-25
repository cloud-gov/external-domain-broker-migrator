import datetime

from cloudfoundry_client.errors import InvalidStatusCode
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


def test_get_migrations(clean_db, fake_cf_client, mocker):

    good_result = dict(entity=dict(name="my-old-cdn"))
    bad_result = InvalidStatusCode("404", "not here")
    get_instance_mock = mocker.patch(
        "migrator.migration.cf.get_instance_data",
        side_effect=[good_result, good_result, good_result, good_result, bad_result],
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
    assert get_instance_mock.call_count == 5


def test_migration_for_instance_id(clean_db, fake_cf_client, fake_requests, mocker):
    good_result = dict(entity=dict(name="my-old-cdn"))
    get_instance_mock = mocker.patch(
        "migrator.migration.cf.get_instance_data", return_value=good_result
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
    get_instance_mock.assert_called_once_with("alb-5678", fake_cf_client)


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


def test_migration_gets_space_id(clean_db, fake_cf_client, migration, mocker):
    instance_fetch_mock = mocker.patch(
        "migrator.migration.cf.get_space_id_for_service_instance_id",
        return_value="my-space-guid",
    )
    # check state before, so we know we're doing _something_
    assert migration._space_id is None
    # make sure we get the right value
    assert migration.space_id == "my-space-guid"
    # get the value after to make sure we'll remember it
    assert migration._space_id is not None
    # try a few more times
    assert migration.space_id == "my-space-guid"
    assert migration.space_id == "my-space-guid"
    assert migration.space_id == "my-space-guid"
    # assert we only called the client once
    instance_fetch_mock.assert_called_once_with("asdf-asdf", fake_cf_client)


def test_migration_gets_org_id(clean_db, fake_cf_client, migration, mocker):
    instance_fetch_mock = mocker.patch(
        "migrator.migration.cf.get_org_id_for_space_id", return_value="my-org-guid"
    )
    # prime space id, so we only have one call to think about
    migration._space_id = "my-space-guid"
    # check state before, so we know we're doing _something_
    assert migration._org_id is None
    # make sure we get the right value
    assert migration.org_id == "my-org-guid"
    # get the value after to make sure we'll remember it
    assert migration._org_id is not None
    # try a few more times
    assert migration.org_id == "my-org-guid"
    assert migration.org_id == "my-org-guid"
    assert migration.org_id == "my-org-guid"
    # assert we only called the client once
    instance_fetch_mock.assert_called_once_with("my-space-guid", fake_cf_client)


def test_migration_enables_plan_in_org(
    clean_db, fake_cf_client, fake_requests, migration
):
    def service_plan_visibility_matcher(request):
        params = request.json()
        return params.get("organizations", [{}])[0].get("guid") == "my-org-guid"

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
    assert (
        last_request.url
        == "http://localhost/v3/service_plans/FAKE-MIGRATION-PLAN-GUID/visibility"
    )


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
    clean_db, fake_cf_client, migration, mocker
):
    migration._space_id = "my-space-guid"
    migration._org_id = "my-org-guid"

    assert migration.external_domain_broker_service_instance is None
    create_mocker = mocker.patch(
        "migrator.migration.cf.create_bare_migrator_service_instance_in_space",
        return_value="my-job",
    )
    wait_mocker = mocker.patch(
        "migrator.migration.cf.wait_for_service_instance_ready",
        return_value="my-instance-id",
    )
    migration.create_bare_migrator_instance_in_org_space()
    create_mocker.assert_called_once_with(
        "my-space-guid",
        "FAKE-MIGRATION-PLAN-GUID",
        "migrating-instance-my-old-cdn",
        ["example.gov"],
        fake_cf_client,
    )
    wait_mocker.assert_called_once_with("my-job", fake_cf_client)

    assert migration.external_domain_broker_service_instance == "my-instance-id"


def test_migration_renames_instance(clean_db, fake_cf_client, migration, mocker):
    update_service_instance_mock = mocker.patch(
        "migrator.migration.cf.update_existing_cdn_domain_service_instance",
        return_value="my-job-id"
    )
    instance_status_mock = mocker.patch(
        "migrator.migration.cf.wait_for_service_instance_ready",
        return_value="migrator-instance-id",
    )
    migration.external_domain_broker_service_instance = "migrator-instance-id"
    migration.update_instance_name()
    update_service_instance_mock.assert_called_once_with(
        "migrator-instance-id", {}, fake_cf_client, new_instance_name="my-old-cdn"
    )

    instance_status_mock.assert_called_once_with("my-job-id", fake_cf_client)


def test_migration_marks_route_migrated(clean_db, fake_cf_client, migration):
    migration.mark_complete()
    assert migration.route.state == "migrated"
