# pylint: disable=line-too-long, missing-module-docstring,
# pylint: disable=loop-invariant-statement, loop-try-except-usage, too-many-statements

import threading
from logging import debug

from chai_data_sources import Minutes, NetatmoClient
from chai_data_sources.exceptions import NetatmoError
from pause import until
from pendulum import now, datetime
from sqlalchemy.orm import Session, scoped_session

from chai_persistence.db_definitions import NetatmoReading, db_session, Home


class HomePersistenceThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    _stop_event: threading.Event
    _relay: NetatmoClient
    _home_db_id: int
    _st_session: scoped_session
    _interval: Minutes
    _tz: str = "Europe/London"

    def __init__(self, *,
                 relay: NetatmoClient, home_db_id: int, st_session: scoped_session, interval: Minutes = Minutes.MIN_5):
        super().__init__()
        self._stop_event = threading.Event()
        self._relay = relay
        self._home_db_id = home_db_id
        self._st_session = st_session
        self._interval = interval

    @property
    def stopped(self) -> bool:
        """ Get whether this thread has been stopped. """
        return self._stop_event.is_set()

    def run(self):
        """ Start the execution of this thread in a blocking way. Call `start()` instead for a non-blocking thread. """
        debug("starting run for home with DB id %s", self._home_db_id)
        bootstrapped = False

        while True:
            if self.stopped:
                print(f"  stopped thread for home with ID {self._home_db_id}")
                break

            # thread is still active, we can continue
            time = now(self._tz)
            completed = time.minute // self._interval.value  # number of times the slot has been filled this hour
            base = datetime(time.year, time.month, time.day, time.hour, tz=self._tz)
            current_start = base.add(minutes=completed * self._interval.value)
            current_end = base.add(minutes=(completed + 1) * self._interval.value)
            current_mid = base.add(minutes=(completed + 0.5) * self._interval.value)
            try:
                if not bootstrapped:
                    # wait until the middle of an interval, either the current one or the next one
                    middle = current_mid if time < current_mid else current_mid.add(minutes=self._interval.value)
                    bootstrapped = True

                    debug("range:  %s – %s", current_start.isoformat(), current_end.isoformat())
                    debug("waiting until %s before continuing to align the logging", middle.isoformat())
                    until(middle.int_timestamp)
                    debug("bootstrap complete")
                    continue

                debug("performing data polling")

                session: Session
                with db_session(self._st_session) as session:
                    home: Home = session.query(Home).filter_by(id=self._home_db_id).one()
                    debug("got the home instance")
                    try:
                        value = self._relay.thermostat_temperature
                        # noinspection PyTypeChecker
                        # ignore the warnings; DateTime is a datetime.datetime (compatible) instance
                        entry = NetatmoReading(room_id=1, relay=home.relay,
                                               start=current_start, end=current_end, reading=value)
                        debug("prepared thermostat reading")
                        session.add(entry)
                        debug("stored thermostat reading")
                    except NetatmoError:
                        pass
                    try:
                        value = self._relay.valve_temperature
                        # noinspection PyTypeChecker
                        # ignore the warnings; DateTime is a datetime.datetime (compatible) instance
                        entry = NetatmoReading(room_id=2, relay=home.relay,
                                               start=current_start, end=current_end, reading=value)
                        debug("prepared valve reading")
                        session.add(entry)
                        debug("stored valve reading")
                    except NetatmoError:
                        pass
                    try:
                        value = self._relay.valve_percentage
                        # noinspection PyTypeChecker
                        # ignore the warnings; DateTime is a datetime.datetime (compatible) instance
                        entry = NetatmoReading(room_id=3, relay=home.relay,
                                               start=current_start, end=current_end, reading=value)
                        debug("prepared valve status reading")
                        session.add(entry)
                        debug("stored valve status reading")
                    except NetatmoError:
                        pass
                    debug("storing in DB")
            except Exception as err:
                debug(f"Encountered an unexpected and unhandled error: {err}\nSaving the thread by ignoring the error.")
            debug(f"next polling at %s", current_mid.add(minutes=self._interval.value).isoformat())
            until(current_mid.add(minutes=self._interval.value).int_timestamp)

    def stop(self):
        """ Cancel/stop the execution of this thread. """
        self._stop_event.set()
