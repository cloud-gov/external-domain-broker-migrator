from migrator.dns import get_cname, get_txt


def test_dns_resolver_can_get_cname(dns):
    dns.add_cname("testcname.example.com.", "example.com")
    result = get_cname("testcname.example.com")
    assert result == "example.com"


def test_dns_resolver_can_get_txt(dns):
    dns.add_txt("testtxt.example.com.", "hello1")
    dns.add_txt("testtxt.example.com.", "hello2")
    results = get_txt("testtxt.example.com")
    assert sorted(results) == sorted(["hello1", "hello2"])
