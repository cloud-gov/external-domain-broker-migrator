from datetime import datetime
from typing import Any, Dict, List

import pytest

from migrator.extensions import cloudfront as real_cloudfront
from tests.lib.fake_aws import FakeAWS


class FakeCloudFront(FakeAWS):
    def expect_get_distribution_config(
        self,
        caller_reference: str,
        domains: List[str],
        certificate_id: str,
        origin_hostname: str,
        origin_path: str,
        distribution_id: str,
        forward_cookie_policy: str = "all",
        forwarded_cookies: list = None,
        forwarded_headers: list = None,
        origin_protocol_policy: str = "https-only",
        bucket_prefix: str = "",
        custom_error_responses: str = None,
        skip_empty_items: bool = False,
    ):
        if custom_error_responses is None:
            custom_error_responses = {"Quantity": 0}
        if forwarded_headers is None:
            forwarded_headers = ["HOST"]
        self.etag = str(datetime.now().timestamp())
        self.stubber.add_response(
            "get_distribution_config",
            {
                "DistributionConfig": distribution_config(
                    caller_reference,
                    domains,
                    certificate_id,
                    origin_hostname,
                    origin_path,
                    forward_cookie_policy=forward_cookie_policy,
                    forwarded_cookies=forwarded_cookies,
                    forwarded_headers=forwarded_headers,
                    origin_protocol_policy=origin_protocol_policy,
                    bucket_prefix=bucket_prefix,
                    custom_error_responses=custom_error_responses,
                    skip_empty_items=skip_empty_items,
                ),
                "ETag": self.etag,
            },
            {"Id": distribution_id},
        )

    def expect_get_distribution_config_returning_no_such_distribution(
        self, distribution_id: str
    ):
        self.stubber.add_client_error(
            "get_distribution_config",
            service_error_code="NoSuchDistribution",
            service_message="'Ain't there.",
            http_status_code=404,
            expected_params={"Id": distribution_id},
        )

    def expect_get_distribution(
        self,
        caller_reference: str,
        domains: List[str],
        certificate_id: str,
        origin_hostname: str,
        origin_path: str,
        distribution_id: str,
        status: str,
        enabled: bool = True,
        forward_cookie_policy: str = "all",
        forwarded_cookies: list = None,
        forwarded_headers: list = None,
        origin_protocol_policy: str = "https-only",
        bucket_prefix: str = "",
        custom_error_responses: dict = None,
        skip_empty_items: bool = False,
    ):
        if custom_error_responses is None:
            custom_error_responses = {"Quantity": 0}
        if forwarded_headers is None:
            forwarded_headers = ["HOST"]
        self.etag = str(datetime.now().timestamp())
        distribution = distribution_response(
            caller_reference,
            domains,
            certificate_id,
            origin_hostname,
            origin_path,
            distribution_id,
            "ignored",
            status,
            enabled,
            forward_cookie_policy=forward_cookie_policy,
            forwarded_cookies=forwarded_cookies,
            forwarded_headers=forwarded_headers,
            origin_protocol_policy=origin_protocol_policy,
            bucket_prefix=bucket_prefix,
            custom_error_responses=custom_error_responses,
            skip_empty_items=skip_empty_items,
        )
        distribution["ETag"] = self.etag
        self.stubber.add_response(
            "get_distribution", distribution, {"Id": distribution_id}
        )


def distribution_config(
    caller_reference: str,
    domains: List[str],
    iam_server_certificate_id: str,
    origin_hostname: str,
    origin_path: str,
    enabled: bool = True,
    forward_cookie_policy: str = "all",
    forwarded_cookies: list = None,
    forwarded_headers: list = None,
    origin_protocol_policy: str = "https-only",
    bucket_prefix: str = "",
    custom_error_responses: dict = None,
    skip_empty_items: bool = False,
) -> Dict[str, Any]:
    if forwarded_headers is None:
        forwarded_headers = ["HOST"]
    cookies = {"Forward": forward_cookie_policy}
    if forward_cookie_policy == "whitelist":
        cookies["WhitelistedNames"] = {
            "Quantity": len(forwarded_cookies),
            "Items": forwarded_cookies,
        }
    headers = {
        "Quantity": len(forwarded_headers),
    }
    if forwarded_headers or not skip_empty_items:
        headers["Items"] = forwarded_headers
    return {
        "CallerReference": caller_reference,
        "Aliases": {"Quantity": len(domains), "Items": domains},
        "DefaultRootObject": "",
        "Origins": {
            "Quantity": 1,
            "Items": [
                {
                    "Id": "s3-cdn-broker-le-verify",
                    "DomainName": "doesnt-matter.s3.amazonaws.com",
                    "OriginPath": "",
                    "CustomHeaders": {"Quantity": 0},
                    "S3OriginConfig": {"OriginAccessIdentity": ""},
                },
                {
                    "Id": "default-origin",
                    "DomainName": origin_hostname,
                    "OriginPath": origin_path,
                    "CustomOriginConfig": {
                        "HTTPPort": 80,
                        "HTTPSPort": 443,
                        "OriginProtocolPolicy": origin_protocol_policy,
                        "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                        "OriginReadTimeout": 30,
                        "OriginKeepaliveTimeout": 5,
                    },
                },
            ],
        },
        "OriginGroups": {"Quantity": 0},
        "DefaultCacheBehavior": {
            "TargetOriginId": "default-origin",
            "ForwardedValues": {
                "QueryString": True,
                "Cookies": cookies,
                "Headers": headers,
                "QueryStringCacheKeys": {"Quantity": 0},
            },
            "TrustedSigners": {"Enabled": False, "Quantity": 0},
            "ViewerProtocolPolicy": "redirect-to-https",
            "MinTTL": 0,
            "AllowedMethods": {
                "Quantity": 7,
                "Items": ["GET", "HEAD", "POST", "PUT", "PATCH", "OPTIONS", "DELETE"],
                "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
            },
            "SmoothStreaming": False,
            "DefaultTTL": 86400,
            "MaxTTL": 31536000,
            "Compress": False,
            "LambdaFunctionAssociations": {"Quantity": 0},
        },
        "CacheBehaviors": {"Quantity": 0},
        "CustomErrorResponses": custom_error_responses,
        "Comment": "external domain service https://cloud-gov/external-domain-broker",
        "Logging": {
            "Enabled": True,
            "IncludeCookies": False,
            "Bucket": "mybucket.s3.amazonaws.com",
            "Prefix": bucket_prefix,
        },
        "PriceClass": "PriceClass_100",
        "Enabled": enabled,
        "ViewerCertificate": {
            "CloudFrontDefaultCertificate": False,
            "IAMCertificateId": iam_server_certificate_id,
            "SSLSupportMethod": "sni-only",
            "MinimumProtocolVersion": "TLSv1.2_2018",
        },
        "IsIPV6Enabled": True,
    }


def distribution_response(
    caller_reference: str,
    domains: List[str],
    iam_server_certificate_id: str,
    origin_hostname: str,
    origin_path: str,
    distribution_id: str,
    distribution_hostname: str,
    status: str = "InProgress",
    enabled: bool = True,
    forward_cookie_policy: str = "all",
    forwarded_cookies: list = None,
    forwarded_headers: list = None,
    origin_protocol_policy: str = "https-only",
    bucket_prefix: str = "",
    custom_error_responses: dict = None,
    skip_empty_items: bool = False,
) -> Dict[str, Any]:
    if forwarded_headers is None:
        forwarded_headers = ["HOST"]
    cookies = {"Forward": forward_cookie_policy}
    if forward_cookie_policy == "whitelist":
        cookies["WhitelistedNames"] = {
            "Quantity": len(forwarded_cookies),
            "Items": forwarded_cookies,
        }
    return {
        "Distribution": {
            "Id": distribution_id,
            "ARN": f"arn:aws:cloudfront::000000000000:distribution/{distribution_id}",
            "Status": status,
            "LastModifiedTime": datetime.utcnow(),
            "InProgressInvalidationBatches": 0,
            "DomainName": distribution_hostname,
            "ActiveTrustedSigners": {"Enabled": False, "Quantity": 0, "Items": []},
            "DistributionConfig": distribution_config(
                caller_reference,
                domains,
                iam_server_certificate_id,
                origin_hostname,
                origin_path,
                enabled,
                forward_cookie_policy,
                forwarded_cookies,
                forwarded_headers,
                origin_protocol_policy,
                bucket_prefix,
                custom_error_responses,
                skip_empty_items,
            ),
        }
    }


@pytest.fixture(autouse=True)
def cloudfront():
    with FakeCloudFront.stubbing(real_cloudfront) as cloudfront_stubber:
        yield cloudfront_stubber
