import pytest
from migrator.db import session_handler, cdn_engine, domain_engine


@pytest.fixture
def clean_db():
    with session_handler() as session:
        session.execute("TRUNCATE TABLE user_data CASCADE", bind=cdn_engine)
        session.execute("TRUNCATE TABLE routes CASCADE", bind=cdn_engine)
        session.execute("TRUNCATE TABLE certificates CASCADE", bind=cdn_engine)
        session.execute("TRUNCATE TABLE user_data CASCADE", bind=domain_engine)
        session.execute("TRUNCATE TABLE routes CASCADE", bind=domain_engine)
        session.execute("TRUNCATE TABLE certificates CASCADE", bind=domain_engine)
        session.execute("TRUNCATE TABLE alb_proxies CASCADE", bind=domain_engine)
        session.commit()
        session.close()
        yield session
        session.execute("TRUNCATE TABLE user_data CASCADE", bind=cdn_engine)
        session.execute("TRUNCATE TABLE routes CASCADE", bind=cdn_engine)
        session.execute("TRUNCATE TABLE certificates CASCADE", bind=cdn_engine)
        session.execute("TRUNCATE TABLE user_data CASCADE", bind=domain_engine)
        session.execute("TRUNCATE TABLE routes CASCADE", bind=domain_engine)
        session.execute("TRUNCATE TABLE certificates CASCADE", bind=domain_engine)
        session.execute("TRUNCATE TABLE alb_proxies CASCADE", bind=domain_engine)
        session.commit()
        session.close()
