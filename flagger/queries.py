from migrator.db import session_handler
from migrator.migration import (
    find_active_instances,
    find_active_domain_instances,
    find_active_cdn_instances,
)

# Extract a list of domain names from all CdnRoutes.
def find_domains(session):
    routes = find_active_instances(session)
    domains = []
    for route in routes:
        domains.extend(route.domain_external_list())
    return domains


def find_cdn_aliases(session):
    routes = find_active_cdn_instances(session)
    domain_cdns = []
    for route in routes:
        for domain in route.domain_external_list():
            domain_cdns.append((domain, route.domain_internal))
    return domain_cdns


def find_domain_aliases(session):
    routes = find_active_domain_instances(session)
    domain_albs = []
    for route in routes:
        for domain in route.domain_external_list():
            domain_albs.append((domain, route.alb_proxy.alb_dns_name))
    return domain_albs
