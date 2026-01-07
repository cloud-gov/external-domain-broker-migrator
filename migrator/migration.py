import time

from cloudfoundry_client.errors import InvalidStatusCode
from cloudfoundry_client.v3.jobs import JobTimeout
from sqlalchemy import or_

from migrator import cf, logger
from migrator.dns import has_expected_cname
from migrator.extensions import (
    cloudfront,
    config,
    route53,
)
from migrator.models import CdnRoute, DomainRoute
from migrator.smtp import send_email


def find_active_instances(session):
    cdn_routes = find_active_cdn_instances(session)
    domain_routes = find_active_domain_instances(session)
    routes = [*cdn_routes, *domain_routes]
    return routes


def find_active_cdn_instances(session):
    cdn_query = session.query(CdnRoute).filter(
        or_(CdnRoute.state == "provisioned", CdnRoute.state == "migration_failed")
    )
    cdn_routes = cdn_query.all()
    return cdn_routes


def find_active_domain_instances(session):
    domain_query = session.query(DomainRoute).filter(
        or_(DomainRoute.state == "provisioned", DomainRoute.state == "migration_failed")
    )
    domain_routes = domain_query.all()
    return domain_routes


def migration_for_route(route, session, client):
    if isinstance(route, CdnRoute):
        return CdnMigration(route, session, client)
    return DomainMigration(route, session, client)


def migration_for_instance_id(instance_id, session, client):
    instances = find_active_instances(session)
    filtered = filter(lambda x: x.instance_id == instance_id, instances)
    instance = list(filtered)[0]
    return migration_for_route(instance, session, client)


def find_migrations(session, client):
    migrations = []
    for route in find_active_instances(session):
        try:
            migration = migration_for_route(route, session, client)
            migrations.append(migration)
        except InvalidStatusCode as e:
            logger.exception("error getting migration", exc_info=e)
            route.state = "migration_failed"
            session.commit()
    return migrations


def migrate_ready_instances(session, client):
    results = dict(migrated=[], skipped=[], failed=[])
    for migration in find_migrations(session, client):
        if migration.has_valid_dns():
            try:
                migration.migrate()
            except Exception as e:
                # todo: drop print when we add global handling
                print(e)
                if migration.route:
                    migration.route.state = "migration_failed"
                    session.commit()
                results["failed"].append(migration.route.instance_id)
            else:
                results["migrated"].append(migration.route.instance_id)
        else:
            results["skipped"].append(migration.route.instance_id)
    return results


def migrate_single_instance(
    instance_id, session, client, skip_dns_check=False, skip_site_dns_check=False
):
    migration = migration_for_instance_id(instance_id, session, client)
    if skip_dns_check or migration.has_valid_dns(skip_site_dns_check):
        try:
            migration.migrate()
        except Exception as e:
            # todo: drop print when we add global handling
            print(e)
            migration.route.state = "migration_failed"
            session.commit()
        else:
            logger.info("migrated instance %s successfully!", instance_id)


class Migration:
    def __init__(self, route, session, client):
        self.instance_id = route.instance_id
        self.route = route
        self.session = session
        self.client = client
        self._space_id = None
        self._org_id = None
        self._iam_server_certificate_data = None
        self.external_domain_broker_service_instance_guid = None
        self.domains = []

        # get this early so we're sure we have it before we purge the instance
        self.instance_name = self.get_instance_name()

    def get_instance_name(self):
        instance_data = cf.get_instance_data(self.instance_id, self.client)
        return instance_data["name"]

    def has_valid_dns(self, skip_site_dns_check=False):
        logger.debug("validating DNS for %s", self.instance_id)
        if not self.domains:
            return False
        return all(
            [has_expected_cname(domain, skip_site_dns_check) for domain in self.domains]
        )

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

    def enable_migration_service_plan(self):
        cf.enable_plan_for_org(config.MIGRATION_PLAN_ID, self.org_id, self.client)

    def disable_migration_service_plan(self):
        cf.disable_plan_for_org(config.MIGRATION_PLAN_ID, self.org_id, self.client)

    def create_bare_migrator_instance_in_org_space(self):
        logger.debug(
            "creating bare migration instance for migrating legacy service %s",
            self.instance_id,
        )
        job_id = cf.create_bare_migrator_service_instance_in_space(
            self.space_id,
            config.MIGRATION_PLAN_ID,
            f"migrating-instance-{self.instance_name}",
            self.domains,
            self.client,
        )

        guid = self.wait_for_instance_create(job_id)
        logger.debug(
            "created bare migration instance with GUID %s for migrating legacy service %s",
            guid,
            self.instance_id,
        )
        self.external_domain_broker_service_instance_guid = guid
        return guid

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
                self.external_domain_broker_service_instance_guid, self.client
            )

            if status == "succeeded":
                return

            if status == "failed":
                raise Exception("Creation of migrator service instance failed.")

            retries -= 1
            time.sleep(config.SERVICE_CHANGE_POLL_TIME_SECONDS)

        raise Exception("Checking migrator service instance timed out.")

    def wait_for_instance_update(self, job_id):
        try:
            return cf.wait_for_job_complete(job_id, self.client)
        except JobTimeout as e:
            raise Exception("Checking migrator service instance timed out.") from e

    def wait_for_instance_create(self, job_id):
        try:
            return cf.wait_for_service_instance_create(job_id, self.client)
        except JobTimeout as e:
            raise Exception("Checking migrator service instance timed out.") from e

    def purge_old_instance(self):
        cf.purge_service_instance(self.route.instance_id, self.client)

    def update_instance_name(self):
        if not self.external_domain_broker_service_instance_guid:
            raise Exception(
                "Missing value for the external domain broker service instance GUID"
            )

        job_id = cf.update_existing_cdn_domain_service_instance(
            self.external_domain_broker_service_instance_guid,
            {},
            self.client,
            new_instance_name=self.instance_name,
        )

        if job_id:
            return self.wait_for_instance_update(job_id)

    def mark_complete(self):
        self.route.state = "migrated"
        self.session.commit()

    def _migrate(self):
        pass

    def migrate(self):
        try:
            self._migrate()
        except Exception as e:
            if config.ENV not in {"unit", "local"}:
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


class CdnMigration(Migration):
    def __init__(self, route, session, client):
        super().__init__(route, session, client)
        self.cloudfront_distribution_id = route.dist_id
        self._cloudfront_distribution_data = None
        self.domain_internal = route.domain_internal
        self.external_domain_broker_service_instance_guid = None
        self.hosted_zone_id = config.CLOUDFRONT_HOSTED_ZONE_ID
        self.domains = route.domain_external.split(",")

    @property
    def current_certificate(self):
        return self.route.certificates[0]

    @property
    def iam_certificate_id(self):
        return self.current_certificate.iam_server_certificate_id

    @property
    def iam_certificate_arn(self):
        return self.current_certificate.iam_server_certificate_arn

    @property
    def iam_certificate_name(self):
        return self.current_certificate.iam_server_certificate_name

    @property
    def cloudfront_distribution_data(self):
        if self._cloudfront_distribution_data is None:
            logger.debug("getting cloudfront data for %s", self.instance_id)
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
        ]["Headers"].get("Items", [])

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

        logger.debug(
            "updating bare migrator instance with guid %s to new CDN service for legacy service %s",
            self.external_domain_broker_service_instance_guid,
            self.instance_id,
        )

        # Update instance from
        job_id = cf.update_existing_cdn_domain_service_instance(
            self.external_domain_broker_service_instance_guid,
            params,
            self.client,
            new_plan_guid=config.CDN_PLAN_ID,
        )

        if job_id:
            self.wait_for_instance_update(job_id)

    def remove_old_instance_cdn_reference(self):
        self.route.dist_id = None
        self.session.commit()
        pass

    def _migrate(self):
        self.enable_migration_service_plan()
        self.create_bare_migrator_instance_in_org_space()
        self.update_existing_cdn_domain()
        self.disable_migration_service_plan()
        self.remove_old_instance_cdn_reference()
        self.purge_old_instance()
        self.update_instance_name()
        self.mark_complete()

    def __repr__(self):
        return f"<instance_name={self.instance_name}, route={self.route.instance_id}, domains={self.route.domain_external}, domain_instance={self.external_domain_broker_service_instance_guid}, space_id={self._space_id}, org_id={self._org_id}>"

    @staticmethod
    def parse_cloudfront_error_response(error_responses):
        responses = {}
        for item in error_responses.get("Items", []):
            responses[item["ResponseCode"]] = item["ResponsePagePath"]
        return responses


class DomainMigration(Migration):
    def __init__(self, route, session, client):
        super().__init__(route, session, client)
        self.domains = route.domains

    @property
    def current_certificate(self):
        return self.route.certificates[0]

    @property
    def iam_certificate_id(self):
        return self.current_certificate.iam_server_certificate_id

    @property
    def iam_certificate_arn(self):
        return self.current_certificate.iam_server_certificate_arn

    @property
    def iam_certificate_name(self):
        return self.current_certificate.iam_server_certificate_name

    def update_migration_instance_to_alb_plan(self):
        logger.debug("updating bare instance for %s", self.instance_id)
        params = {
            "iam_server_certificate_name": self.iam_certificate_name,
            "iam_server_certificate_id": self.iam_certificate_id,
            "iam_server_certificate_arn": self.iam_certificate_arn,
            "alb_arn": self.route.alb_proxy.alb_arn,
            "alb_listener_arn": self.route.alb_proxy.listener_arn,
            "domain_internal": self.route.alb_proxy.alb_dns_name,
            "hosted_zone_id": config.ALB_HOSTED_ZONE_ID,
        }

        job_id = cf.update_existing_cdn_domain_service_instance(
            self.external_domain_broker_service_instance_guid,
            params,
            self.client,
            new_plan_guid=config.DOMAIN_PLAN_ID,
        )

        self.wait_for_instance_update(job_id)

    def _migrate(self):
        self.enable_migration_service_plan()
        self.create_bare_migrator_instance_in_org_space()
        self.update_migration_instance_to_alb_plan()
        self.disable_migration_service_plan()
        self.purge_old_instance()
        self.update_instance_name()
        self.mark_complete()

    def __repr__(self):
        return f"<instance_name={self.instance_name}, route={self.route.instance_id}, domains={self.route.domains}, domain_instance={self.external_domain_broker_service_instance_guid}, space_id={self._space_id}, org_id={self._org_id}>"
