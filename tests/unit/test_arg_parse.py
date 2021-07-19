import pytest

from migrator.__main__ import parse_args


def test_arg_parse_fails_with_no_args():
    with pytest.raises(SystemExit):
        parse_args([])


def test_arg_parse_returns_cron_for_cron():
    parsed = parse_args(["--cron"])
    assert parsed.cron
    assert not parsed.instance


def test_arg_parse_returns_instance_for_instance():
    parsed = parse_args(["--instance", "asdf-asdf"])
    assert parsed.instance == "asdf-asdf"
    assert not parsed.cron
