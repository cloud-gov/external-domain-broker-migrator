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
