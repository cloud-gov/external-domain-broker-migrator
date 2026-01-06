from unittest import mock

from dns.exception import Timeout

from migrator.dns import get_cname, get_txt, has_expected_semaphore, has_expected_cname
from migrator.extensions import config


def test_dns_resolver_can_get_cname(dns):
    dns.add_cname("testcname.example.com.", "example.com")
    result = get_cname("testcname.example.com")
    assert result == "example.com"


def test_dns_resolver_can_get_txt(dns):
    dns.add_txt("testtxt.example.com.", "hello1")
    dns.add_txt("testtxt.example.com.", "hello2")
    results = get_txt("testtxt.example.com")
    assert sorted(results) == sorted(["hello1", "hello2"])


def test_dns_finds_semaphore(dns):
    dns.add_txt("_acme-challenge.example.com.", config.SEMAPHORE)
    assert has_expected_semaphore("example.com")


def test_dns_ignores_non_semaphore_txt_records(dns):
    dns.add_txt("_acme-challenge.example.net.", "some other txt record")
    assert not has_expected_semaphore("example.net")
    assert not has_expected_semaphore("example.org")


def test_dns_finds_semaphore_with_multiple_txt_records(dns):
    dns.add_txt("_acme-challenge.example.com.", "some other txt record")
    dns.add_txt("_acme-challenge.example.com.", config.SEMAPHORE)
    dns.add_txt("_acme-challenge.example.com.", "another txt record")
    assert has_expected_semaphore("example.com")


def test_has_expected_cname_returns_false_on_timeout(dns):
    m = mock.MagicMock()
    m.side_effect = Timeout
    with mock.patch("migrator.dns._resolver.resolve", new=m):
        assert not has_expected_semaphore("example.com")


def test_has_expected_cname_returns_false_on_exception(dns):
    # raise an exception we know doesn't exist, so we know we're
    # catching all exception cases
    class MyException(Exception):
        pass

    m = mock.MagicMock()
    m.side_effect = MyException
    with mock.patch("migrator.dns._resolver.resolve", new=m):
        assert not has_expected_semaphore("example.com")


def test_has_expected_cname(dns):
    dns.add_cname("testcname.example.com.", "testcname.example.com.domains.cloud.test")
    dns.add_cname(
        "_acme-challenge.testcname.example.com.",
        "_acme-challenge.testcname.example.com.domains.cloud.test",
    )
    assert has_expected_cname("testcname.example.com", False) == True


def test_missing_acme_challenge_expected_cname(dns):
    dns.add_cname("testcname.example.com.", "testcname.example.com.domains.cloud.test")
    assert has_expected_cname("testcname.example.com", False) == False


def test_missing_site_expected_cname(dns):
    dns.add_cname(
        "_acme-challenge.testcname.example.com.",
        "_acme-challenge.testcname.example.com.domains.cloud.test",
    )
    assert has_expected_cname("testcname.example.com", False) == False


def test_skip_expected_site_cname(dns):
    dns.add_cname(
        "_acme-challenge.testcname.example.com.",
        "_acme-challenge.testcname.example.com.domains.cloud.test",
    )
    assert has_expected_cname("testcname.example.com", True) == True
