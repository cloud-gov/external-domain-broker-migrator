from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from migrator.extensions import config
from migrator.models import CdnBase

cdn_engine = create_engine(config.CDN_BROKER_DATABASE_URI)
external_domain_engine = create_engine(config.EXTERNAL_DOMAIN_BROKER_DATABASE_URI)
Session = sessionmaker(binds={CdnBase: cdn_engine})


@contextmanager
def session_handler():
    session = Session()
    try:
        yield session
    finally:
        session.close()


def check_connections(
    session_maker=Session,
    cdn_binding=cdn_engine,
    external_domain_binding=external_domain_engine,
):
    session = session_maker()
    session.execute("SELECT 1 FROM certificates", bind=cdn_binding)
    session.close()
    session.execute("SELECT 1 FROM service_instance", bind=external_domain_binding)
    session.close()
