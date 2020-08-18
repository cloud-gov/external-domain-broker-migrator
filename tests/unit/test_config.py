import pytest


from migrator.config import config_from_env


@pytest.mark.parametrize("env", ["local", "development", "staging", "production"])
def test_config_doesnt_explode(env, monkeypatch):
    monkeypatch.setenv("ENV", env)
    config = config_from_env()

    assert config.ENV == env
