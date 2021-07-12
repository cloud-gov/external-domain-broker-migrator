import logging
import time

from migrator import cf
from migrator.db import session_handler
from migrator.dns import has_expected_cname
from migrator.extensions import (
    cloudfront,
    config,
    iam_commercial,
    route53,
    migration_plan_guid,
    migration_plan_instance_name,
    domain_with_cdn_plan_guid,
)
from migrator.models import CdnRoute, DomainRoute
from migrator.smtp import send_email

logger = logging.getLogger(__name__)


def find_active_instances(session):
    cdn_query = session.query(CdnRoute).filter(CdnRoute.state == "provisioned")
    cdn_routes = cdn_query.all()
    domain_query = session.query(DomainRoute).filter(DomainRoute.state == "provisioned")
    domain_routes = domain_query.all()
    return (*cdn_routes, *domain_routes)


def migration_for_route(route, session, client):
    if isinstance(route, CdnRoute):
        return CdnMigration(route, session, client)
    return DomainMigration(route, session, client)


def migrate_ready_instances(session, client):
    results = dict(migrated=[], skipped=[], failed=[])
    for route in find_active_instances(session):
        if route.has_valid_dns():
            try:
                migration = migration_for_route(route, session, client)
                migration.migrate()
            except Exception as e:
                # todo: drop print when we add global handling
                print(e)
                route.state = "migration_failed"
                session.commit()
                results["failed"].append(route.instance_id)
            else:
                results["migrated"].append(route.instance_id)
        else:
            results["skipped"].append(route.instance_id)
    return results


class Migration:
    def __init__(self, route, session, client):
        self.instance_id = route.instance_id
        self.domain_internal = route.domain_internal
        self.route = route
        self.session = session
        self.client = client
        self._space_id = None
        self._org_id = None
        self._iam_server_certificate_data = None

        # get this early so we're sure we have it before we purge the instance
        self.instance_name = self.get_instance_name()

    def get_instance_name(self):
        instance_data = cf.get_instance_data(self.instance_id, self.client)
        return instance_data["entity"]["name"]

    @property
    def has_valid_dns(self):
        logger.debug("validating DNS for %s", self.instance_id)
        if not self.domains:
            return False
        return all([has_expected_cname(domain) for domain in self.domains])

    @property
    def iam_certificate_id(self):
        return self.cloudfront_distribution_config["ViewerCertificate"][
            "IAMCertificateId"
        ]

    @property
    def iam_certificate_name(self):
        return self.iam_server_certificate_data["ServerCertificateName"]

    @property
    def iam_certificate_arn(self):
        return self.iam_server_certificate_data["Arn"]

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
        logger.debug("creating bare instance for %s", self.instance_id)
        instance_info = cf.create_bare_migrator_service_instance_in_space(
            self.space_id,
            migration_plan_guid,
            migration_plan_instance_name,
            self.client,
        )

        self.external_domain_broker_service_instance = instance_info["guid"]

        self.check_instance_status()

    def upsert_dns(self):
        logger.debug("upserting DNS for %s", self.instance_id)
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
                                    "HostedZoneId": self.hosted_zone_id,
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
                                    "HostedZoneId": self.hosted_zone_id,
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

    def check_instance_status(self):
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

    def check_instance_status(self):
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

    def purge_old_instance(self):
        cf.purge_service_instance(self.route.instance_id, self.client)

    def update_instance_name(self):
        cf.update_existing_cdn_domain_service_instance(
            self.external_domain_broker_service_instance,
            {},
            self.client,
            new_instance_name=self.instance_name,
        )
        self.check_instance_status()

    def mark_complete(self):
        self.route.state = "migrated"
        self.session.commit()


class CdnMigration(Migration):
    def __init__(self, route, session, client):
        self.cloudfront_distribution_id = route.dist_id
        self._cloudfront_distribution_data = None
        self.external_domain_broker_service_instance = None
        self.hosted_zone_id = config.CLOUDFRONT_HOSTED_ZONE_ID
        self.domains = route.domain_external.split(",")
        super().__init__(route, session, client)

    @property
    def cloudfront_distribution_data(self):
        if self._cloudfront_distribution_data is None:
            logger.debug("getting cloudfront data for %s", self.instance_id)
            self._cloudfront_distribution_data = cloudfront.get_distribution(
                Id=self.cloudfront_distribution_id
            )["Distribution"]
        return self._cloudfront_distribution_data

    @property
    def iam_server_certificate_data(self):
        logger.debug("getting iam server certificate data for %s", self.instance_id)
        if self._iam_server_certificate_data is None:
            server_certificate_metadata_list = {}
            is_truncated = True

            while is_truncated:
                logger.debug(
                    "getting next page of server certificates %s", self.instance_id
                )
                if server_certificate_metadata_list.get("Marker") is not None:
                    kwargs = {"Marker": server_certificate_metadata_list.get("Marker")}
                else:
                    kwargs = {}

                server_certificate_metadata_list = iam_commercial.list_server_certificates(
                    **kwargs
                )
                is_truncated = server_certificate_metadata_list["IsTruncated"]

                for server_certificate in server_certificate_metadata_list[
                    "ServerCertificateMetadataList"
                ]:
                    if (
                        server_certificate["ServerCertificateId"]
                        == self.iam_certificate_id
                    ):
                        self._iam_server_certificate_data = server_certificate
                        return self._iam_server_certificate_data

        return self._iam_server_certificate_data

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
        return CdnMigration.parse_cloudfront_error_response(
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
    def insecure_origin(self):
        if self.origin_protocol_policy == "http-only":
            return True

        return False

    @property
    def interesting_origin(self):
        # this ignores the s3 bucket currently used for Lets Encrypt validation
        # it still makes an assumption that there's only _one_ interesting origin
        # but that's pretty safe, given how the cdn-broker works
        for origin in self.cloudfront_distribution_config["Origins"]["Items"]:
            if origin.get("S3OriginConfig") is None:
                return origin

    def update_existing_cdn_domain(self):
        logger.debug("updating bare instance for %s", self.instance_id)
        params = {
            "origin": self.origin_hostname,
            "path": self.origin_path,
            "forwarded_cookies": self.forwarded_cookies,
            "forward_cookie_policy": self.forward_cookie_policy,
            "forwarded_headers": self.forwarded_headers,
            "insecure_origin": self.insecure_origin,
            "error_responses": self.custom_error_responses,
            "cloudfront_distribution_id": self.cloudfront_distribution_id,
            "cloudfront_distribution_arn": self.cloudfront_distribution_arn,
            "iam_server_certificate_name": self.iam_certificate_name,
            "iam_server_certificate_id": self.iam_certificate_id,
            "iam_server_certificate_arn": self.iam_certificate_arn,
            "domain_internal": self.domain_internal,
        }

        cf.update_existing_cdn_domain_service_instance(
            self.external_domain_broker_service_instance,
            params,
            self.client,
            new_plan_guid=domain_with_cdn_plan_guid,
        )

        self.check_instance_status()

    def migrate(self):
        try:
            self.enable_migration_service_plan()
            self.create_bare_migrator_instance_in_org_space()
            self.update_existing_cdn_domain()
            self.disable_migration_service_plan()
            self.purge_old_instance()
            self.update_instance_name()
            self.mark_complete()
        except Exception as e:
            self.send_failed_operation_alert(e)
            # the goal here is to try to make it easier to find the logs in Kibana
            # since we can't just email ourselves the stack trace
            logger.exception("failed migrating %s", repr(self))
            raise

    def send_failed_operation_alert(self, exception):
        subject = f"[{config.ENV}] - external-domain-broker-migrator migration failed"
        body = f"""
<h1>Migration failed unexpectedly!</h1>

migration: {repr(self)}
        """
        send_email(config.SMTP_TO, subject, body)

    def __repr__(self):
        return f"<instance_name={self.instance_name}, route={self.route.instance_id}, domains={self.route.domain_external}, domain_instance={self.external_domain_broker_service_instance}, space_id={self._space_id}, org_id={self._org_id}>"

    @staticmethod
    def parse_cloudfront_error_response(error_responses):
        responses = {}
        for item in error_responses.get("Items", []):
            responses[item["ResponseCode"]] = item["ResponsePagePath"]
        return responses


class DomainMigration(Migration):
    def __init__(self, route, session, client):
        self.domains = route.domains
        super().__init__(route, session, client)
