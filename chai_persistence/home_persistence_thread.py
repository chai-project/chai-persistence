# pylint: disable=line-too-long, missing-module-docstring,
# pylint: disable=loop-invariant-statement, loop-try-except-usage, too-many-statements

import threading
from logging import debug

from chai_data_sources import EfergyMeter, Minutes, NetatmoClient
from chai_data_sources.exceptions import NetatmoError
from pause import until
from pendulum import now, datetime
from sqlalchemy.orm import Session, scoped_session

from chai_persistence.db_definitions import EfergyReading, NetatmoReading, db_session, Home
from chai_persistence.efergy_meter_thread import EfergyMeterThread


class HomePersistenceThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    _stop_event: threading.Event
    _efergy_thread: EfergyMeterThread
    _relay: NetatmoClient
    _home_db_id: int
    _st_session: scoped_session
    _interval: Minutes
    _tz: str = "Europe/London"

    def __init__(self, *, meter: EfergyMeter, relay: NetatmoClient,
                 home_db_id: int, st_session: scoped_session, interval: Minutes = Minutes.MIN_5):
        super().__init__()
        self._stop_event = threading.Event()
        # self._efergy_token = efergy_token
        # self._netatmo_token = netatmo_refresh_token
        self._efergy_thread = EfergyMeterThread(meter)
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
        self._efergy_thread.start()
        bootstrapped = False

        while True:
            if self.stopped:
                print("stopped")
                self._efergy_thread.stop()
                break

            # thread is still active, we can continue
            time = now(self._tz)
            completed = time.minute // self._interval.value  # number of times the slot has been filled this hour
            base = datetime(time.year, time.month, time.day, time.hour, tz=self._tz)
            current_start = base.add(minutes=completed * self._interval.value)
            current_end = base.add(minutes=(completed + 1) * self._interval.value)
            current_middle = base.add(minutes=(completed + 0.5) * self._interval.value)
            if not bootstrapped:
                # wait until the middle of an interval, either the current one or the next one
                middle = current_middle if time < current_middle else current_middle.add(minutes=self._interval.value)
                bootstrapped = True
                print(f"range: {current_start} – {current_end}")
                print(f"waiting until {middle.isoformat()} before continuing to align the logging")
                until(middle.int_timestamp)
                print("bootstrap complete")
                continue

            print("performing data polling")

            session: Session
            with db_session(self._st_session) as session:
                home: Home = session.query(Home).filter_by(id=self._home_db_id).one()
                print("got the home")
                try:
                    value = self._relay.thermostat_temperature
                    entry = NetatmoReading(relay=home.relay,
                                           start=current_start, end=current_end,
                                           room_type=1, reading=value)
                    print("prepared thermostat reading")
                    session.add(entry)
                    print("stored thermostat reading")
                except NetatmoError:
                    pass
                try:
                    value = self._relay.valve_temperature
                    entry = NetatmoReading(relay=home.relay,
                                           start=current_start, end=current_end,
                                           room_type=2, reading=value)
                    print("prepared valve reading")
                    session.add(entry)
                    print("stored valve reading")
                except NetatmoError:
                    pass
                power_usage = self._efergy_thread.get_interval(self._interval)
                if power_usage:
                    entry = EfergyReading(meter=home.meter,
                                          start=power_usage.start, end=power_usage.end,
                                          reading=power_usage.value)
                    print("prepared efergy reading")
                    session.add(entry)
                    print("stored efergy reading")
                print("storing in DB")
            print(f"next polling at {current_middle.add(minutes=self._interval.value)}")
            until(current_middle.add(minutes=self._interval.value).int_timestamp)

    def stop(self):
        """ Cancel/stop the execution of this thread. """
        self._stop_event.set()
