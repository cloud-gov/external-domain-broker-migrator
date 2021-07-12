import pytest
import sqlalchemy as sa
from sqlalchemy import orm
from migrator import db
from migrator import models
from migrator import extensions


def test_can_get_session():
    with db.session_handler() as session:
        result = session.execute(
            "SELECT count(1) FROM certificates", bind=db.domain_engine
        )
        assert result.first() == (0,)


def test_can_create_route():
    # the assertion here is really just that no exceptions are raised

    # note that we shouldn't _actually_ be creating routes in this project
    # but this is a test we can do with an empty database
    with db.session_handler() as session:
        route = models.DomainRoute()
        route.instance_id = "12345"
        route.state = "deprovisioned"
        route.domains = ["example1.com", "example2.com", "example3.com"]

        session.add(route)
        session.commit()

        route = session.query(models.DomainRoute).filter_by(instance_id="12345").first()
        session.delete(route)
        session.commit()
        session.close()
