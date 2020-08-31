import pytest
from migrator.db import session_handler, cdn_engine


@pytest.fixture
def clean_db():
    with session_handler() as session:
        session.execute("TRUNCATE TABLE user_data", bind=cdn_engine)
        session.execute("TRUNCATE TABLE routes", bind=cdn_engine)
        session.execute("TRUNCATE TABLE certificates", bind=cdn_engine)
        session.commit()
        session.close()
        yield session
        session.execute("TRUNCATE TABLE user_data", bind=cdn_engine)
        session.execute("TRUNCATE TABLE routes", bind=cdn_engine)
        session.execute("TRUNCATE TABLE certificates", bind=cdn_engine)
        session.commit()
        session.close()
