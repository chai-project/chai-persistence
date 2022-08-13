# pylint: disable=line-too-long, missing-module-docstring, too-few-public-methods, missing-class-docstring

from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, TIMESTAMP, Index
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.orm import scoped_session


@dataclass
class Configuration:
    server: str
    username: str
    password: str
    database: str = "chai"
    enable_debugging: bool = False


def db_engine(config: Configuration):
    """
    Get a database engine.
    :param config: The configuration to use to initialise the database engine.
    :return: A database engine connection.
    """
    target = f"postgresql+pg8000://{config.username}:{config.password}@{config.server}/{config.database}"
    return create_engine(target, echo=config.enable_debugging, future=True, client_encoding="utf8")


@contextmanager
def db_engine_manager(config: Configuration):
    """
    A context manager that yields a database engine.
    :param config: The configuration to use to initialise the database engine.
    :return: A database engine connection.
    """
    yield db_engine(config)


@contextmanager
def db_session(st_session: scoped_session):
    """
    A context manager that yields a database connection.
    :param st_session: The database engine connection to bind the session to.
    :return: A database session.
    """
    _session = st_session()
    try:
        yield _session
        _session.commit()
    finally:
        _session.close()


# database naming convention is to use camelCase and singular nouns throughout

Base = declarative_base()


class NetatmoDevice(Base):
    __tablename__ = "netatmodevice"
    id = Column(Integer, primary_key=True)
    refreshToken = Column("refreshtoken", String, nullable=False)
    readings = relationship("NetatmoReading", back_populates="relay")


class Home(Base):
    __tablename__ = "home"
    id = Column(Integer, primary_key=True)
    label = Column(String, nullable=False)
    revision = Column(TIMESTAMP, nullable=False)
    netatmoID = Column("netatmoid", Integer, ForeignKey("netatmodevice.id"), nullable=False)
    relay: NetatmoDevice = relationship("NetatmoDevice")


class NetatmoReading(Base):
    __tablename__ = "netatmoreading"
    id = Column(Integer, primary_key=True)
    room_id = Column("roomid", Integer, nullable=False)  # 1 for thermostat temp, 2 for valve temp, 3 for valve %
    netatmo_id = Column("netatmoid", Integer, ForeignKey("netatmodevice.id"), nullable=False)
    start = Column(DateTime, nullable=False, index=True)
    end = Column(DateTime, nullable=False, index=True)
    reading = Column(Float, nullable=False)
    relay: NetatmoDevice = relationship("NetatmoDevice", back_populates="readings")
    idxOneReading = Index("ix_one_reading", id, room_id, start, unique=True)
