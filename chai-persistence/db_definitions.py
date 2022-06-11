# pylint: disable=line-too-long, missing-module-docstring, too-few-public-methods, missing-class-docstring

from contextlib import contextmanager

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm import relationship, declarative_base

from chai_persistence.utilities import Configuration


def db_engine(config: Configuration):
    """
    Get a database engine.
    :param config: The configuration to use to initialise the database engine.
    :return: A database engine connection.
    """
    target = "sqlite:///:memory:" if config.db_in_memory else f"sqlite:///{config.database}?check_same_thread=False"
    return create_engine(target, echo=config.enable_debugging, future=True)


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


Base = declarative_base()


class Efergy(Base):
    __tablename__ = "efergy"
    id = Column(Integer, primary_key=True)
    token = Column(String)
    readings = relationship("EfergyReading", back_populates="meter")


class Netatmo(Base):
    __tablename__ = "netatmo"
    id = Column(Integer, primary_key=True)
    refresh_token = Column(String)
    readings = relationship("NetatmoReading", back_populates="relay")


class Home(Base):
    __tablename__ = "homes"
    id = Column(Integer, primary_key=True)
    label = Column(String)
    revision = Column(DateTime)
    efergy_id = Column(Integer, ForeignKey("efergy.id"))
    netatmo_id = Column(Integer, ForeignKey("netatmo.id"))
    meter: Efergy = relationship("Efergy")
    relay: Netatmo = relationship("Netatmo")


class EfergyReading(Base):
    __tablename__ = "efergy_readings"
    id = Column(Integer, primary_key=True)
    efergy_id = Column(Integer, ForeignKey("efergy.id"))
    start = Column(DateTime)
    end = Column(DateTime)
    reading = Column(Float)
    meter = relationship("Efergy", back_populates="readings")


class NetatmoReading(Base):
    __tablename__ = "netatmo_readings"
    id = Column(Integer, primary_key=True)
    netatmo_id = Column(Integer, ForeignKey("netatmo.id"))
    start = Column(DateTime)
    end = Column(DateTime)
    room_type = Column(Integer)
    reading = Column(Float)
    relay = relationship("Netatmo", back_populates="readings")


class SetpointChange(Base):
    __tablename__ = "setpoint_changes"
    id = Column(Integer, primary_key=True)
    netatmo_id = Column(Integer, ForeignKey("netatmo.id"))
    time = Column(DateTime)
    room_type = Column(Integer)
    mode = Column(String)
    temperature = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)


if __name__ == "__main__":
    pass
