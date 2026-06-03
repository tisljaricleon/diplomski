import argparse
import csv
import datetime
import getpass
import os
import signal
import socket
import sys
import time

try:
    import psutil
except ImportError as exc:
    print("ERROR: psutil is not installed. Run: pip install psutil", file=sys.stderr)
    raise SystemExit(1) from exc


STOP = False
SOURCE = f"{getpass.getuser()}@{socket.gethostname()}"


def _handle_signal(signum, frame):
    global STOP
    STOP = True


def _cpu_temp() -> float | None:
    """Read CPU temperature from sysfs thermal zones."""
    try:
        # Try psutil first (works on most Linux)
        temps = psutil.sensors_temperatures()
        for key in ("cpu_thermal", "cpu-thermal", "coretemp", "thermal_zone0"):
            if key in temps and temps[key]:
                return temps[key][0].current
        # Fallback: first available zone
        for zones in temps.values():
            if zones:
                return zones[0].current
    except (AttributeError, OSError):
        pass
    # Direct sysfs fallback
    for i in range(10):
        path = f"/sys/class/thermal/thermal_zone{i}/temp"
        try:
            with open(path) as f:
                return int(f.read().strip()) / 1000.0
        except OSError:
            continue
    return None


def _build_row() -> dict:
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    ram_ratio = vm.used / vm.total if vm.total else None
    swap_ratio = sw.used / sw.total if sw.total else None
    return {
        "client_name": SOURCE,
        "timestamp": int(time.time() * 1000),
        "cpu_usage": psutil.cpu_percent(),
        "cpu_temperature": _cpu_temp(),
        "ram_usage": ram_ratio,
        "swap_usage": swap_ratio,
    }


FIELDNAMES = [
    "client_name",
    "timestamp",
    "cpu_usage",
    "cpu_temperature",
    "ram_usage",
    "swap_usage",
]


def run(output_path: str, interval_s: float) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        f.flush()

        print(f"{SOURCE}: writing to {output_path}, interval={interval_s}s (Ctrl+C to stop)")

        while not STOP:
            writer.writerow(_build_row())
            f.flush()
            time.sleep(interval_s)

    print(f"{SOURCE}: stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Log device stats to CSV (Raspberry Pi).")
    _ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    parser.add_argument(
        "--output", default=f"rpi_logs_{_ts}.csv",
        help="Output CSV file (default: rpi_logs_<timestamp>.csv)",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Sampling interval in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    if args.interval <= 0:
        print("ERROR: --interval must be > 0", file=sys.stderr)
        raise SystemExit(2)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    run(args.output, args.interval)


if __name__ == "__main__":
    main()
