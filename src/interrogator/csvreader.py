import csv
from itertools import islice
import numpy as np
import os
from threading import Event
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from src.config import INTERROGATOR_CSVS_FOLDERNAME
from src.utils import log

NUM_CHANNELS = 4

def _average_wavelengths(input):
    """
    Recebe uma lista de blocos de 4 elementos cada.
    Cada elemento do bloco é uma lista de floats (pode estar vazia).
    Retorna um bloco único com a média de cada posição.
    """
    blocos_np = np.array(input, dtype=object)
    media = []
    for i in range(4):  # 4 posições por bloco
        # pega todos os elementos da posição i
        elems = [b[i] for b in blocos_np if len(b) > i and b[i] != 0]
        if elems:  # evita lista vazia
            # faz a média dos valores dentro de cada lista e depois entre blocos
            # primeiro transforma cada lista em array para somar elemento a elemento
            max_len = max(len(e) for e in elems)
            # preenche listas menores com NaN para alinhar tamanho
            arr = np.array([e + [np.nan] * (max_len - len(e)) for e in elems])
            media.append(np.nanmean(arr, axis=0).tolist())  # média ignorando NaN
        else:
            media.append([])  # mantém vazio se não houver dados

    bloco_arredondado = [[round(x, 4) for x in elem] if elem else [] for elem in media]
    return bloco_arredondado


def _validate_csv_file(file_path):
    """
    Check if CSV file has valid structure before processing.

    Returns:
        tuple: (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, "File does not exist"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if len(lines) < 2:  # Need at least header + 1 data row
            return False, "File too small (no data rows)"

        # Check if we have at least one complete block (header + 4 channels)
        if len(lines) < 1 + NUM_CHANNELS:
            return False, f"Insufficient rows (need at least {1 + NUM_CHANNELS})"

        return True, "OK"

    except Exception as e:
        return False, f"Error reading file: {e}"

"""
def _read_csv_peaks_to_wavelengths(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader) # ignore the first line (header)
        output = []

        while True:
            buffer = list(islice(reader, NUM_CHANNELS))  # reads up to NUM_CHANNELS lines from the iterator
            if not buffer or len(buffer) < 4:
                break

            # Date and Time
            print(f"\n{buffer[0][0]}")
            # Laser Temperature
            print(f"Laser Temperature: {buffer[0][2]}.{buffer[0][3]} ºC")


            for i in range(0,NUM_CHANNELS):
                print(f"Channel {buffer[i][1]}:")

                linha = buffer[i][4:] # ingores the first 4 arguments (date&time, channel and laser temperature)
                numbers = [x.strip('{}') for x in linha if x.strip('{}').isdigit()]
                # concatenate pairs integerpart.decimalpart
                values = [float(f"{numbers[i]}.{numbers[i + 1]}") for i in range(0, len(numbers) - 1, 2)]

                print(values)
                output.append(values)

    output_separate = [output[i:i + NUM_CHANNELS] for i in range(0, len(output), NUM_CHANNELS)]   # list comprehension
    return _average_wavelengths(output_separate)
"""

def _read_csv_peaks_to_wavelengths(file_path):
    #TODO: Check if the peak number is consistent
    """
    Read CSV file containing peak wavelength data.

    Args:
        file_path: Path to the CSV file

    Returns:
        List of averaged wavelengths per channel, or empty list if no valid data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    output = []

    try:
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)

            # Skip header
            try:
                next(reader)
            except StopIteration:
                print(f"Warning: Empty CSV file: {file_path}")
                return []

            while True:
                buffer = list(islice(reader, NUM_CHANNELS))

                # Check if we have enough data
                if not buffer:
                    break  # End of file

                if len(buffer) < NUM_CHANNELS:
                    # No need to print the warning if it's not the first block
                    #print(f"Warning: Incomplete data block (expected at least {NUM_CHANNELS} channels, got {len(buffer)})")
                    break

                # Validate that first row has minimum required fields
                # (6 is time + channel_num + laser_temp + 1_peak)
                if len(buffer[0]) < 6:
                    # No need to print the warning if it's not the first block
                    #print(f"Warning: Insufficient columns in data row (got {len(buffer[0])}, need at least 6)")
                    break

                # Date and Time
                print(f"\n{buffer[0][0]}")

                # Laser Temperature (safely access with bounds checking)
                try:
                    laser_temp = f"{buffer[0][2]}.{buffer[0][3]}"
                    print(f"Laser Temperature: {laser_temp} °C")
                except IndexError:
                    print("Warning: Laser temperature data missing")

                # Process each channel
                for i in range(NUM_CHANNELS):
                    print(f"Channel {buffer[i][1]}:")

                    # Check if there's data beyond the header columns
                    if len(buffer[i]) <= 4:
                        print("  No peak data")
                        output.append([])
                        continue

                    linha = buffer[i][4:]  # Skip first 4 columns

                    # Filter and extract numeric values
                    numbers = [x.strip('{}') for x in linha if x.strip('{}').isdigit()]

                    # Check if we have pairs of numbers
                    if len(numbers) < 2:
                        print("  No valid peak values")
                        output.append([])
                        continue

                    # Concatenate pairs: integer.decimal
                    values = [float(f"{numbers[i]}.{numbers[i + 1]}")
                              for i in range(0, len(numbers) - 1, 2)]

                    print(f"  {values}")
                    output.append(values)

    except Exception as e:
        print(f"Error reading CSV file {file_path}: {e}")
        raise ValueError(f"Failed to parse CSV file: {e}")

    # Check if we got any data
    if not output:
        print("Warning: No peak data found in CSV")
        return []

    # Separate into blocks and average
    output_separate = [output[i:i + NUM_CHANNELS]
                       for i in range(0, len(output), NUM_CHANNELS)]

    return _average_wavelengths(output_separate)

def _adc2db(adc_array, gain):
    gain_factor = (2.36161E-05, 1.50849E-05, 1.01289E-05, 6.4699E-06, 4.356E-06, 2.9059E-06)
    x = gain_factor[gain]
    adc_array = np.asarray(adc_array, dtype=np.float64)
    return (10.0 * np.log10(adc_array * x)).tolist()


def _read_csv_scpecturm(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # ignore the first line (header)
        output = []

        while True:
            buffer = list(islice(reader, NUM_CHANNELS))  # reads up to NUM_CHANNELS lines from the iterator
            if not buffer or len(buffer) < 4:
                break

            # Date and Time
            print(f"\n{buffer[0][0]}")
            # Laser Temperature
            print(f"Laser Temperature: {buffer[0][2]}.{buffer[0][3]} ºC")

            for i in range(0, NUM_CHANNELS):
                print(f"Channel {buffer[i][1]}:")

                linha = buffer[i][4:]  # ingores the first 4 arguments (date&time, channel and laser temperature)
                numbers = [x.strip('{}') for x in linha if x.strip('{}').isdigit()]
                # take only the integer parts, no float conversion needed
                values = [numbers[i] for i in range(0, len(numbers), 2)]

                print(values)
                output.append(values)

    output_db = [_adc2db(adc_array, 1) for adc_array in output] # conversion to dB

    import matplotlib.pyplot as plt

    x_min = 1528
    x_max = 1568

    # Generate x axis with same number of points
    x = np.linspace(x_min, x_max, len(output_db[0]))

    output_db[0].reverse() # Important
    plt.plot(x, output_db[0])  # line plot
    plt.ylabel("Amplitude (dB)")  # y-axis label
    plt.xlabel("Wavelength (nm)")
    plt.title("Spectrum")
    plt.grid(True)  # optional grid
    plt.show()


    return output_db


def _process_file(file_path):
    # Your processing code
    print(f"Processing {file_path}...")
    print(_read_csv_peaks_to_wavelengths(file_path))


def _wait_for_csv(folder_path):
    # First, check if any CSV already exists
    existing_files = sorted(f for f in os.listdir(folder_path) if f.endswith(".csv"))
    if existing_files:
        # Take the first CSV file (or sort if you want oldest/newest)
        file_path = os.path.join(folder_path, existing_files[0])
        print(f"Found existing CSV: {file_path}")
    else:
        # No CSV exists, start watching
        csv_detected = Event()
        csv_file = {"path": None}

        class CSVHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory and event.src_path.endswith(".csv"):
                    csv_file["path"] = event.src_path
                    csv_detected.set()

        observer = Observer()
        observer.schedule(CSVHandler(), folder_path, recursive=False)
        observer.start()

        print("Waiting for CSV file...")
        csv_detected.wait()  # block until a CSV is created
        observer.stop()
        observer.join()

        file_path = csv_file["path"]

    # Wait until the file is no longer used by any process
    while True:
        try:
            # Try to open the file exclusively
            fd = os.open(file_path, os.O_RDWR | os.O_EXCL)
            os.close(fd)
            break  # file is free to process
        except OSError:
            time.sleep(0.1)  # still in use

    print(f"Detected CSV file: {file_path}")

    # Validate before processing
    is_valid, error_msg = _validate_csv_file(file_path)
    if not is_valid:
        print(f"Warning: Invalid CSV file: {error_msg}")
        os.remove(file_path)  # Clean up invalid file
        print(f"Deleted invalid file: {file_path}")
        return None  # or raise exception, depending on your needs

    # Process the file
    _process_file(file_path)
    os.remove(file_path)
    print(f"Processed and deleted: {file_path}")


def scan_csv():
    _wait_for_csv(INTERROGATOR_CSVS_FOLDERNAME)

def clear_csvs_folder():
    try:
        for f in os.listdir(INTERROGATOR_CSVS_FOLDERNAME):
            os.remove(os.path.join(INTERROGATOR_CSVS_FOLDERNAME, f))
    except Exception as e:
        log(f"Warning: Tried to clear csvs folder but got an error: {e}")

if __name__ == "__main__":
    # Example usage:
    #_wait_for_csv("../csvs")  # blocks until a CSV file is created
    # next call will start watching again
    _read_csv_scpecturm("spec.csv")
    #clear_csvs_folder()
