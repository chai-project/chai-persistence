# pylint: disable=line-too-long, missing-module-docstring, too-many-arguments

from typing import Optional

import pendulum
from chai_data_sources import EfergyMeter, CurrentPower
from chai_data_sources import Minutes
from chai_data_sources import NetatmoClient, DeviceType, SetpointMode
from sqlalchemy.orm import scoped_session, Session

from chai_persistence.db_definitions import SetpointChange, Home
from chai_persistence.home_persistence_thread import HomePersistenceThread, db_session


class HomeInterface:
    """
    Provide a simple interface to the Efergy meter and Netatmo relay installed in a home.
    Unless stopped, the interface also logs power and temperature according to the indicated interval.
    """
    _meter: EfergyMeter
    _relay: NetatmoClient
    _thread: HomePersistenceThread
    _home_db_id: int
    _st_session: scoped_session

    def __init__(self, *, home_db_id: int, st_session: scoped_session,
                 efergy_token: str,
                 netatmo_refresh_token: str, client_id: str, client_secret: str,
                 efergy_target: Optional[str] = None, netatmo_target: Optional[str] = None,
                 interval: Minutes = Minutes.MIN_5):
        self._home_db_id = home_db_id
        self._st_session = st_session
        self._meter = EfergyMeter(token=efergy_token, **({"target": efergy_target} if efergy_target else {}))
        self._relay = NetatmoClient(client_id=client_id, client_secret=client_secret,
                                    refresh_token=netatmo_refresh_token,
                                    **({"target": netatmo_target} if netatmo_target else {}))
        # start a thread that:
        #  - logs the power use (and convert it after binning)
        #  - logs the temperature for both valve and thermostat
        self._thread = HomePersistenceThread(meter=self._meter, relay=self._relay,
                                             home_db_id=home_db_id, st_session=st_session, interval=interval)
        self._thread.start()
        print(f"started interface for home with database ID {home_db_id}")

    @property
    def power_current(self) -> CurrentPower:
        """ The current power reading in W. """
        return self._meter.current

    @property
    def thermostat_temperature(self) -> float:
        """ The temperature reported by the Netatmo thermostat/cube. """
        return self._relay.thermostat_temperature

    @property
    def valve_temperature(self) -> float:
        """ The temperature reported by the Netatmo thermostatic valve. """
        return self._relay.valve_temperature

    # TODO: depending on use in project this can be an interface to the on/off or to the specific setpoint change
    def set_device(self, *, device: DeviceType, mode: SetpointMode = SetpointMode.MANUAL,
                   temperature: Optional[int] = None, minutes: Optional[int] = None) -> bool:
        """
        Set a given device to a specific mode.
        :param device: The device to set to a specific mode.
        :param mode: The mode to set the device in.
        :param temperature: When using .MANUAL: the temperature to set the device to.
        :param minutes: When using .MAX or .MANUAL: the duration of this mode before the device reverts.
        :return: True if the API reported success, False otherwise.
        """
        result = self._relay.set_device(device=device, mode=mode, temperature=temperature, minutes=minutes)
        if result:
            session: Session
            with db_session(self._st_session) as session:
                home: Home = session.query(Home).filter_by(id=self._home_db_id).one()
                entry = SetpointChange(netatmo_id=home.netatmo_id, time=pendulum.now("Europe/London"),
                                       room_type=(1 if device == DeviceType.THERMOSTAT else 2), mode=mode.name,
                                       temperature=temperature, duration=minutes)
                session.add(entry)
        return result

    def stop(self):
        """ Stop this interface from logging any data. """
        self._thread.stop()
