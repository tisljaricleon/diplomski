import argparse
import csv
import datetime as dt
import getpass
import os
import signal
import socket
import sys
import time

try:
    from jtop import jtop
except ImportError as exc:
    print("ERROR: jtop is not installed. Run: pip install jetson-stats", file=sys.stderr)
    raise SystemExit(1) from exc


STOP = False
SOURCE = f"{getpass.getuser()}@{socket.gethostname()}"


def _handle_signal(signum, frame):
    global STOP
    STOP = True


def _build_row(stats: dict) -> dict:
    return {
        "client_name": SOURCE,
        "timestamp": int(time.time() * 1000),
        "gpu_usage": stats.get("GPU"),
        "gpu_temperature": stats.get("Temp gpu"),
        "ram_usage": stats.get("RAM"),
        "swap_usage": stats.get("SWAP"),
    }


FIELDNAMES = [
    "client_name",
    "timestamp",
    "gpu_usage",
    "gpu_temperature",
    "ram_usage",
    "swap_usage",
]


def run(output_path: str, interval_s: float) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Always start a fresh log file for each run.
    if os.path.exists(output_path):
        os.remove(output_path)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        f.flush()

        print(f"{SOURCE}: writing to {output_path}, interval={interval_s}s (Ctrl+C to stop)")

        with jtop() as jetson:
            while not STOP and jetson.ok():
                writer.writerow(_build_row(jetson.stats))
                f.flush()
                time.sleep(interval_s)

    print(f"{SOURCE}: stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Log jtop device stats to CSV.")
    parser.add_argument(
        "--output", default="jtop_logs.csv",
        help="Output CSV file (default: jtop_logs.csv)",
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
