import pytest
import re
from flagger.queries import find_domains
from migrator.models import CdnRoute


def test_flagger_finds_domains(clean_db):
    for i in range(5):
        route = CdnRoute()
        route.state = "provisioned"
        route.instance_id = f"instance-{i}"
        route.domain_external = f"domain{i}.example.com"
        clean_db.add(route)
    clean_db.commit()
    clean_db.close()
    domains = find_domains()
    assert re.match(r"domain\d.example.com", domains[0])
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
    domains = find_domains()
    assert sorted(domains) == sorted(
        ["example1.com", "example2.com", "example3.com", "example4.com"]
    )
