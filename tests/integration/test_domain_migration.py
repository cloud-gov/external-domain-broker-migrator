import datetime
from unittest.mock import call

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
def domain_migration(clean_db, fake_cf_client, domain_route, mocker):
    return subtest_migration_instantiable(
        clean_db, fake_cf_client, domain_route, mocker
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


def subtest_migration_instantiable(clean_db, fake_cf_client, domain_route, mocker):
    get_instance_mock = mocker.patch(
        "migrator.migration.cf.get_instance_data",
        return_value=dict(entity=dict(name="my-old-domain")),
    )
    migration = DomainMigration(domain_route, clean_db, fake_cf_client)
    get_instance_mock.assert_called_once_with("asdf-asdf", fake_cf_client)
    return migration


def test_domain_migration_migrates(
    clean_db, fake_cf_client, fake_requests, domain_route, mocker
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
        clean_db, fake_cf_client, domain_route, mocker
    )

    assert migration.external_domain_broker_service_instance is None

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

    enable_plan_mock = mocker.patch("migrator.migration.cf.enable_plan_for_org")

    create_mock = mocker.patch(
        "migrator.migration.cf.create_bare_migrator_service_instance_in_space",
        return_value="my-job",
    )
    wait_mock = mocker.patch(
        "migrator.migration.cf.wait_for_service_instance_ready",
        return_value="my-instance-id",
    )

    # these two functions are called more than once. The way mocking works means we define them once then check their calls later
    update_service_instance_mock = mocker.patch(
        "migrator.migration.cf.update_existing_cdn_domain_service_instance",
        return_value="my-second-job"
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
        "migrating-instance-my-old-domain",
        ["www0.example.gov", "www1.example.gov"],
        fake_cf_client,
    )

    # wait for service instance
    wait_mock.assert_has_calls([call("my-job", fake_cf_client),call("my-second-job", fake_cf_client)])

    # update service instance
    update_service_instance_mock.assert_has_calls(
        [
            # update instance type
            call(
                "my-instance-id",
                {
                    "iam_server_certificate_name": "my-cert-name",
                    "iam_server_certificate_id": "my-cert-id",
                    "iam_server_certificate_arn": "my-cert-arn",
                    "alb_arn": "arn:123",
                    "alb_listener_arn": "arn:234",
                    "domain_internal": "foo.example.com",
                    "hosted_zone_id": "FAKEZONEIDFORALBS",
                },
                fake_cf_client,
                new_plan_guid="FAKE-DOMAIN-PLAN-GUID",
            ),
            # rename instance
            call(
                "my-instance-id", {}, fake_cf_client, new_instance_name="my-old-domain"
            ),
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
