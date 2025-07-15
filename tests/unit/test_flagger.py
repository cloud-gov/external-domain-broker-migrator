import pytest
import re
from flagger.queries import find_domains, find_domain_aliases
from migrator.models import CdnRoute, DomainAlbProxy, DomainRoute


def test_flagger_finds_domains(clean_db):
    for i in range(5):
        route = CdnRoute()
        route.state = "provisioned"
        route.instance_id = f"instance-{i}"
        route.domain_external = f"domain{i}.example.com"
        clean_db.add(route)
    clean_db.commit()
    clean_db.close()
    domains = find_domains(clean_db)
    assert re.match(r"domain\d\.example\.com", domains[0])
    assert len(domains) == 5


def test_flagger_finds_multiple_domains_in_route(clean_db):
    route1 = CdnRoute()
    route1.state = "provisioned"
    route1.instance_id = "12345"
    route1.domain_external = "example1.com,example2.com,example3.com"
    clean_db.add(route1)
    route2 = CdnRoute()
    route2.state = "provisioned"
    route2.instance_id = "67890"
    route2.domain_external = "example4.com"
    clean_db.add(route2)
    clean_db.commit()
    clean_db.close()
    domains = find_domains(clean_db)
    assert sorted(domains) == sorted(
        ["example1.com", "example2.com", "example3.com", "example4.com"]
    )


def test_flagger_finds_alb_dns(clean_db):

    proxy_0 = DomainAlbProxy()
    proxy_0.alb_arn = "arn:0123"
    proxy_0.alb_dns_name = "foo0.example.com"
    proxy_0.listener_arn = "arn:234"
    proxy_1 = DomainAlbProxy()
    proxy_1.alb_arn = "arn:1234"
    proxy_1.alb_dns_name = "foo1.example.com"
    proxy_1.listener_arn = "arn:234"
    clean_db.add(proxy_0)
    clean_db.add(proxy_1)
    clean_db.commit()

    route_0 = DomainRoute()
    route_0.alb_proxy_arn = "arn:0123"
    route_0.instance_id = "0123"
    route_0.state = "provisioned"
    route_0.domains = ["domain0.example.com"]
    route_1 = DomainRoute()
    route_1.alb_proxy_arn = "arn:1234"
    route_1.instance_id = "1234"
    route_1.state = "provisioned"
    route_1.domains = ["domain1.example.com"]
    clean_db.add(route_0)
    clean_db.add(route_1)
    clean_db.commit()

    domain_aliases = find_domain_aliases(clean_db)

    # it's _possible_ these will come back in a different order
    # we'll cross that bridge if we come to it.
    assert domain_aliases[0][0] == "domain0.example.com"
    assert domain_aliases[0][1] == "foo0.example.com"
    assert domain_aliases[1][0] == "domain1.example.com"
    assert domain_aliases[1][1] == "foo1.example.com"
