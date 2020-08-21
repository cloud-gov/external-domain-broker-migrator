import pytest
from migrator.db import cdn_session_handler


@pytest.fixture
def clean_db():
    with cdn_session_handler() as session:
        session.execute("TRUNCATE TABLE user_data")
        session.execute("TRUNCATE TABLE routes")
        session.execute("TRUNCATE TABLE certificates")
        session.commit()
        session.close()
        yield session
        session.execute("TRUNCATE TABLE user_data")
        session.execute("TRUNCATE TABLE routes")
        session.execute("TRUNCATE TABLE certificates")
        session.commit()
        session.close()
