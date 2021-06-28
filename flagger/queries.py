from migrator.db import session_handler
from migrator.migration import find_active_instances

# Extract a list of domain names from all CdnRoutes.
def find_domains():
    with session_handler() as session:
        routes = find_active_instances(session)
        domains = []
        for route in routes:
            domains.extend(route.domain_external_list())
        return domains


def find_aliases():
    with session_handler() as session:
        routes = find_active_instances(session)
        domain_cdns = []
        for route in routes:
            for domain in route.domain_external_list():
                domain_cdns.append((domain, route.domain_internal))
    return domain_cdns
