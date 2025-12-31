from contextlib import nullcontext
from src.utils import log, suppress_output
from pathlib import Path
import time
from src.config import SUPPRESS_INTERROGATOR_PRINTS, INTERROGATOR_CSVS_FOLDERNAME

NUM_CHANNELS = 4

class InterrogatorConnection:
    """Manages connection and data collection for M4 Interrogator."""

    def __init__(self,
                 dll_path: str = "./M4Interface_NET.dll",
                 max_connection_attempts: int = 10,
                 retry_delay_seconds: int = 3):
        self.dll_path = dll_path
        self.max_connection_attempts = max_connection_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self._mxlib = None
        self._data_export_type = None
        self._connected = False
        self._configured = False

    def connect(self) -> None:
        """Initialize and connect to the interrogator."""
        if self._connected:
            log("Already connected")
            return

        self._initialize_dll()
        self._establish_connection()
        self._connected = True

    def _initialize_dll(self) -> None:
        """Load the .NET DLL and initialize types."""
        if not Path(self.dll_path).exists():
            raise FileNotFoundError(f"DLL not found: {self.dll_path}")

        import sys
        sys.path.append(str(Path(self.dll_path).parent))

        # noinspection PyUnresolvedReferences
        from clr import AddReference
        AddReference("M4Interface_NET")

        # noinspection PyUnresolvedReferences
        import M4Interface_NET
        self._data_export_type = M4Interface_NET.DataExportType
        self._mxlib = M4Interface_NET.MXLIB()

        log(f"Initialized MXLIB version {self._mxlib.version()}")

    def _establish_connection(self) -> None:
        """Attempt to connect to the interrogator with retries."""
        log("Connecting to interrogator...")
        for attempt in range(self.max_connection_attempts):
            try:
                with (suppress_output() if SUPPRESS_INTERROGATOR_PRINTS else nullcontext()):
                    dp = self._mxlib.connect()

                if dp.Ready:
                    log(f"Interrogator ready! LibVersion: {dp.LibVersion}, "
                        f"FW: {dp.Version}, Serial: {dp.BoardNo}")
                    return
            except Exception as e:
                ...#log(f"Connection attempt {attempt + 1} failed: {e}")

            if attempt < self.max_connection_attempts - 1:
                log(f"Failed to connect to interrogator. Retrying in {self.retry_delay_seconds} s...")
                time.sleep(self.retry_delay_seconds)

        raise ConnectionError(f"Failed to connect after {self.max_connection_attempts} attempts")



    def configure(self,
                  output_divider: int,
                  max_samples_per_file: int,
                  threshold: float = -20.0,
                  gain: int = 1,
                  bandwidth: float = 60,
                  output_path: Path = None) -> None:
        """Configure interrogator parameters."""
        self._ensure_connected()

        if output_path is None:
            output_path = Path().resolve().joinpath(INTERROGATOR_CSVS_FOLDERNAME)

        self._create_parameters_file(output_path, output_divider, max_samples_per_file)
        self._mxlib.ReadParamsFile()

        for channel in range(1,NUM_CHANNELS):
            self._mxlib.setThreshold(channel, threshold)
            self._mxlib.setGain(channel, gain)
        self._mxlib.SetBandwidth(bandwidth)

        self._configured = True
        log("Configured interrogator parameters")

    def start_peaks_collection(self) -> None:
        """Start collecting peak data."""
        self._ensure_connected()
        self._ensure_configured()

        result = self._mxlib.EnableExport(self._data_export_type.FILE_PEAK, True)
        if not result:
            raise RuntimeError("Failed to enable peaks collection")
        #log(f"EnableExport (Peaks): {result}")
        self._mxlib.getPeaks()

    def start_spectrum_collection(self) -> None:
        """Start collecting spectrum data."""
        self._ensure_connected()
        self._ensure_configured()

        result = self._mxlib.EnableExport(self._data_export_type.FILE_SPEC, True)
        if not result:
            raise RuntimeError("Failed to enable spectrum collection")
        #log(f"EnableExport (Spectrum): {result}")
        self._mxlib.startWaveScan()
        self._mxlib.getSpectrum()

    def stop_collection(self) -> None:
        """Stop data collection (either spectrum or peaks)."""
        self._ensure_connected()
        self._ensure_configured()

        self._mxlib.stopWaveMode()
        self._mxlib.EnableExport(self._data_export_type.FILE_PEAK, False)
        self._mxlib.EnableExport(self._data_export_type.FILE_SPEC, False)

    def disconnect(self) -> None:
        """Close connection to the interrogator."""
        if self._connected and self._mxlib:
            self._mxlib.Close()
            self._connected = False
            log("Disconnected from interrogator")

        self._delete_parameter_file()

    def _ensure_connected(self) -> None:
        """Verify connection exists before operations."""
        if not self._connected or self._mxlib is None:
            raise RuntimeError("Tried to use interrogator without being connected to it. Call connect() first.")

    def _ensure_configured(self) -> None:
        """Verify interrogator has been configured before operations."""
        if not self._configured:
            raise RuntimeError("Tried to use interrogator without being configured. Call configure() first.")

    def __enter__(self):
        """Context manager support."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure cleanup on context exit."""
        self.disconnect()

    @staticmethod
    def _create_parameters_file(output_path: Path,
                                output_divider: int,
                                output_max_entries: int,
                                ip: str = "192.168.0.19",
                                tx_port: int = 4567,
                                rx_port: int = 8001,
                                param_file_path: Path = Path("parameter.txt")) -> None:
        """Generate parameter configuration file."""
        # ... (same content generation, but with configurable params)
        content = f"""[Interrogator-Settings]
IP={ip}
TxPort={tx_port}
RxPort={rx_port}

[File-Peaks]
Path={output_path}
Divider={output_divider}
MaxEntries={output_max_entries}

[File-Sensor]
Path=E:\\
Divider=1
MaxEntries=100

[File-Spectrum]
Path={output_path}
Divider={output_divider}
MaxEntries={output_max_entries}

[Server-Peaks]
URL=192.168.0.111
Interval=100
Divider=100
MaxEntries=10

[Server-Spectrum]
URL=192.168.0.14
Divider=10
MaxEntries=10

[Coefficients]
Ta=0.00000301
Tb=0.00000402
Tc=0.00000503

[Channel-01]
Threshold=-19
Gain=3

[Channel-02]
Threshold=-22.36

[Ref-Peak:1]
Name=p1
Channel=1
refWL=1534.9
LowWL=1530
HighWL=1535.1
EnableReset=yes"""

        try:
            with open(param_file_path, "w") as f:
                f.write(content)
            log(f"Parameter file created successfully at {param_file_path}")
        except PermissionError:
            raise IOError(f"Permission denied writing to {param_file_path}")
        except IOError as e:
            raise IOError(f"Failed to write parameter file to {param_file_path}: {e}")

    @staticmethod
    def _delete_parameter_file(param_file_path: Path = Path("parameter.txt")) -> None:
        """
        Delete the parameter configuration file.

        Args:
            param_file_path: Path to the parameter file to delete
        """
        try:
            param_file = Path(param_file_path)
            if param_file.exists():
                param_file.unlink()
                log(f"Parameter file deleted: {param_file_path}")
            else:
                log(f"Parameter file not found (already deleted?): {param_file_path}")
        except PermissionError:
            log(f"Warning: Permission denied deleting parameter file: {param_file_path}")
        except Exception as e:
            log(f"Warning: Failed to delete parameter file {param_file_path}: {e}")