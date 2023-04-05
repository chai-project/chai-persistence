# pylint: disable=line-too-long, missing-module-docstring, too-many-arguments

from typing import Optional

from chai_data_sources import Minutes
from chai_data_sources import NetatmoClient
from sqlalchemy.orm import scoped_session

from chai_persistence.home_persistence_thread import HomePersistenceThread


class HomeInterface:
    """
    Provide an interface to the Netatmo relay installed in a home, which itself starts the data collection thread.
    Unless stopped, the interface logs temperature according to the indicated interval.
    """
    _home_db_id: int
    _st_session: scoped_session
    _relay: NetatmoClient
    _thread: HomePersistenceThread

    def __init__(self, *, home_db_id: int, st_session: scoped_session,
                 netatmo_refresh_token: str, client_id: str, client_secret: str,
                 netatmo_target: Optional[str] = None,
                 interval: Minutes = Minutes.MIN_5):

        # set the variables related to this interface
        self._home_db_id = home_db_id
        self._st_session = st_session
        self._relay = NetatmoClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=netatmo_refresh_token,
            **({"target": netatmo_target} if netatmo_target else {})
        )

        # start a thread to log the temperature for both valve and thermostat, as well as the valve status
        self._thread = HomePersistenceThread(
            relay=self._relay,
            home_db_id=home_db_id,
            st_session=st_session,
            interval=interval
        )
        self._thread.start()

    def stop(self):
        """ Stop this interface from logging any data. """
        self._thread.stop()
