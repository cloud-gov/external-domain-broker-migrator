import pytest
import sqlalchemy as sa

from migrator.db import session_handler, cdn_engine, domain_engine
from migrator.models.cdn import metadata as cdn_meta
from migrator.models.domain import metadata as domain_meta
from migrator.extensions import config




@pytest.fixture
def clean_db():
    if config.ENV == "unit":
        domain_meta.drop_all(domain_engine)
        cdn_meta.drop_all(cdn_engine)
        domain_meta.create_all(domain_engine)
        cdn_meta.create_all(cdn_engine)
        with session_handler() as session:
            yield session
    else:
        with session_handler() as session:
            session.execute(
                sa.text("TRUNCATE TABLE user_data CASCADE"),
                bind_arguments={"bind": cdn_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE routes CASCADE"),
                bind_arguments={"bind": cdn_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE certificates CASCADE"),
                bind_arguments={"bind": cdn_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE user_data CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE routes CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE certificates CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE alb_proxies CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.commit()
            session.close()
            yield session
            session.execute(
                sa.text("TRUNCATE TABLE user_data CASCADE"),
                bind_arguments={"bind": cdn_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE routes CASCADE"),
                bind_arguments={"bind": cdn_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE certificates CASCADE"),
                bind_arguments={"bind": cdn_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE user_data CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE routes CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE certificates CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.execute(
                sa.text("TRUNCATE TABLE alb_proxies CASCADE"),
                bind_arguments={"bind": domain_engine},
            )
            session.commit()
            session.close()
