from enum import Enum

import sqlalchemy as sa
from sqlalchemy.ext import declarative
from sqlalchemy.dialects import postgresql
from sqlalchemy import orm
from sqlalchemy_utils.types.encrypted.encrypted_type import (
    AesGcmEngine,
    StringEncryptedType,
)

from migrator.extensions import config

CdnBase = declarative.declarative_base()
ExternalDomainBase = declarative.declarative_base()


def db_encryption_key():
    return config.DATABASE_ENCRYPTION_KEY


class CdnUserData(CdnBase):
    """
    CdnUserData is about the Let's Encrypt user associated with a CdnRoute.
    We probably have no reason to ever think about this model in this project.
    """

    __tablename__ = "user_data"

    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(postgresql.TIMESTAMP)
    updated_at = sa.Column(postgresql.TIMESTAMP)
    deleted_at = sa.Column(postgresql.TIMESTAMP)
    email = sa.Column(sa.Text, nullable=False)
    reg = sa.Column(postgresql.BYTEA)
    key = sa.Column(postgresql.BYTEA)


class CdnRoute(CdnBase):
    """
    CdnRoute represents the core of the service instance
    """

    __tablename__ = "routes"

    id = sa.Column(sa.Integer, primary_key=True)
    # domain_internal is effectively the domain name of the CloudFront distribution
    domain_internal = sa.Column(sa.Text)
    # domain_external is a comma-separated list of domain names the user wants the CloudFront distribution to respond to
    domain_external = sa.Column(sa.Text)
    created_at = sa.Column(postgresql.TIMESTAMP)
    updated_at = sa.Column(postgresql.TIMESTAMP)
    deleted_at = sa.Column(postgresql.TIMESTAMP)
    instance_id = sa.Column(sa.Text)
    dist_id = sa.Column(sa.Text)
    origin = sa.Column(sa.Text)
    path = sa.Column(sa.Text)
    insecure_origin = sa.Column(sa.Boolean)
    challenge_json = sa.Column(postgresql.BYTEA)
    user_data_id = sa.Column(sa.Integer, sa.ForeignKey(CdnUserData.id))
    user_data = orm.relationship(CdnUserData)
    certificates = orm.relationship("CdnCertificate")
    # state should be one of:
    # deprovisioned
    # provisioning
    # provisioned
    state = sa.Column(sa.Text)


class CdnCertificate(CdnBase):
    __tablename__ = "certificates"

    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(postgresql.TIMESTAMP)
    updated_at = sa.Column(postgresql.TIMESTAMP)
    deleted_at = sa.Column(postgresql.TIMESTAMP)
    route_id = sa.Column(sa.Integer, sa.ForeignKey(CdnRoute.id))
    route = orm.relationship(CdnRoute, back_populates="certificates")
    domain = sa.Column(sa.Text)
    # cert_url is the Let's Encrypt URL for the certificate
    cert_url = sa.Column(sa.Text)
    # certificate is the actual body of the certificate chain
    certificate = sa.Column(postgresql.BYTEA)
    expires = sa.Column(postgresql.TIMESTAMP)


class EdbBase(ExternalDomainBase):
    __abstract__ = True

    created_at = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    updated_at = sa.Column(sa.TIMESTAMP(timezone=True), onupdate=sa.func.now())


class EdbACMEUser(EdbBase):
    __tablename__ = "acme_user"

    id = sa.Column(sa.Integer, primary_key=True)
    email = sa.Column(sa.String, nullable=False)
    uri = sa.Column(sa.String, nullable=False)
    private_key_pem = sa.Column(
        StringEncryptedType(sa.Text, db_encryption_key, AesGcmEngine, "pkcs5"),
        nullable=False,
    )

    registration_json = sa.Column(sa.Text)
    service_instances = orm.relationship(
        "EdbServiceInstance", backref="acme_user", lazy="dynamic"
    )


class EdbCertificate(EdbBase):
    __tablename__ = "certificate"
    id = sa.Column(sa.Integer, primary_key=True)
    service_instance_id = sa.Column(
        sa.String, sa.ForeignKey("service_instance.id"), nullable=False
    )
    subject_alternative_names = sa.Column(postgresql.JSONB, default=[])
    leaf_pem = sa.Column(sa.Text)
    expires_at = sa.Column(sa.TIMESTAMP(timezone=True))
    private_key_pem = sa.Column(
        StringEncryptedType(sa.Text, db_encryption_key, AesGcmEngine, "pkcs5")
    )
    csr_pem = sa.Column(sa.Text)
    fullchain_pem = sa.Column(sa.Text)
    iam_server_certificate_id = sa.Column(sa.String)
    iam_server_certificate_name = sa.Column(sa.String)
    iam_server_certificate_arn = sa.Column(sa.String)
    challenges = orm.relationship(
        "EdbChallenge",
        backref="certificate",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    order_json = sa.Column(sa.Text)


class EdbServiceInstance(EdbBase):
    __tablename__ = "service_instance"
    id = sa.Column(sa.String(36), primary_key=True)
    operations = orm.relationship(
        "EdbOperation", backref="service_instance", lazy="dynamic"
    )
    acme_user_id = sa.Column(sa.Integer, sa.ForeignKey("acme_user.id"))
    domain_names = sa.Column(postgresql.JSONB, default=[])
    instance_type = sa.Column(sa.Text)

    domain_internal = sa.Column(sa.String)

    route53_alias_hosted_zone = sa.Column(sa.String)
    route53_change_ids = sa.Column(postgresql.JSONB, default=[])

    deactivated_at = sa.Column(sa.TIMESTAMP(timezone=True))
    certificates = orm.relationship(
        "EdbCertificate",
        backref="service_instance",
        foreign_keys=EdbCertificate.service_instance_id,
    )
    current_certificate_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            "certificate.id",
            name="fk__service_instance__certificate__current_certificate_id",
        ),
    )
    current_certificate = orm.relationship(
        EdbCertificate,
        primaryjoin=current_certificate_id == EdbCertificate.id,
        foreign_keys=current_certificate_id,
        post_update=True,
    )
    new_certificate_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            "certificate.id",
            name="fk__service_instance__certificate__new_certificate_id",
        ),
    )
    new_certificate = orm.relationship(
        EdbCertificate,
        primaryjoin=new_certificate_id == EdbCertificate.id,
        foreign_keys=new_certificate_id,
        post_update=True,
    )

    __mapper_args__ = {
        "polymorphic_identity": "service_instance",
        "polymorphic_on": instance_type,
    }

    def has_active_operations(self):
        for operation in self.operations:
            if (
                operation.state == EdbOperation.States.IN_PROGRESS.value
                and operation.canceled_at is None
            ):
                return True
        return False

    def __repr__(self):
        return f"<ServiceInstance {self.id} {self.domain_names}>"


class EdbCDNServiceInstance(EdbServiceInstance):
    class ForwardCookiePolicy(Enum):
        ALL = "all"
        NONE = "none"
        WHITELIST = "whitelist"

    class ProtocolPolicy(Enum):
        HTTPS = "https-only"
        HTTP = "http-only"

    cloudfront_distribution_arn = sa.Column(sa.String)
    cloudfront_distribution_id = sa.Column(sa.String)
    cloudfront_origin_hostname = sa.Column(sa.String)
    cloudfront_origin_path = sa.Column(sa.String)
    forward_cookie_policy = sa.Column(sa.String, default=ForwardCookiePolicy.ALL.value)
    forwarded_cookies = sa.Column(postgresql.JSONB, default=[])
    forwarded_headers = sa.Column(postgresql.JSONB, default=[])
    error_responses = sa.Column(postgresql.JSONB, default=[])
    origin_protocol_policy = sa.Column(sa.String)

    __mapper_args__ = {"polymorphic_identity": "cdn_service_instance"}

    def __repr__(self):
        return f"<CDNServiceInstance {self.id} {self.domain_names}>"


class EdbALBServiceInstance(EdbServiceInstance):
    alb_arn = sa.Column(sa.String)
    alb_listener_arn = sa.Column(sa.String)

    previous_alb_arn = sa.Column(sa.String)
    previous_alb_listener_arn = sa.Column(sa.String)

    __mapper_args__ = {"polymorphic_identity": "alb_service_instance"}

    def __repr__(self):
        return f"<ALBServiceInstance {self.id} {self.domain_names}>"


class EdbOperation(EdbBase):
    __tablename__ = "operation"
    # operation.state = Operation.States.IN_PROGRESS.value
    class States(Enum):
        IN_PROGRESS = "in progress"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    # operation.action = Operation.Actions.PROVISION.value
    class Actions(Enum):
        PROVISION = "Provision"
        DEPROVISION = "Deprovision"
        RENEW = "Renew"
        UPDATE = "Update"

    id = sa.Column(sa.Integer, primary_key=True)
    service_instance_id = sa.Column(
        sa.String, sa.ForeignKey("service_instance.id"), nullable=False
    )
    state = sa.Column(
        sa.String,
        default=States.IN_PROGRESS.value,
        server_default=States.IN_PROGRESS.value,
        nullable=False,
    )
    action = sa.Column(sa.String, nullable=False)
    canceled_at = sa.Column(sa.TIMESTAMP(timezone=True))
    step_description = sa.Column(sa.String)

    def __repr__(self):
        return f"<Operation {self.id} {self.state}>"


class EdbChallenge(EdbBase):
    __tablename__ = "challenge"
    id = sa.Column(sa.Integer, primary_key=True)
    certificate_id = sa.Column(
        sa.Integer, sa.ForeignKey("certificate.id"), nullable=False
    )
    domain = sa.Column(sa.String, nullable=False)
    validation_domain = sa.Column(sa.String, nullable=False)
    validation_contents = sa.Column(sa.Text, nullable=False)
    body_json = sa.Column(sa.Text)
    answered = sa.Column(sa.Boolean, default=False)

    def __repr__(self):
        return f"<Challenge {self.id} {self.domain}>"
