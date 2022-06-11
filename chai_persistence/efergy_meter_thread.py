# pylint: disable=line-too-long, missing-module-docstring, invalid-name, loop-invariant-statement, too-many-locals

import logging
from logging import debug
import threading
from typing import Optional, List, Tuple
import pendulum
from pendulum import now

from pause import until, sleep
from chai_data_sources import EfergyMeter, CurrentPower, Minutes, HistoricPower
from chai_data_sources.exceptions import EfergyError

log = logging.getLogger(__name__)  # get a module-level logger
log.addHandler(logging.NullHandler())  # add a no-op handler that can be modified by other code using this package


class EfergyMeterThread(threading.Thread):
    """
    This thread is cancellable by calling the stop() method.
    Collect Efergy meter readings on regular intervals using both the expiry date of a reading and a backoff strategy.
    Also perform the required binning, taking into account missing records, spurious values, and proper bin alignment.
    """
    _stop_event: threading.Event
    _meter: EfergyMeter
    _records: List[Tuple[pendulum.DateTime, CurrentPower]]  # store when we retrieved a record and what the record is
    _tz: str = "Europe/London"

    def __init__(self, meter: EfergyMeter):
        super().__init__()
        self._stop_event = threading.Event()
        self._meter = meter
        self._records = []

    @property
    def stopped(self) -> bool:
        """ Get whether this thread has been stopped. """
        return self._stop_event.is_set()

    def run(self):
        """ Start the execution of this thread in a blocking way. Call `start()` instead for a non-blocking thread. """
        token = self._meter.token
        while True:
            # pylint: disable=loop-try-except-usage
            if self.stopped:
                break

            # thread is still active, we can continue
            try:
                reading = self._meter.get_current()
                debug("got a new current reading: %s", reading)
                if reading not in [record for _, record in self._records]:  # make sure to not store duplicate records
                    self._records.append((now(self._tz), reading))
                    until(reading.expires.int_timestamp + 5)
                else:
                    sleep(2)  # sometimes the Efergy API isn't ready yet to send new values, wait it out a few seconds
            except EfergyError as exc:
                debug("received an error when trying to fetch the current reading - err: %s, token: %s", exc, token)

    def get_interval(self, minutes: Minutes) -> Optional[HistoricPower]:
        """
        Get a binned Efergy meter reading aligning with the specified minutes.
        :param minutes: The desired interval length.
        :return: The usage during the last minutes interval, during the current minutes interval if complete, or None
        """

        # determine the boundaries of the current and the previous interval
        time = now(self._tz)
        completed = time.minute // minutes.value  # number of times the minutes slot has already been filled this hour
        base = pendulum.datetime(time.year, time.month, time.day, time.hour, tz=self._tz)
        prev_start = base.add(minutes=(completed - 1) * minutes.value)
        prev_end = base.add(minutes=completed * minutes.value)
        # current_start = prev_end
        # current_end = base.add(minutes=(completed + 1) * minutes.value)

        # get the records that we retrieved in the current and previous interval
        previous_interval = [record for date, record in self._records if prev_start <= date <= prev_end]
        # current_interval = [record for date, record in self._records if current_start <= date <= current_end]

        debug("length of %s for interval %s – %s", str(len(previous_interval)),
              prev_start.isoformat(), prev_end.isoformat())
        debug("known entries: %s", [date.isoformat() for date, _ in self._records])

        expected = minutes.value * 60 // 30
        if len(previous_interval) < expected:
            debug("none of the intervals have the expected length")
            return None  # we don't have a complete set of records

        interval: List[CurrentPower] = previous_interval

        # calculate the value of the records in kWh
        contribution = sum({record.value / 3600 * 30 / 1000 for record in interval})
        contribution = contribution / len(interval) * expected  # correct for when we have too many records

        # keep only the new and still relevant records
        self._records = [(date, record) for date, record in self._records if date > prev_end]

        return HistoricPower(contribution, prev_start, prev_end)

    def stop(self):
        """ Cancel/stop the execution of this thread. """
        self._stop_event.set()
