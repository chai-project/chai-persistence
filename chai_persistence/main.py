# pylint: disable=line-too-long, missing-module-docstring
# pylint: disable=loop-invariant-statement, loop-global-usage, singleton-comparison

import logging
import os
from threading import Thread
from typing import Dict, Tuple, Optional

from chai_data_sources import DeviceType, SetpointMode
from pause import sleep
from sqlalchemy import and_
from sqlalchemy.orm import aliased, Session, sessionmaker, scoped_session

from chai_persistence.db_definitions import Home, db_session, db_engine, Base
from chai_persistence.home_interface import HomeInterface
from chai_persistence.utilities import Configuration, read_config

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


# logging.basicConfig(level=logging.DEBUG)

# get all the current homes (and periodically check for changes)
# store home instances so that they can be used for both automated logging and for user interaction

# for every participant:
#   log the power use (and convert it)
#     binning of the power measurements
#   fix power use gaps with periodic checks
#   log the temperature for both valve and thermostat
#   fix temperature use gaps with periodic checks
#   accept calls to change setpoint temperature
#     log changes to DB and execute them


class SingletonMeta(type):  # pylint: disable=missing-class-docstring
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Intercept calls to make a new class of a given type and instead
        create a blank instance or return existing instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Homes(metaclass=SingletonMeta):
    """ Singleton instance that provides a single point of call for automated home information logging,
        retrieving home information, and modifying home setpoints. """
    _config: Configuration
    _st_session: scoped_session
    _home_interfaces: Dict[str, Tuple[int, HomeInterface]]
    _thread: Thread

    def __init__(self):
        self._config = read_config(os.path.dirname(os.path.realpath(__file__)))

        engine = db_engine(self._config)
        Base.metadata.create_all(engine)  # create the DB tables if they don't exist yet
        session_factory = sessionmaker(bind=engine)
        self._st_session: scoped_session = scoped_session(session_factory)

        self._home_interfaces = {}

        self._thread = Thread(target=self._update_homes, args=(1 * 60 * 60,), daemon=False, name="homes refresh")
        self._thread.start()

    def _update_homes(self, sleep_duration: int):
        while True:
            session: Session
            with db_session(self._st_session) as session:
                home_alias = aliased(Home)
                homes = session.query(Home) \
                    .outerjoin(home_alias, and_(Home.label == home_alias.label, Home.revision < home_alias.revision)) \
                    .filter(home_alias.revision == None)  # noqa: E711

                homes = homes.all()
                for home in homes:
                    if home.label in self._home_interfaces:
                        db_id, h_i = self._home_interfaces[home.label]  # get the home interface we currently have
                        if home.id != db_id:  # if the id changed for the home with this label we need ...
                            h_i.stop()  # ... stop it's background threads and ...
                            del self._home_interfaces[home.label]  # ... remove its reference
                    if home.label not in self._home_interfaces:
                        h_i = HomeInterface(home_db_id=home.id, st_session=self._st_session,
                                            efergy_token=home.meter.token,
                                            netatmo_refresh_token=home.relay.refresh_token,
                                            client_id=self._config.client_id, client_secret=self._config.client_secret)
                        self._home_interfaces[home.label] = (home.id, h_i)
                    print("started all interfaces")

            sleep(sleep_duration)

    def get_power(self, home_label: str) -> Optional[int]:
        """ The current power reading in W for a given home.
        :param home_label: The unique label of the home you want to access information from.
        :return: The current power reading in W, or None if the reading could not be retrieved.
        """
        if home_label not in self._home_interfaces:
            return None
        _, h_i = self._home_interfaces[home_label]
        return h_i.power_current.value

    def get_temperature(self, home_label: str, device: DeviceType) -> Optional[float]:
        """ Get temperature in Celsius reported by the Netatmo thermostat/cube or the valve.
        :param home_label: The unique label of the home you want to access information from.
        :param device: The device from which you want to retrieve the value.
        :return: The temperature in Celsius of the specified device, or None if the reading could not be retrieved.
        """
        if home_label not in self._home_interfaces:
            return None
        _, h_i = self._home_interfaces[home_label]
        return h_i.thermostat_temperature if device == DeviceType.THERMOSTAT else h_i.valve_temperature

    def set_device(self, *, home_label: str,
                   device: DeviceType, mode: SetpointMode = SetpointMode.MANUAL,
                   temperature: Optional[int] = None, minutes: Optional[int] = None) -> bool:
        """
        Set a given device in a given home to a specific mode.
        :param home_label: The unique label of the home you want to access information from.
        :param device: The device to set to a specific mode.
        :param mode: The mode to set the device in.
        :param temperature: When using .MANUAL: the temperature to set the device to.
        :param minutes: When using .MAX or .MANUAL: the duration of this mode before the device reverts.
        :return: True if the API reported success, False otherwise.
        """
        if home_label not in self._home_interfaces:
            return False
        _, h_i = self._home_interfaces[home_label]
        return h_i.set_device(device=device, mode=mode, temperature=temperature, minutes=minutes)


# homes_api = Homes()
# sleep(1)
# print(homes_api.get_temperature("first_home", DeviceType.THERMOSTAT))
