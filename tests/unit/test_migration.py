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
    migration = Migration(route, clean_db)
    assert migration.has_valid_dns


def test_validate_bad_dns(clean_db, dns):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com"
    migration = Migration(route, clean_db)
    assert not migration.has_valid_dns


def test_validate_mixed_good_and_bad_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    migration = Migration(route, clean_db)
    assert not migration.has_valid_dns


def test_validate_multiple_valid_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    migration = Migration(route, clean_db)
    assert Migration.has_valid_dns


def test_migration_init(clean_db):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    route.dist_id = "some-distribution-id"
    migration = Migration(route, clean_db)
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
    migration = Migration(route, clean_db)
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
    migration = Migration(route, clean_db)
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


def test_migration_creates_edb_instance(clean_db, cloudfront):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="/test",
        distribution_id="sample-distribution-id",
        status="active",
        custom_error_responses={"Quantity": 0},
    )
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db)
    si = migration.external_domain_broker_service_instance
    assert si.domain_names == domains
    assert si.domain_internal == "example.cloudfront.net"
    assert si.origin_protocol_policy == "https-only"
    assert (
        si.cloudfront_distribution_arn
        == "arn:aws:cloudfront::000000000000:distribution/sample-distribution-id"
    )
    assert si.cloudfront_origin_hostname == "cloud.test"
    assert si.cloudfront_origin_path == "/test"
    assert si.forward_cookie_policy == "all"
    assert si.forwarded_headers == ["HOST"]
    cloudfront.assert_no_pending_responses()


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


def test_migration_creates_edb_instance_with_error_pages(clean_db, cloudfront):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="/test",
        distribution_id="sample-distribution-id",
        status="active",
        custom_error_responses={
            "Quantity": 1,
            "Items": [
                {"ErrorCode": 404, "ResponsePagePath": "/path", "ResponseCode": "404"}
            ],
        },
    )
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db)
    si = migration.external_domain_broker_service_instance
    assert si.error_responses == {"404": "/path"}
    cloudfront.assert_no_pending_responses()


def test_migration_creates_edb_instance_with_forward_headers(clean_db, cloudfront):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="/test",
        distribution_id="sample-distribution-id",
        status="active",
        forwarded_headers=["HOST", "my-header"],
    )
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db)
    si = migration.external_domain_broker_service_instance
    assert si.forwarded_headers == ["HOST", "my-header"]
    cloudfront.assert_no_pending_responses()


def test_migration_creates_edb_instance_with_forward_cookies_filtered(
    clean_db, cloudfront
):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="/test",
        distribution_id="sample-distribution-id",
        status="active",
        forward_cookie_policy="whitelist",
        forwarded_cookies=["cookie_one", "cookie_two"],
    )
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db)
    si = migration.external_domain_broker_service_instance
    cloudfront.assert_no_pending_responses()
    assert si.forward_cookie_policy == "whitelist"
    assert si.forwarded_cookies == ["cookie_one", "cookie_two"]


def test_migration_creates_edb_instance_with_forward_cookies_none(clean_db, cloudfront):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="/test",
        distribution_id="sample-distribution-id",
        status="active",
        forward_cookie_policy="none",
    )
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db)
    si = migration.external_domain_broker_service_instance
    cloudfront.assert_no_pending_responses()
    assert si.forward_cookie_policy == "none"
    assert si.forwarded_cookies == []


def test_migration_creates_edb_instance_with_forward_cookies_all(clean_db, cloudfront):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="/test",
        distribution_id="sample-distribution-id",
        status="active",
        forward_cookie_policy="all",
    )
    route = CdnRoute()
    route.state = "provisioned"
    route.domain_external = "example.gov"
    route.domain_internal = "example.cloudfront.net"
    route.dist_id = "sample-distribution-id"
    route.instance_id = "some-service-instance-id"
    migration = Migration(route, clean_db)
    si = migration.external_domain_broker_service_instance
    cloudfront.assert_no_pending_responses()
    assert si.forward_cookie_policy == "all"
    assert si.forwarded_cookies == []
