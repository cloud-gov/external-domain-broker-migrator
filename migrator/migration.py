from migrator.dns import has_expected_cname
from migrator.db import session_handler
from migrator.extensions import cloudfront, config, iam_commercial, route53
from migrator.models import CdnRoute, EdbCDNServiceInstance, EdbCertificate


def find_active_instances(session):
    query = session.query(CdnRoute).filter(CdnRoute.state == "provisioned")
    routes = query.all()
    return routes


class Migration:
    def __init__(self, route: CdnRoute, session):
        self.domains = route.domain_external.split(",")
        self.instance_id = route.instance_id
        self.domain_internal = route.domain_internal
        self.cloudfront_distribution_id = route.dist_id
        self._cloudfront_distribution_data = None
        self.session = session
        self._external_domain_broker_service_instance = None

    @property
    def has_valid_dns(self):
        if not self.domains:
            return False
        return all([has_expected_cname(domain) for domain in self.domains])

    @property
    def cloudfront_distribution_data(self):
        if self._cloudfront_distribution_data is None:
            self._cloudfront_distribution_data = cloudfront.get_distribution(
                Id=self.cloudfront_distribution_id
            )["Distribution"]
        return self._cloudfront_distribution_data

    @property
    def cloudfront_distribution_config(self):
        return self.cloudfront_distribution_data["DistributionConfig"]

    @property
    def cloudfront_distribution_arn(self):
        return self.cloudfront_distribution_data["ARN"]

    @property
    def forward_cookie_policy(self):
        return self.cloudfront_distribution_config["DefaultCacheBehavior"][
            "ForwardedValues"
        ]["Cookies"]["Forward"]

    @property
    def forwarded_cookies(self):
        if self.forward_cookie_policy == "whitelist":
            return self.cloudfront_distribution_config["DefaultCacheBehavior"][
                "ForwardedValues"
            ]["Cookies"]["WhitelistedNames"]["Items"]
        else:
            return []

    @property
    def forwarded_headers(self):
        return self.cloudfront_distribution_config["DefaultCacheBehavior"][
            "ForwardedValues"
        ]["Headers"]["Items"]

    @property
    def custom_error_responses(self):
        return Migration.parse_cloudfront_error_response(
            self.cloudfront_distribution_config["CustomErrorResponses"]
        )

    @property
    def origin_hostname(self):
        return self.interesting_origin["DomainName"]

    @property
    def origin_path(self):
        return self.interesting_origin["OriginPath"]

    @property
    def origin_protocol_policy(self):
        return self.interesting_origin["CustomOriginConfig"]["OriginProtocolPolicy"]

    @property
    def interesting_origin(self):
        # this ignores the s3 bucket currently used for Lets Encrypt validation
        # it still makes an assumption that there's only _one_ interesting origin
        # but that's pretty safe, given how the cdn-broker works
        for origin in self.cloudfront_distribution_config["Origins"]["Items"]:
            if origin.get("S3OriginConfig") is None:
                return origin

    @property
    def iam_certificate_id(self):
        return self.cloudfront_distribution_config["ViewerCertificate"][
            "IAMCertificateId"
        ]

    def upsert_edb_cdn_instance(self):
        si = (
            self.session.query(EdbCDNServiceInstance)
            .filter_by(id=self.instance_id)
            .first()
        )
        if si is None:
            si = EdbCDNServiceInstance()
        self._external_domain_broker_service_instance = si
        si.id = self.instance_id
        si.domain_names = self.domains
        si.domain_internal = self.domain_internal
        si.origin_protocol_policy = self.origin_protocol_policy
        si.cloudfront_distribution_arn = self.cloudfront_distribution_arn
        si.cloudfront_origin_hostname = self.origin_hostname
        si.cloudfront_origin_path = self.origin_path
        si.error_responses = self.custom_error_responses
        si.forwarded_headers = self.forwarded_headers
        si.forward_cookie_policy = self.forward_cookie_policy
        si.forwarded_cookies = self.forwarded_cookies
        self.external_domain_broker_service_instance = si
        return si

    def upsert_edb_certificate(self):
        cert_response = {"IsTruncated": True}
        server_certificate = None
        while cert_response["IsTruncated"] and not server_certificate:
            kwargs = {}
            if cert_response.get("Marker"):
                kwargs["Marker"] = cert_response["Marker"]
            cert_response = iam_commercial.list_server_certificates(**kwargs)
            for cert in cert_response["ServerCertificateMetadataList"]:
                if cert["ServerCertificateId"] == self.iam_certificate_id:
                    server_certificate = cert
        edb_certificate = EdbCertificate()
        edb_certificate.expires_at = server_certificate["Expiration"]
        edb_certificate.iam_server_certificate_arn = server_certificate["Arn"]
        edb_certificate.iam_server_certificate_name = server_certificate[
            "ServerCertificateName"
        ]
        edb_certificate.iam_server_certificate_id = server_certificate[
            "ServerCertificateId"
        ]
        edb_certificate.service_instance_id = self.instance_id
        self.external_domain_broker_service_instance.current_certificate = (
            edb_certificate
        )
        self.session.add(self.external_domain_broker_service_instance)
        self.session.add(edb_certificate)
        self.session.commit()
        return edb_certificate

    def upsert_dns(self):
        change_ids = []
        for domain in self.domains:
            alias_record = f"{domain}.{config.DNS_ROOT_DOMAIN}"
            target = self.domain_internal
            route53_response = route53.change_resource_record_sets(
                ChangeBatch={
                    "Changes": [
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Type": "A",
                                "Name": alias_record,
                                "AliasTarget": {
                                    "DNSName": target,
                                    "HostedZoneId": config.CLOUDFRONT_HOSTED_ZONE_ID,
                                    "EvaluateTargetHealth": False,
                                },
                            },
                        },
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Type": "AAAA",
                                "Name": alias_record,
                                "AliasTarget": {
                                    "DNSName": target,
                                    "HostedZoneId": config.CLOUDFRONT_HOSTED_ZONE_ID,
                                    "EvaluateTargetHealth": False,
                                },
                            },
                        },
                    ]
                },
                HostedZoneId=config.ROUTE53_ZONE_ID,
            )
            change_ids.append(route53_response["ChangeInfo"]["Id"])
        for change_id in change_ids:
            waiter = route53.get_waiter("resource_record_sets_changed")
            waiter.wait(
                Id=change_id,
                WaiterConfig={
                    "Delay": config.AWS_POLL_WAIT_TIME_IN_SECONDS,
                    "MaxAttempts": config.AWS_POLL_MAX_ATTEMPTS,
                },
            )

    @staticmethod
    def parse_cloudfront_error_response(error_responses):
        responses = {}
        for item in error_responses.get("Items", []):
            responses[item["ResponseCode"]] = item["ResponsePagePath"]
        return responses
