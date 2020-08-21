import pytest
from migrator.migrator import find_active_instances, check_route_dns
from migrator.models import CdnRoute


def test_find_instances(clean_db):
    states = [
        "provisioned",
        "deprovisioned",
        "deprovisioning",
        "this-state-should-never-exist",
    ]
    for state in states:
        route = CdnRoute()
        route.state = state
        route.instance_id = f"id-{state}"
        clean_db.add(route)
    clean_db.commit()
    clean_db.close()
    instances = find_active_instances(clean_db)
    assert len(instances) == 1
    assert instances[0].state == "provisioned"


def test_validate_good_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com"
    assert check_route_dns(route)


def test_validate_bad_dns(clean_db, dns):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com"
    assert not check_route_dns(route)


def test_validate_no_domains(clean_db, dns):
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    assert not check_route_dns(route)


def test_validate_mixed_good_and_bad_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    assert not check_route_dns(route)


def test_validate_multiple_valid_dns(clean_db, dns):
    dns.add_cname("_acme-challenge.example.com")
    dns.add_cname("_acme-challenge.foo.example.com")
    route = CdnRoute()
    route.state = "provisioned"
    route.instance_id = "asdf-asdf"
    route.domain_external = "example.com,foo.example.com"
    assert check_route_dns(route)
