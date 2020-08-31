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


def test_validate_good_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com"
    migration = Migration(route)
    assert migration.has_valid_dns


def test_validate_bad_dns(clean_db, dns):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com"
    migration = Migration(route)
    assert not migration.has_valid_dns


def test_validate_mixed_good_and_bad_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    migration = Migration(route)
    assert not migration.has_valid_dns


def test_validate_multiple_valid_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    migration = Migration(route)
    assert Migration.has_valid_dns


def test_migration_init(clean_db):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route)
    assert sorted(migration.domains) == sorted(["example.com", "foo.example.com"])
    assert migration.instance_id == "asdf-asdf"
    assert migration.cloudfront_distribution_id == "some-distribution-id"


def test_migration_loads_cloudfront_config(clean_db, cloudfront):
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
    migration = Migration(route)
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


def test_migration_loads_cloudfront_config_with_no_error_reponses(clean_db, cloudfront):
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
    migration = Migration(route)
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
