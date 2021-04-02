import time

from migrator import cf
from migrator.dns import has_expected_cname
from migrator.db import session_handler
from migrator.extensions import (
    cloudfront,
    config,
    iam_commercial,
    route53,
    migration_plan_guid,
    migration_plan_instance_name,
    migration_instance_check_timeout,
)
from migrator.models import CdnRoute


def find_active_instances(session):
    query = session.query(CdnRoute).filter(CdnRoute.state == "provisioned")
    routes = query.all()
    return routes


class Migration:
    def __init__(self, route: CdnRoute, session, client):
        self.domains = route.domain_external.split(",")
        self.instance_id = route.instance_id
        self.domain_internal = route.domain_internal
        self.cloudfront_distribution_id = route.dist_id
        self._cloudfront_distribution_data = None
        self.session = session
        self.client = client
        self.external_domain_broker_service_instance = None
        self._space_id = None
        self._org_id = None

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

    @property
    def space_id(self):
        if self._space_id is None:
            self._space_id = cf.get_space_id_for_service_instance_id(
                self.instance_id, self.client
            )
        return self._space_id

    @property
    def org_id(self):
        if self._org_id is None:
            self._org_id = cf.get_org_id_for_space_id(self.space_id, self.client)
        return self._org_id

    @property
    def service_plan_visibility_ids(self):
        return cf.get_service_plan_visibility_ids_for_org(
            migration_plan_guid, self.org_id, self.client
        )

    def enable_migration_service_plan(self):
        cf.enable_plan_for_org(migration_plan_guid, self.org_id, self.client)

    def disable_migration_service_plan(self):
        for service_plan_visibility_id in self.service_plan_visibility_ids:
            cf.disable_plan_for_org(service_plan_visibility_id, self.client)

    def create_bare_migrator_instance_in_org_space(self):
        instance_info = cf.create_bare_migrator_service_instance_in_space(
            self.space_id,
            migration_plan_guid,
            migration_plan_instance_name,
            self.client,
        )

        self.external_domain_broker_service_instance = instance_info["guid"]

        retries = config.SERVICE_CHANGE_RETRY_COUNT

        while retries:
            status = cf.get_migrator_service_instance_status(
                self.external_domain_broker_service_instance, self.client
            )

            if status == "succeeded":
                return

            if status == "failed":
                raise Exception("Creation of migrator service instance failed.")
            retries -= 1
            time.sleep(config.SERVICE_CHANGE_POLL_TIME_SECONDS)

        raise Exception("Checking migrator service instance timed out.")

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
