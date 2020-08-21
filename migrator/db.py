from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from migrator.extensions import config

cdn_engine = create_engine(config.CDN_BROKER_DATABASE_URI)
CdnSession = sessionmaker(bind=cdn_engine)


@contextmanager
def cdn_session_handler():
    session = CdnSession()
    try:
        yield session
    finally:
        session.close()


def check_connections(cdn_session_maker=CdnSession):
    cdn_session = cdn_session_maker()
    cdn_session.execute("SELECT 1 FROM certificates")
    cdn_session.close()
