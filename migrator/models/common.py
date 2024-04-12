import datetime
from enum import Enum
from typing import Union, Type, List

from migrator.extensions import config


class Action(str, Enum):
    RENEW = "renew"


class RouteType(str, Enum):
    CDN = "cdn"
    ALB = "alb"


class OperationState(str, Enum):
    IN_PROGRESS = "in progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RouteModel:
    __allow_unmapped__ = True

    @property
    def needs_renewal(self):
        return all([c.needs_renewal for c in self.certificates])

    @classmethod
    def find_active_instances(cls, session):
        query = session.query(cls).filter(cls.state == "provisioned")
        routes = query.all()
        return routes


class CertificateModel:
    __allow_unmapped__ = True

    @property
    def needs_renewal(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        return self.expires < now + datetime.timedelta(days=config.RENEW_BEFORE_DAYS)


class OperationModel:
    __allow_unmapped__ = True
    pass


class AcmeUserV2Model:
    __allow_unmapped__ = True

    @classmethod
    def get_user(cls, session):
        users: List = session.query(cls).all()
        users = sorted(users, key=lambda x: len(list(x.routes)))
        if not len(users):
            return None
        lowest = users[0]
        if len(lowest.routes) >= config.MAX_ROUTES_PER_USER:
            return None
        return lowest


class ChallengeModel:
    __allow_unmapped__ = True
    pass
