from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from migrator.extensions import config
from migrator.models.cdn import CdnModel
from migrator.models.domain import DomainModel

cdn_engine = create_engine(config.CDN_BROKER_DATABASE_URI)
domain_engine = create_engine(config.DOMAIN_BROKER_DATABASE_URI)
Session = sessionmaker(binds={CdnModel: cdn_engine, DomainModel: domain_engine})


@contextmanager
def session_handler():
    session = Session()
    try:
        yield session
    finally:
        session.close()


def check_connections(
    session_maker=Session, cdn_binding=cdn_engine, domain_binding=domain_engine
):
    session = session_maker()
    session.execute(
        sa.text("SELECT 1 FROM certificates"), bind_arguments={"bind": cdn_binding}
    )
    session.execute(
        sa.text("SELECT 1 FROM certificates"), bind_arguments={"bind": domain_binding}
    )
    session.close()
