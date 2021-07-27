from cfenv import AppEnv
from environs import Env


def config_from_env():
    environments = {
        "local": LocalConfig,
        "development": DevelopmentConfig,
        "staging": StagingConfig,
        "production": ProductionConfig,
    }
    env = Env()
    return environments[env("ENV")]()


class Config:
    def __init__(self):
        self.env_parser = Env()
        self.cf_env_parser = AppEnv()
        self.ENV = self.env_parser("ENV")
        self.SEMAPHORE = "cloud-gov-migration-ready"
        # this is a well-known constant
        # https://docs.aws.amazon.com/Route53/latest/APIReference/API_AliasTarget.html
        self.CLOUDFRONT_HOSTED_ZONE_ID = "Z2FDTNDATAQYW2"


class LocalConfig(Config):
    def __init__(self):
        super().__init__()
        self.TESTING = True
        self.DEBUG = True
        self.CDN_BROKER_DATABASE_URI = "postgresql://localhost/local-development-cdn"
        self.DOMAIN_BROKER_DATABASE_URI = (
            "postgresql://localhost/local-development-domain"
        )
        self.DNS_VERIFICATION_SERVER = "127.0.0.1:8053"
        self.DNS_ROOT_DOMAIN = "domains.cloud.test"
        self.AWS_COMMERCIAL_REGION = "us-west-1"
        self.AWS_COMMERCIAL_ACCESS_KEY_ID = "ASIANOTAREALKEY"
        self.AWS_COMMERCIAL_SECRET_ACCESS_KEY = "THIS_IS_A_FAKE_KEY"
        self.AWS_GOVCLOUD_REGION = "us-gov-west-1"
        self.AWS_GOVCLOUD_ACCESS_KEY_ID = "ASIANOTAREALKEYGOV"
        self.AWS_GOVCLOUD_SECRET_ACCESS_KEY = "THIS_IS_A_FAKE_KEY_GOV"
        self.ROUTE53_ZONE_ID = "FAKEZONEID"
        # https://docs.aws.amazon.com/Route53/latest/APIReference/API_AliasTarget.html
        self.ALB_HOSTED_ZONE_ID = "FAKEZONEIDFORALBS"
        self.AWS_POLL_WAIT_TIME_IN_SECONDS = 0.01
        self.AWS_POLL_MAX_ATTEMPTS = 10
        self.CF_USERNAME = "fake-username"
        self.CF_PASSWORD = "fake-password"
        self.CF_API_ENDPOINT = "http://localhost"
        self.SERVICE_CHANGE_RETRY_COUNT = 2
        self.SERVICE_CHANGE_POLL_TIME_SECONDS = 0.01
        self.MIGRATION_TIME = "11:00:00"
        self.MIGRATION_PLAN_ID = "FAKE-MIGRATION-PLAN-GUID"
        self.CDN_PLAN_ID = "FAKE-CDN-PLAN-GUID"
        self.DOMAIN_PLAN_ID = "FAKE-DOMAIN-PLAN-GUID"


class AppConfig(Config):
    def __init__(self):
        super().__init__()
        cdn_db = self.cf_env_parser.get_service(name="rds-cdn-broker")
        self.CDN_BROKER_DATABASE_URI = cdn_db.credentials["uri"]
        alb_db = self.cf_env_parser.get_service(name="rds-domain-broker")
        self.DOMAIN_BROKER_DATABASE_URI = alb_db.credentials["uri"]
        self.DNS_VERIFICATION_SERVER = "8.8.8.8:53"
        self.DNS_ROOT_DOMAIN = self.env_parser("DNS_ROOT_DOMAIN")
        self.AWS_COMMERCIAL_REGION = self.env_parser("AWS_COMMERCIAL_REGION")
        self.AWS_COMMERCIAL_ACCESS_KEY_ID = self.env_parser(
            "AWS_COMMERCIAL_ACCESS_KEY_ID"
        )
        self.AWS_COMMERCIAL_SECRET_ACCESS_KEY = self.env_parser(
            "AWS_COMMERCIAL_SECRET_ACCESS_KEY"
        )
        self.AWS_GOVCLOUD_REGION = self.env_parser("AWS_GOVCLOUD_REGION")
        self.AWS_GOVCLOUD_ACCESS_KEY_ID = self.env_parser("AWS_GOVCLOUD_ACCESS_KEY_ID")
        self.AWS_GOVCLOUD_SECRET_ACCESS_KEY = self.env_parser(
            "AWS_GOVCLOUD_SECRET_ACCESS_KEY"
        )
        self.ROUTE53_ZONE_ID = self.env_parser("ROUTE53_HOSTED_ZONE_ID")
        self.ALB_HOSTED_ZONE_ID = self.env_parser("ALB_HOSTED_ZONE_ID")
        self.CF_USERNAME = self.env_parser("CF_USERNAME")
        self.CF_PASSWORD = self.env_parser("CF_PASSWORD")
        self.CF_API_ENDPOINT = self.env_parser("CF_API_ENDPOINT")
        self.AWS_POLL_WAIT_TIME_IN_SECONDS = 60
        self.AWS_POLL_MAX_ATTEMPTS = 10
        # just a little bit longer than the broker will try for
        self.SERVICE_CHANGE_RETRY_COUNT = 1440
        self.SERVICE_CHANGE_POLL_TIME_SECONDS = 10
        self.MIGRATION_TIME = self.env_parser("MIGRATION_TIME", "11:00:00")
        self.MIGRATION_PLAN_ID = self.env_parser("MIGRATION_PLAN_ID")
        self.CDN_PLAN_ID = self.env_parser("CDN_PLAN_ID")
        self.DOMAIN_PLAN_ID = self.env_parser("DOMAIN_PLAN_ID")

        self.SMTP_HOST = self.env_parser("SMTP_HOST")
        self.SMTP_FROM = self.env_parser("SMTP_FROM")
        self.SMTP_CERT = self.env_parser("SMTP_CERT")
        self.SMTP_USER = self.env_parser("SMTP_USER")
        self.SMTP_PASS = self.env_parser("SMTP_PASS")
        self.SMTP_PORT = self.env_parser.int("SMTP_PORT")
        self.SMTP_TO = self.env_parser("SMTP_TO")
        self.SMTP_TLS = True


class DevelopmentConfig(AppConfig):
    def __init__(self):
        super().__init__()


class StagingConfig(AppConfig):
    def __init__(self):
        super().__init__()


class ProductionConfig(AppConfig):
    def __init__(self):
        super().__init__()
