from migrator.models import CdnRoute


def find_active_instances(session):
    query = session.query(CdnRoute).filter(CdnRoute.state == "provisioned")
    routes = query.all()
    return routes
