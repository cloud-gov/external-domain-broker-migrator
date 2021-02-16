from migrator.dns import get_cname, get_txt, has_expected_semaphore
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
