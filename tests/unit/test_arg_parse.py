import pytest

from migrator.__main__ import parse_args


def test_arg_parse_fails_with_no_args():
    with pytest.raises(SystemExit):
        parse_args([])


def test_arg_parse_returns_cron_for_cron():
    parsed = parse_args(["--cron"])
    assert parsed.cron
    assert not parsed.instance
    assert not parsed.skip_site_dns_check


def test_arg_parse_returns_instance_for_instance_and_not_forced():
    parsed = parse_args(
        [
            "--instance",
            "asdf-asdf",
        ]
    )
    assert parsed.instance == "asdf-asdf"
    assert not parsed.cron
    assert not parsed.force


def test_arg_parse_returns_instance_for_instance_and_forced_for_forced():
    parsed = parse_args(["--instance", "asdf-asdf", "--force"])
    assert parsed.instance == "asdf-asdf"
    assert not parsed.cron
    assert parsed.force


def test_arg_parse_skip_site_dns_check():
    parsed = parse_args(["--instance", "asdf-asdf", "--skip-site-dns-check"])
    assert parsed.instance == "asdf-asdf"
    assert not parsed.cron
    assert not parsed.force
    assert parsed.skip_site_dns_check
