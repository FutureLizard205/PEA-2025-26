import interrogator
import src.utils as utils
import time

def _init():
    print("[Data Gathering]")
    utils.init_log_file()

if __name__ == "__main__":
    _init()

    with interrogator.InterrogatorConnection() as conn:
        """
        conn.configure(100, 10, ) # Interval here is supposed to be 100ms, but is acting as if 1000ms
        conn.start_peaks_collection()
        time.sleep(6)
        conn.stop_collection()
        """

        """
        conn.configure(1, 10, ) # Interval here is supposed to be 1ms, but is acting as if 1000ms
        conn.start_spectrum_collection()
        time.sleep(6)
        conn.stop_collection()"""

        # TODO: CSV file is not deleted if no peaks are detected
        # TODO: Better function documentation












        conn.configure(output_divider=10, max_samples_per_file=100)

        # Create collector
        collector = interrogator.InterrogatorCollector(conn)

        # Periodic collection
        collector.collect_periodic(
            duration_ms=20000,
            period_ms=1000,
            acqperiod_ms=500
        )