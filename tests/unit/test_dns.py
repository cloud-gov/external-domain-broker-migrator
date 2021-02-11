from migrator.dns import get_cname


def test_dns_can_get_cname(dns):
    dns.add_cname("testcname.example.com.", "example.com")
    result = get_cname("testcname.example.com")
    assert result == "example.com"
