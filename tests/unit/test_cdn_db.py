import pytest
from migrator import db


def test_can_get_session():
    session = db.CdnSession()
    result = session.execute("SELECT count(1) FROM certificates")
    assert result.first() == (0,)
