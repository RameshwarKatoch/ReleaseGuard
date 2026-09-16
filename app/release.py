from sqlalchemy import Column, Integer, String
from app.models import Base


class Release(Base):
    __tablename__ = "releases"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String)
    environment = Column(String)
    deployment_status = Column(String)
    health_status = Column(String)
    commit_sha = Column(String)