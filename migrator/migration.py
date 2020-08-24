from migrator.dns import has_expected_cname
from migrator.models import CdnRoute


def find_active_instances(session):
    query = session.query(CdnRoute).filter(CdnRoute.state == "provisioned")
    routes = query.all()
    return routes


class Migration:
    def __init__(self, route: CdnRoute):
        self.domains = route.domain_external.split(",")
        self.instance_id = route.instance_id
        self.cloudfront_distribution_id = route.dist_id

    @property
    def has_valid_dns(self):
        if not self.domains:
            return False
        return all([has_expected_cname(domain) for domain in self.domains])
