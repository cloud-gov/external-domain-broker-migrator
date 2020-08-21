from migrator.dns import has_expected_cname
from migrator.models import CdnRoute


def find_active_instances(session):
    query = session.query(CdnRoute).filter(CdnRoute.state == "provisioned")
    routes = query.all()
    return routes


def check_route_dns(route):
    if not route.domain_external:
        return False
    domains = route.domain_external.split(",")
    return all([has_expected_cname(domain) for domain in domains])
