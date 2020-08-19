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


class LocalConfig(Config):
    def __init__(self):
        super().__init__()
        self.TESTING = True
        self.DEBUG = True
        self.CDN_BROKER_DATABASE_URI = "postgresql://localhost/local-development-cdn"


class AppConfig(Config):
    def __init__(self):
        super().__init__()
        cdn_db = self.cf_env_parser.get_service(name="rds-cdn-broker")
        self.CDN_BROKER_DATABASE_URI = cdn_db.credentials["uri"]


class DevelopmentConfig(AppConfig):
    def __init__(self):
        super().__init__()


class StagingConfig(AppConfig):
    def __init__(self):
        super().__init__()


class ProductionConfig(AppConfig):
    def __init__(self):
        super().__init__()
