import pytest
import sqlalchemy as sa

from migrator.db import session_handler, cdn_engine, domain_engine


@pytest.fixture
def clean_db():
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
