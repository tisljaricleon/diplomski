"""
analyze.py  –  Generate evaluation graphs for FL inference proxy experiments.

Usage examples:

  # Plot 1 & 2: latency & error rate comparison (requires request CSVs)
  python analyze.py latency --scenarios baseline no_proxy with_proxy --rounds rounds_no_proxy.csv rounds_with_proxy.csv

  # Plot 3: FL round duration comparison (requires two rounds CSVs)
  python analyze.py rounds --labels "Bez preusmjeravanja" "S preusmjeravanjem" --files rounds_no_proxy.csv rounds_with_proxy.csv

  # Plot 4: FL accuracy convergence (requires two rounds CSVs)
  python analyze.py accuracy --labels "Bez selekcije" "Sa selekcijom" --files rounds_no_selection.csv rounds_with_selection.csv

    # Plot 5: Runtime metrics (Jetson + proxy)
    python analyze.py runtime --scenarios baseline no_proxy with_proxy

  # Run all plots at once
  python analyze.py all \
    --request-csvs baseline no_proxy with_proxy \
    --rounds-files rounds_no_proxy.csv rounds_with_proxy.csv \
    --rounds-labels "Bez preusmjeravanja" "S preusmjeravanjem" \
    --accuracy-files rounds_no_selection.csv rounds_with_selection.csv \
    --accuracy-labels "Bez selekcije" "Sa selekcijom"
"""

import argparse
import csv
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict


# ---------------------------------------------------------------------------
# CSV loaders
# ---------------------------------------------------------------------------

def load_requests(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        print(f"[WARN] File not found: {csv_path}")
        return []
    rows = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                row["timestamp"] = int(row["timestamp"])
                row["latency"] = float(row["latency"])
                row["status"] = int(row["status"])
                row["rate"] = int(row["rate"]) if row.get("rate") else 0
                row["is_training"] = row.get("is_training", "False").strip().lower() in ("true", "1")
            except (ValueError, KeyError):
                continue
            rows.append(row)
    return rows


def load_rounds(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        print(f"[WARN] File not found: {csv_path}")
        return []
    rows = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                row["round"] = int(row["round"])
                row["start_ts_ms"] = int(row["start_ts_ms"])
                row["end_ts_ms"] = int(row["end_ts_ms"])
                row["duration_s"] = float(row["duration_s"])
                row["num_clients_selected"] = int(row["num_clients_selected"])
                row["loss"] = float(row["loss"]) if row.get("loss") else None
                row["accuracy"] = float(row["accuracy"]) if row.get("accuracy") else None
            except (ValueError, KeyError):
                continue
            rows.append(row)
    return rows


def _to_float_maybe(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    # jtop can return values like "23%" or "53 C"
    s = s.replace("%", "").replace("C", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def load_runtime_metrics(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        print(f"[WARN] File not found: {csv_path}")
        return []
    rows = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                row["timestamp"] = int(row["timestamp"])
                row["is_training"] = str(row.get("is_training", "False")).strip().lower() in ("true", "1")
                row["gpu_usage"] = _to_float_maybe(row.get("gpu_usage"))
                row["gpu_temperature"] = _to_float_maybe(row.get("gpu_temperature"))
                row["ram_usage"] = _to_float_maybe(row.get("ram_usage"))
                row["inflight_60s_avg"] = _to_float_maybe(row.get("inflight_60s_avg"))
                row["inflight_requests"] = _to_float_maybe(row.get("inflight_requests"))
                row["inflight_60s_max"] = _to_float_maybe(row.get("inflight_60s_max"))
            except (ValueError, KeyError):
                continue
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCENARIO_COLORS = ["#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0"]
TRAINING_SHADE = "#FFF9C4"  # light yellow for training periods


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    return float(np.percentile(values, p))


def _mark_training_rounds(ax, rounds: list[dict], y_min: float, y_max: float):
    """Shade background during FL training rounds."""
    for r in rounds:
        t_start = r["start_ts_ms"] / 1000.0
        t_end = r["end_ts_ms"] / 1000.0
        ax.axvspan(t_start, t_end, alpha=0.25, color="orange", zorder=0)


# ---------------------------------------------------------------------------
# Plot 1 + 2: Latency & Error Rate over time (per scenario, with training shading)
# ---------------------------------------------------------------------------

def plot_latency_and_errors(
    scenario_names: list[str],
    rounds_files: list[str],
    output_dir: str = ".",
    window_s: float = 15.0,
):
    """
    For each scenario, loads request_data_{scenario}.csv.
    Plots:
      - p50/p95 latency rolling window over time
      - Error rate (non-200 requests) rolling window over time
    Shades FL training rounds (from rounds_files[i], matched to scenario by index).
    Generates two PNG files: latency_comparison.png and error_rate_comparison.png.
    """
    fig_lat, ax_lat = plt.subplots(figsize=(14, 6))
    fig_err, ax_err = plt.subplots(figsize=(14, 5))

    ax_lat.set_xlabel("Relativno vrijeme (s)")
    ax_lat.set_ylabel("Latencija (s)")
    ax_lat.set_title("p95 latencija inference zahtjeva po scenariju")

    ax_err.set_xlabel("Relativno vrijeme (s)")
    ax_err.set_ylabel("Stopa grešaka (%)")
    ax_err.set_title("Stopa grešaka inference zahtjeva po scenariju")

    for idx, scenario in enumerate(scenario_names):
        csv_path = os.path.join(output_dir, f"request_data_{scenario}.csv")
        rows = load_requests(csv_path)
        if not rows:
            print(f"[SKIP] No data for scenario '{scenario}'")
            continue

        color = SCENARIO_COLORS[idx % len(SCENARIO_COLORS)]

        # Normalise timestamps to seconds from experiment start
        t0 = min(r["timestamp"] for r in rows) / 1000.0
        times = [(r["timestamp"] / 1000.0) - t0 for r in rows]
        latencies = [r["latency"] for r in rows]
        errors = [0 if r["status"] == 200 else 1 for r in rows]

        t_max = max(times)
        bucket_starts = np.arange(0, t_max, window_s / 2)

        win_times, win_p95, win_err = [], [], []
        for bs in bucket_starts:
            be = bs + window_s
            mask = [bs <= t < be for t in times]
            window_lat = [latencies[i] for i, m in enumerate(mask) if m and latencies[i] >= 0]
            window_err = [errors[i] for i, m in enumerate(mask) if m]
            if window_lat:
                win_times.append(bs + window_s / 2)
                win_p95.append(_percentile(window_lat, 95))
                win_err.append(100.0 * sum(window_err) / len(window_err) if window_err else 0.0)

        ax_lat.plot(win_times, win_p95, label=scenario, color=color, linewidth=2)
        ax_err.plot(win_times, win_err, label=scenario, color=color, linewidth=2)

        # Shade training periods if rounds file provided for this scenario
        if idx < len(rounds_files) and rounds_files[idx]:
            rounds = load_rounds(rounds_files[idx])
            for r in rounds:
                r_start = (r["start_ts_ms"] / 1000.0) - t0
                r_end = (r["end_ts_ms"] / 1000.0) - t0
                ax_lat.axvspan(r_start, r_end, alpha=0.12, color=color, zorder=0)
                ax_err.axvspan(r_start, r_end, alpha=0.12, color=color, zorder=0)

    training_patch = mpatches.Patch(color="gray", alpha=0.3, label="FL runde (treniranje aktivno)")
    handles_lat, labels_lat = ax_lat.get_legend_handles_labels()
    ax_lat.legend(handles=handles_lat + [training_patch])
    ax_lat.grid(True, alpha=0.3)
    fig_lat.tight_layout()
    out_lat = os.path.join(output_dir, "latency_comparison.png")
    fig_lat.savefig(out_lat, dpi=150)
    print(f"[SAVED] {out_lat}")

    handles_err, labels_err = ax_err.get_legend_handles_labels()
    ax_err.legend(handles=handles_err + [training_patch])
    ax_err.grid(True, alpha=0.3)
    fig_err.tight_layout()
    out_err = os.path.join(output_dir, "error_rate_comparison.png")
    fig_err.savefig(out_err, dpi=150)
    print(f"[SAVED] {out_err}")

    plt.close("all")

    # Print degradation summary table
    print("\n=== Degradacija p95 latencije (za vrijeme treniranja vs baseline) ===")
    baseline_p95 = None
    for idx, scenario in enumerate(scenario_names):
        csv_path = os.path.join(output_dir, f"request_data_{scenario}.csv")
        rows = load_requests(csv_path)
        if not rows:
            continue
        training_lat = [r["latency"] for r in rows if r["latency"] >= 0 and r["is_training"]]
        all_lat = [r["latency"] for r in rows if r["latency"] >= 0]
        p95_training = _percentile(training_lat, 95) if training_lat else float("nan")
        p95_all = _percentile(all_lat, 95)
        if scenario == "baseline" or baseline_p95 is None:
            baseline_p95 = p95_all
        degradation = ((p95_training / baseline_p95) - 1) * 100 if baseline_p95 else float("nan")
        err_rate = 100.0 * sum(1 for r in rows if r["status"] != 200) / len(rows) if rows else 0
        print(f"  {scenario:<25} p95(treniranje)={p95_training:.3f}s  p95(ukupno)={p95_all:.3f}s  degradacija={degradation:+.1f}%  error_rate={err_rate:.1f}%")


# ---------------------------------------------------------------------------
# Plot 3: FL Round Duration
# ---------------------------------------------------------------------------

def plot_round_duration(
    labels: list[str],
    files: list[str],
    output_dir: str = ".",
):
    """Bar chart comparing per-round duration across scenarios."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_xlabel("FL runda")
    ax.set_ylabel("Trajanje runde (s)")
    ax.set_title("Trajanje FL rundi po scenariju")

    all_rounds = []
    for label, fpath in zip(labels, files):
        rounds = load_rounds(fpath)
        if not rounds:
            print(f"[SKIP] No rounds data in {fpath}")
            continue
        all_rounds.append((label, rounds))

    if not all_rounds:
        print("[SKIP] No round data available for plot_round_duration")
        return

    max_round = max(r["round"] for _, rs in all_rounds for r in rs)
    x = np.arange(1, max_round + 1)
    width = 0.8 / len(all_rounds)

    for idx, (label, rounds) in enumerate(all_rounds):
        dur_by_round = {r["round"]: r["duration_s"] for r in rounds}
        durations = [dur_by_round.get(rnd, 0) for rnd in x]
        offset = (idx - len(all_rounds) / 2 + 0.5) * width
        color = SCENARIO_COLORS[idx % len(SCENARIO_COLORS)]
        bars = ax.bar(x + offset, durations, width=width, label=label, color=color, alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels([str(i) for i in x])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # Print average durations
    print("\n=== Prosječno trajanje FL runde ===")
    for label, rounds in all_rounds:
        avg = sum(r["duration_s"] for r in rounds) / len(rounds)
        print(f"  {label:<35} avg={avg:.1f}s  (n={len(rounds)} rundi)")

    fig.tight_layout()
    out = os.path.join(output_dir, "round_duration.png")
    fig.savefig(out, dpi=150)
    print(f"[SAVED] {out}")
    plt.close("all")


# ---------------------------------------------------------------------------
# Plot 4: FL Accuracy Convergence
# ---------------------------------------------------------------------------

def plot_accuracy(
    labels: list[str],
    files: list[str],
    output_dir: str = ".",
):
    """Line chart of server-side accuracy per round, one line per scenario."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    ax_acc, ax_loss = axes
    ax_acc.set_xlabel("FL runda")
    ax_acc.set_ylabel("Točnost modela (%)")
    ax_acc.set_title("Točnost FL modela po rundi")
    ax_loss.set_xlabel("FL runda")
    ax_loss.set_ylabel("Gubitak (loss)")
    ax_loss.set_title("Gubitak FL modela po rundi")

    print("\n=== Konvergencija modela ===")
    for idx, (label, fpath) in enumerate(zip(labels, files)):
        rounds = load_rounds(fpath)
        if not rounds:
            print(f"[SKIP] No data in {fpath}")
            continue
        rounds_with_acc = [r for r in rounds if r["accuracy"] is not None]
        if not rounds_with_acc:
            print(f"[SKIP] No accuracy entries in {fpath}")
            continue

        x = [r["round"] for r in rounds_with_acc]
        acc = [r["accuracy"] * 100.0 for r in rounds_with_acc]
        loss = [r["loss"] for r in rounds_with_acc if r["loss"] is not None]
        color = SCENARIO_COLORS[idx % len(SCENARIO_COLORS)]

        ax_acc.plot(x, acc, marker="o", label=label, color=color, linewidth=2)
        if loss:
            ax_loss.plot(x, loss, marker="o", label=label, color=color, linewidth=2)

        final_acc = acc[-1] if acc else float("nan")
        print(f"  {label:<35} finalna točnost={final_acc:.2f}%  rundi={len(rounds_with_acc)}")

    ax_acc.legend()
    ax_acc.grid(True, alpha=0.3)
    ax_acc.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.1f}%"))
    ax_loss.legend()
    ax_loss.grid(True, alpha=0.3)

    fig.tight_layout()
    out = os.path.join(output_dir, "accuracy_convergence.png")
    fig.savefig(out, dpi=150)
    print(f"[SAVED] {out}")
    plt.close("all")


def plot_runtime_metrics(
    scenario_names: list[str],
    output_dir: str = ".",
):
    """Plot Jetson resource and proxy inflight metrics from runtime_metrics_{scenario}.csv."""
    fig_gpu, ax_gpu = plt.subplots(figsize=(14, 5))
    fig_proxy, ax_proxy = plt.subplots(figsize=(14, 5))

    ax_gpu.set_xlabel("Relativno vrijeme (s)")
    ax_gpu.set_ylabel("GPU usage (%)")
    ax_gpu.set_title("GPU opterećenje po scenariju")

    ax_proxy.set_xlabel("Relativno vrijeme (s)")
    ax_proxy.set_ylabel("Inflight zahtjevi")
    ax_proxy.set_title("Proxy inflight_60s_avg po scenariju")

    for idx, scenario in enumerate(scenario_names):
        csv_path = os.path.join(output_dir, f"runtime_metrics_{scenario}.csv")
        rows = load_runtime_metrics(csv_path)
        if not rows:
            print(f"[SKIP] No runtime metrics for scenario '{scenario}'")
            continue

        color = SCENARIO_COLORS[idx % len(SCENARIO_COLORS)]
        t0 = min(r["timestamp"] for r in rows) / 1000.0
        times = [(r["timestamp"] / 1000.0) - t0 for r in rows]
        gpu = [r["gpu_usage"] for r in rows]
        inflight = [r["inflight_60s_avg"] for r in rows]

        x_gpu = [t for t, v in zip(times, gpu) if v is not None]
        y_gpu = [v for v in gpu if v is not None]
        x_inflight = [t for t, v in zip(times, inflight) if v is not None]
        y_inflight = [v for v in inflight if v is not None]

        if y_gpu:
            ax_gpu.plot(x_gpu, y_gpu, label=scenario, color=color, linewidth=2)
        if y_inflight:
            ax_proxy.plot(x_inflight, y_inflight, label=scenario, color=color, linewidth=2)

    ax_gpu.legend()
    ax_gpu.grid(True, alpha=0.3)
    fig_gpu.tight_layout()
    out_gpu = os.path.join(output_dir, "gpu_usage_comparison.png")
    fig_gpu.savefig(out_gpu, dpi=150)
    print(f"[SAVED] {out_gpu}")

    ax_proxy.legend()
    ax_proxy.grid(True, alpha=0.3)
    fig_proxy.tight_layout()
    out_proxy = os.path.join(output_dir, "proxy_inflight_comparison.png")
    fig_proxy.savefig(out_proxy, dpi=150)
    print(f"[SAVED] {out_proxy}")

    plt.close("all")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze FL proxy experiment results")
    sub = parser.add_subparsers(dest="command")

    # latency subcommand
    p_lat = sub.add_parser("latency", help="Plot latency and error rate comparison")
    p_lat.add_argument("--scenarios", nargs="+", required=True,
                       help="Scenario names (will load request_data_{name}.csv)")
    p_lat.add_argument("--rounds", nargs="*", default=[],
                       help="Optional rounds CSV files (one per scenario, in same order)")
    p_lat.add_argument("--window", type=float, default=15.0, help="Rolling window size in seconds")
    p_lat.add_argument("--dir", default=".", help="Directory containing CSV files")

    # rounds subcommand
    p_rnd = sub.add_parser("rounds", help="Plot FL round duration comparison")
    p_rnd.add_argument("--labels", nargs="+", required=True)
    p_rnd.add_argument("--files", nargs="+", required=True)
    p_rnd.add_argument("--dir", default=".", help="Directory containing CSV files")

    # accuracy subcommand
    p_acc = sub.add_parser("accuracy", help="Plot FL accuracy convergence")
    p_acc.add_argument("--labels", nargs="+", required=True)
    p_acc.add_argument("--files", nargs="+", required=True)
    p_acc.add_argument("--dir", default=".", help="Directory containing CSV files")

    # runtime subcommand
    p_run = sub.add_parser("runtime", help="Plot Jetson and proxy runtime metrics")
    p_run.add_argument("--scenarios", nargs="+", required=True,
                       help="Scenario names (will load runtime_metrics_{name}.csv)")
    p_run.add_argument("--dir", default=".", help="Directory containing CSV files")

    # all subcommand
    p_all = sub.add_parser("all", help="Run all plots")
    p_all.add_argument("--request-csvs", nargs="+", required=True,
                       help="Scenario names for request CSVs")
    p_all.add_argument("--rounds-files", nargs="+", required=True,
                       help="Rounds CSV files for duration + latency shading (one per request-csv scenario)")
    p_all.add_argument("--rounds-labels", nargs="+", required=True,
                       help="Labels for round duration plot")
    p_all.add_argument("--accuracy-files", nargs="+", required=True,
                       help="Rounds CSV files for accuracy convergence plot")
    p_all.add_argument("--accuracy-labels", nargs="+", required=True,
                       help="Labels for accuracy convergence plot")
    p_all.add_argument("--window", type=float, default=15.0)
    p_all.add_argument("--dir", default=".")

    args = parser.parse_args()

    if args.command == "latency":
        rounds_files = args.rounds + [""] * max(0, len(args.scenarios) - len(args.rounds))
        plot_latency_and_errors(args.scenarios, rounds_files, output_dir=args.dir, window_s=args.window)

    elif args.command == "rounds":
        files = [os.path.join(args.dir, f) for f in args.files]
        plot_round_duration(args.labels, files, output_dir=args.dir)

    elif args.command == "accuracy":
        files = [os.path.join(args.dir, f) for f in args.files]
        plot_accuracy(args.labels, files, output_dir=args.dir)

    elif args.command == "runtime":
        plot_runtime_metrics(args.scenarios, output_dir=args.dir)

    elif args.command == "all":
        rounds_files = args.rounds_files + [""] * max(0, len(args.request_csvs) - len(args.rounds_files))
        plot_latency_and_errors(args.request_csvs, rounds_files, output_dir=args.dir, window_s=args.window)
        plot_runtime_metrics(args.request_csvs, output_dir=args.dir)
        rounds_files_full = [os.path.join(args.dir, f) for f in args.rounds_files]
        plot_round_duration(args.rounds_labels, rounds_files_full, output_dir=args.dir)
        acc_files_full = [os.path.join(args.dir, f) for f in args.accuracy_files]
        plot_accuracy(args.accuracy_labels, acc_files_full, output_dir=args.dir)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
