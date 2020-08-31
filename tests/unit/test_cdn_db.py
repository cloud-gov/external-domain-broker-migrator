import pytest
import sqlalchemy as sa
from sqlalchemy import orm
from migrator import db
from migrator import models
from migrator import extensions


def test_can_get_session():
    with db.session_handler() as session:
        result = session.execute(
            "SELECT count(1) FROM certificates", bind=db.cdn_engine
        )
        assert result.first() == (0,)


def test_can_create_route():
    # the assertion here is really just that no exceptions are raised

    # note that we shouldn't _actually_ be creating routes in this project
    # but this is a test we can do with an empty database
    with db.session_handler() as session:
        route = models.CdnRoute()
        route.id = 12345
        route.instance_id = "disposable-route-id"
        route.state = "deprovisioned"
        session.add(route)
        session.commit()

        route = session.query(models.CdnRoute).filter_by(id=12345).first()
        session.delete(route)
        session.commit()
        session.close()


def test_check_connections():
    engine = sa.create_engine("postgresql://localhost:1234")
    Session = orm.sessionmaker(bind=engine)
    with pytest.raises(Exception):
        db.check_connections(cdn_session_maker=Session, cdn_binding=engine)

    with pytest.raises(Exception):
        db.check_connections(cdn_session_maker=Session, external_domain_binding=engine)
    db.check_connections()
