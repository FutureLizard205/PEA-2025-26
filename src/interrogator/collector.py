import time
from pathlib import Path
from typing import Optional, Callable

from . import csvreader
from .connection import InterrogatorConnection
from src.utils import log


class InterrogatorCollector:
    """Orchestrates data collection from the interrogator."""

    def __init__(self, connection: InterrogatorConnection):
        """
        Initialize collector with an interrogator connection.
        Also clears csvs folder.

        Args:
            connection: Connected InterrogatorConnection instance
        """
        self.connection = connection
        self._is_collecting = False
        csvreader.clear_csvs_folder()

    def collect_periodic(self,
                         duration_ms: int,
                         period_ms: int,
                         acqperiod_ms: int,
                         callback: Optional[Callable[[], None]] = csvreader.scan_csv) -> None:
        """
        Periodically collect data from interrogator.

        Args:
            duration_ms: Total collection duration in milliseconds
            period_ms: Time between start of each collection cycle
            acqperiod_ms: Duration of each acquisition window
            callback: Optional function called after each CSV is read

        Raises:
            ValueError: If period_ms < acqperiod_ms
            RuntimeError: If hardware communication fails
        """
        if period_ms < acqperiod_ms:
            raise ValueError(
                f"period_ms ({period_ms}) must be >= acqperiod_ms ({acqperiod_ms})"
            )

        duration_s = duration_ms / 1000.0
        period_s = period_ms / 1000.0
        acqperiod_s = acqperiod_ms / 1000.0

        t_start = time.perf_counter()
        iteration = 0
        self._is_collecting = True

        log(f"Starting periodic collection: {duration_ms}ms total, "
            f"{period_ms}ms period, {acqperiod_ms}ms acquisition")

        try:
            while self._is_collecting:
                t_target = t_start + (iteration * period_s)
                t_now = time.perf_counter()

                # Check if duration exceeded
                if t_now >= t_start + duration_s:
                    log(f"Collection complete after {iteration} iterations")
                    break

                # Timing compensation
                if t_now > t_target:
                    lag_ms = (t_now - t_target) * 1000
                    log(f"Warning: Iteration {iteration} is {lag_ms:.1f}ms behind")
                else:
                    sleep_time = t_target - t_now
                    if sleep_time > 0.0:
                        time.sleep(sleep_time)

                # Acquisition cycle
                try:
                    self.connection.start_peaks_collection()
                    t_acq_start = time.perf_counter()

                    time.sleep(acqperiod_s)

                    self.connection.stop_collection()

                    if callback:
                        callback()

                    acq_duration = time.perf_counter() - t_acq_start
                    log(f"Iteration {iteration}: took {acq_duration * 1000:.1f}ms")

                except Exception as e:
                    log(f"Error in iteration {iteration}: {e}")
                    # Continue to next iteration instead of crashing

                iteration += 1

        finally:
            self._is_collecting = False
            total_duration = time.perf_counter() - t_start
            log(f"Total time: {total_duration:.3f}s (target: {duration_s:.3f}s)")

    def collect_continuous(self,
                           duration_ms: int,
                           acqperiod_ms: int = 1000,
                           callback: Optional[Callable[[Path], None]] = None) -> None:
        """
        Continuously collect data with minimal gaps between acquisitions.

        Args:
            duration_ms: Total collection duration
            acqperiod_ms: Duration of each acquisition window
            callback: Optional function called after each CSV is read
        """
        # Minimal period = acquisition period (back-to-back collection)
        self.collect_periodic(duration_ms, acqperiod_ms, acqperiod_ms, callback)

    def stop(self):
        """Stop ongoing collection."""
        self._is_collecting = False
        log("Collection stop requested")