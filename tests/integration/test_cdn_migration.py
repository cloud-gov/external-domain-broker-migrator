import datetime
from unittest.mock import call

import pytest

from migrator.migration import find_active_instances, CdnMigration
from migrator.models import CdnRoute, CdnCertificate


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
    cdn_migration = CdnMigration(route, clean_db, fake_cf_client)

    assert sorted(cdn_migration.domains) == sorted(["example.com", "foo.example.com"])
    assert cdn_migration.instance_id == "asdf-asdf"
    assert cdn_migration.cloudfront_distribution_id == "some-distribution-id"
    assert cdn_migration.instance_name == "my-old-cdn"


def test_migration_loads_cloudfront_config(
    clean_db, cloudfront, fake_cf_client, cdn_migration
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
    cdn_migration.route.dist_id = "sample-distribution-id"
    assert cdn_migration.cloudfront_distribution_data is not None
    cloudfront.assert_no_pending_responses()
    assert cdn_migration.cloudfront_distribution_config is not None
    assert (
        cdn_migration.cloudfront_distribution_arn
        == "arn:aws:cloudfront::000000000000:distribution/sample-distribution-id"
    )
    assert cdn_migration.forward_cookie_policy == "all"
    assert cdn_migration.forwarded_cookies == []
    assert cdn_migration.forwarded_headers == ["HOST"]
    assert cdn_migration.custom_error_responses == {"400": "/errors/400.html"}
    assert cdn_migration.origin_hostname == "cloud.test"
    assert cdn_migration.origin_path == ""
    assert cdn_migration.origin_protocol_policy == "https-only"
    assert cdn_migration.iam_certificate_id == "my-cert-id-0"


def test_migration_loads_cloudfront_config_with_no_error_reponses(
    clean_db, cloudfront, fake_cf_client, cdn_migration
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
    cdn_migration.route.dist_id = "sample-distribution-id"
    assert cdn_migration.cloudfront_distribution_data is not None
    cloudfront.assert_no_pending_responses()
    assert cdn_migration.cloudfront_distribution_config is not None
    assert (
        cdn_migration.cloudfront_distribution_arn
        == "arn:aws:cloudfront::000000000000:distribution/sample-distribution-id"
    )
    assert cdn_migration.forward_cookie_policy == "all"
    assert cdn_migration.forwarded_cookies == []
    assert cdn_migration.forwarded_headers == ["HOST"]
    assert cdn_migration.custom_error_responses == {}
    assert cdn_migration.origin_hostname == "cloud.test"
    assert cdn_migration.origin_path == ""
    assert cdn_migration.origin_protocol_policy == "https-only"


def test_migration_loads_cloudfront_config_with_no_error_reponses(
    clean_db, cloudfront, fake_cf_client, cdn_migration
):
    domains = ["example.gov"]
    cloudfront.expect_get_distribution(
        forwarded_headers=[],
        caller_reference="asdf",
        domains=domains,
        certificate_id="not-used-in-this-test",
        origin_hostname="cloud.test",
        origin_path="",
        distribution_id="sample-distribution-id",
        status="active",
        custom_error_responses={"Quantity": 0},
        skip_empty_items=True,
    )
    cdn_migration.route.dist_id = "sample-distribution-id"
    assert cdn_migration.cloudfront_distribution_data is not None
    cloudfront.assert_no_pending_responses()
    assert cdn_migration.cloudfront_distribution_config is not None
    assert (
        cdn_migration.cloudfront_distribution_arn
        == "arn:aws:cloudfront::000000000000:distribution/sample-distribution-id"
    )
    assert cdn_migration.forward_cookie_policy == "all"
    assert cdn_migration.forwarded_cookies == []
    assert cdn_migration.forwarded_headers == []
    assert cdn_migration.custom_error_responses == {}
    assert cdn_migration.origin_hostname == "cloud.test"
    assert cdn_migration.origin_path == ""
    assert cdn_migration.origin_protocol_policy == "https-only"


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
    assert expected == CdnMigration.parse_cloudfront_error_response(input_)


def test_update_existing_cdn_domain(
    clean_db, fake_cf_client, fake_requests, cdn_migration
):
    def update_instance_matcher(request):
        body = request.json()
        name = body.get("name")
        service_plan_guid = body.get("service_plan_guid")
        params = body.get("parameters", {})
        assert name is None
        assert service_plan_guid == "FAKE-CDN-PLAN-GUID"
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
        assert params["iam_server_certificate_name"] == "my-cert-name-0"
        assert params["iam_server_certificate_id"] == "my-cert-id-0"
        assert params["iam_server_certificate_arn"] == "my-cert-arn-0"
        error_config = params["error_responses"]
        assert error_config.get("500") == "/five-hundred"
        assert error_config.get("404") == "/four-oh-four"

        # the matcher API from requests_mock actually wants us to return False for a failed match
        # and True for a good match. We use assertions instead so the error is meaningful, but we
        # need to return True when we are done anyway
        return True

    cdn_migration._space_id = "my-space-guid"
    cdn_migration._org_id = "my-org-guid"
    cdn_migration.external_domain_broker_service_instance = "my-migrator-instance"
    cdn_migration._cloudfront_distribution_data = {
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

    cdn_migration.update_existing_cdn_domain()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_update_existing_cdn_domain_failure(
    clean_db, fake_cf_client, fake_requests, cdn_migration
):
    cdn_migration.route.dist_id = "some-distribution-id"
    cdn_migration._space_id = "my-space-guid"
    cdn_migration._org_id = "my-org-guid"
    cdn_migration.external_domain_broker_service_instance = "my-migrator-instance"
    cdn_migration._cloudfront_distribution_data = {
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
    cdn_migration._iam_server_certificate_data = {
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
        cdn_migration.update_existing_cdn_domain()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_update_existing_cdn_domain_timeout_failure(
    clean_db, fake_cf_client, fake_requests, cdn_migration
):
    cdn_migration.route.dist_id = "some-distribution-id"
    cdn_migration._space_id = "my-space-guid"
    cdn_migration._org_id = "my-org-guid"
    cdn_migration.external_domain_broker_service_instance = "my-migrator-instance"
    cdn_migration._cloudfront_distribution_data = {
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
    cdn_migration._iam_server_certificate_data = {
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
        cdn_migration.update_existing_cdn_domain()

    assert fake_requests.called
    last_request = fake_requests.request_history[-1]
    assert (
        last_request.url == "http://localhost/v2/service_instances/my-migrator-instance"
    )


def test_migration_migrates_happy_path(
    clean_db, fake_cf_client, route53, cloudfront, dns, mocker
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
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.com"
    certificate0 = CdnCertificate()
    certificate0.route = route
    certificate0.iam_server_certificate_name = "my-cert-name-0"
    certificate0.iam_server_certificate_arn = "my-cert-arn-0"
    certificate0.iam_server_certificate_id = "my-cert-id-0"
    certificate0.expires = datetime.datetime.now() + datetime.timedelta(days=1)

    certificate1 = CdnCertificate()
    certificate1.route = route
    certificate1.iam_server_certificate_name = "my-cert-name-2"
    certificate1.iam_server_certificate_arn = "my-cert-arn-2"
    certificate1.iam_server_certificate_id = "my-cert-id-2"
    certificate1.expires = datetime.datetime.now() - datetime.timedelta(days=1)
    clean_db.add_all([route, certificate0, certificate1])
    clean_db.commit()

    get_name_mock = mocker.patch(
        "migrator.migration.cf.get_instance_data",
        return_value={"entity": {"name": "my-cdn"}},
    )
    migration = CdnMigration(route, clean_db, fake_cf_client)

    get_name_mock.assert_called_once_with("asdf-asdf", fake_cf_client)

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
    enable_plan_mock = mocker.patch("migrator.migration.cf.enable_plan_for_org")

    create_mock = mocker.patch(
        "migrator.migration.cf.create_bare_migrator_service_instance_in_space",
        return_value="my-job",
    )
    wait_mock = mocker.patch(
        "migrator.migration.cf.wait_for_service_instance_ready",
        return_value="my-instance-id",
    )
    update_service_instance_mock = mocker.patch(
        "migrator.migration.cf.update_existing_cdn_domain_service_instance"
    )
    update_instance_wait_mock = mocker.patch(
        "migrator.migration.cf.get_migrator_service_instance_status",
        return_value="succeeded",
    )

    disable_service_mock = mocker.patch("migrator.migration.cf.disable_plan_for_org")

    purge_service_instance_mock = mocker.patch(
        "migrator.migration.cf.purge_service_instance"
    )

    migration.migrate()
    # enable service plan
    enable_plan_mock.assert_called_once_with(
        "FAKE-MIGRATION-PLAN-GUID", "my-org-id", fake_cf_client
    )

    # create service instance
    create_mock.assert_called_once_with(
        "my-space-id",
        "FAKE-MIGRATION-PLAN-GUID",
        "migrating-instance-my-cdn",
        ["example.com", "foo.com"],
        fake_cf_client,
    )

    # wait for service instance
    wait_mock.assert_called_once_with("my-job", fake_cf_client)

    # update service instance
    update_service_instance_mock.assert_has_calls(
        [
            # update instance type
            call(
                "my-instance-id",
                {
                    "cloudfront_distribution_arn": "aws:arn:cloudfront:my-cloudfront-distribution",
                    "cloudfront_distribution_id": None,
                    "domain_internal": None,
                    "error_responses": {
                        "404": "/four-oh-four",
                        "500": "/five-hundred",
                    },
                    "forward_cookie_policy": "whitelist",
                    "forwarded_cookies": [
                        "white-listed-name",
                    ],
                    "forwarded_headers": [
                        "white-listed-name-header",
                    ],
                    "iam_server_certificate_arn": "my-cert-arn-0",
                    "iam_server_certificate_id": "my-cert-id-0",
                    "iam_server_certificate_name": "my-cert-name-0",
                    "insecure_origin": False,
                    "origin": "example.gov",
                    "path": "example.gov",
                },
                fake_cf_client,
                new_plan_guid="FAKE-CDN-PLAN-GUID",
            ),
            # rename instance
            call("my-instance-id", {}, fake_cf_client, new_instance_name="my-cdn"),
        ]
    )

    update_instance_wait_mock.assert_has_calls(
        [
            # wait for instance type change
            call("my-instance-id", fake_cf_client),
            # wait for instance rename
            call("my-instance-id", fake_cf_client),
        ]
    )

    # delete service plan visibility
    disable_service_mock.assert_called_once_with(
        "FAKE-MIGRATION-PLAN-GUID", "my-org-id", fake_cf_client
    )

    # purge old instance
    purge_service_instance_mock.assert_called_once_with("asdf-asdf", fake_cf_client)

    # make sure we're all done
    assert migration.route.state == "migrated"
