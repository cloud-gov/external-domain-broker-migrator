from migrator.db import session_handler
from migrator.migration import find_active_instances

# Extract a list of domain names from all CdnRoutes.
def find_domains():
    with session_handler() as session:
        routes = find_active_instances(session)
        domains = list(map(lambda route: route.domain_external, routes))
        return domains
