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
        self.ENV = self.env_parser("ENV")


class LocalConfig(Config):
    def __init__(self):
        super().__init__()
        self.TESTING = True
        self.DEBUG = True


class DevelopmentConfig(Config):
    def __init__(self):
        super().__init__()


class StagingConfig(Config):
    def __init__(self):
        super().__init__()


class ProductionConfig(Config):
    def __init__(self):
        super().__init__()
