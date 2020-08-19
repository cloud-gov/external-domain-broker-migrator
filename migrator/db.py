from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from migrator.extensions import config

cdn_engine = create_engine(config.CDN_BROKER_DATABASE_URI)
CdnSession = sessionmaker(bind=cdn_engine)
