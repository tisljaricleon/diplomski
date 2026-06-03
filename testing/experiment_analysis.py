"""
experiment_analysis.py — Analyze and plot results for the AOM experiment series.

Usage:
    python experiment_analysis.py

Reads data from A/, B1/, B2/, B3/, C1/, C2/ subdirectories.
Outputs plots to experiment_plots/ directory.
"""

import csv
import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── helpers ──────────────────────────────────────────────────────────────────

OUT_DIR = "experiment_plots"
os.makedirs(OUT_DIR, exist_ok=True)

COLORS = {
    "A":  "#4c72b0",
    "B1": "#55a868",
    "B2": "#c44e52",
    "B3": "#8172b2",
    "C1": "#ccb974",
    "C2": "#64b5cd",
}
LABELS = {
    "A":  "A  (no load, AOM off)",
    "B1": "B1 (50 req/s, AOM off)",
    "B2": "B2 (100 req/s, AOM off)",
    "B3": "B3 (200 req/s, AOM off)",
    "C1": "C1 (100 req/s, AOM on)",
    "C2": "C2 (250 req/s, AOM on)",
}

def load_ga_log(exp):
    path = os.path.join(exp, "rpi_device_logs.csv")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    result = []
    for r in rows:
        # A uses old schema (duration_s), B/C use fit_duration_s + eval_duration_s
        if "fit_duration_s" in r:
            fit_dur  = float(r["fit_duration_s"])
            eval_dur = float(r["eval_duration_s"])
            total    = fit_dur + eval_dur
        else:
            fit_dur  = float(r["duration_s"])
            eval_dur = None
            total    = fit_dur
        result.append({
            "round":      int(r["round"]),
            "fit_dur":    fit_dur,
            "eval_dur":   eval_dur,
            "total_dur":  total,
            "accuracy":   float(r["accuracy"]),
            "loss":       float(r["loss"]),
            "n_clients":  int(r["num_clients_selected"]),
        })
    return result

def load_proxy_metrics(exp):
    path = os.path.join(exp, "proxy_metrics.csv")
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return rows

def savefig(name):
    p = os.path.join(OUT_DIR, name)
    plt.savefig(p, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  saved → {p}")

# ── load all experiments ──────────────────────────────────────────────────────

EXPS = ["A", "B1", "B2", "B3", "C1", "C2"]
data = {e: load_ga_log(e) for e in EXPS}

# ── quick console summary ─────────────────────────────────────────────────────

print("\n=== Summary ===")
print(f"{'Exp':<4} {'Rounds':>6}  {'AvgFitDur':>10}  {'FinalAcc':>9}  {'AOM':>5}")
print("-" * 50)
for e in EXPS:
    rows = data[e]
    avg_fit = np.mean([r["fit_dur"] for r in rows])
    final_acc = rows[-1]["accuracy"]
    aom_rounds = sum(1 for r in rows if r["n_clients"] < 3)
    aom_str = f"{aom_rounds}/{len(rows)}" if "C" in e else "off"
    print(f"{e:<4} {len(rows):>6}  {avg_fit:>10.1f}s  {final_acc:>9.4f}  {aom_str:>5}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 1 — Per-round fit duration for every experiment (line chart)
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 1: per-round fit duration …")
fig, ax = plt.subplots(figsize=(11, 5))
for e in EXPS:
    rows = data[e]
    rounds = [r["round"] for r in rows]
    durs   = [r["fit_dur"] for r in rows]
    ax.plot(rounds, durs, marker="o", markersize=3, label=LABELS[e],
            color=COLORS[e], linewidth=1.6)

ax.set_xlabel("Global Round")
ax.set_ylabel("Fit Duration (s)")
ax.set_title("Per-round fit duration — all experiments")
ax.legend(fontsize=8, loc="upper right")
ax.grid(True, alpha=0.3)
plt.tight_layout()
savefig("1_fit_duration_per_round.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 2 — Average fit duration per experiment (bar chart, B1→B2→B3 shows load effect)
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 2: avg fit duration bar chart …")
fig, ax = plt.subplots(figsize=(9, 5))

avg_durs = [np.mean([r["fit_dur"] for r in data[e]]) for e in EXPS]
std_durs = [np.std( [r["fit_dur"] for r in data[e]]) for e in EXPS]
bars = ax.bar(EXPS, avg_durs, yerr=std_durs, capsize=4,
              color=[COLORS[e] for e in EXPS], alpha=0.85, width=0.55)

# Annotate values
for bar, val, std in zip(bars, avg_durs, std_durs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + std + 0.5,
            f"{val:.1f}s", ha="center", va="bottom", fontsize=8)

ax.set_ylabel("Mean Fit Duration (s)")
ax.set_title("Mean fit duration per experiment (error bars = ±1 std)")
ax.set_ylim(0, max(avg_durs) * 1.3)
ax.grid(True, axis="y", alpha=0.3)

# Add annotation arrows for key comparisons
y_ann = max(avg_durs) * 1.15
# B3 vs C2 — main claim
b3_x = EXPS.index("B3")
c2_x = EXPS.index("C2")
diff = avg_durs[b3_x] - avg_durs[c2_x]
ax.annotate("", xy=(c2_x, y_ann), xytext=(b3_x, y_ann),
            arrowprops=dict(arrowstyle="<->", color="black", lw=1.5))
ax.text((b3_x + c2_x) / 2, y_ann + 0.5, f"−{diff:.1f}s\n(AOM benefit)", 
        ha="center", fontsize=7.5, color="black")

plt.tight_layout()
savefig("2_avg_fit_duration_bar.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 3 — Load effect: B1 → B2 → B3 avg fit duration + trend
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 3: load effect B1→B2→B3 …")
B_exps  = ["B1", "B2", "B3"]
B_loads = [50, 100, 200]
B_avgs  = [np.mean([r["fit_dur"] for r in data[e]]) for e in B_exps]
B_stds  = [np.std( [r["fit_dur"] for r in data[e]]) for e in B_exps]

fig, ax = plt.subplots(figsize=(7, 5))
ax.errorbar(B_loads, B_avgs, yerr=B_stds, fmt="o-", capsize=5,
            color="#8172b2", linewidth=2, markersize=7)

for load, avg, std in zip(B_loads, B_avgs, B_stds):
    ax.text(load, avg + std + 1, f"{avg:.1f}s", ha="center", fontsize=9)

# baseline A
a_avg = np.mean([r["fit_dur"] for r in data["A"]])
ax.axhline(a_avg, color=COLORS["A"], linestyle="--", linewidth=1.5,
           label=f"A baseline ({a_avg:.1f}s, no load)")

ax.set_xlabel("Inference Load on orinnano-2 (req/s)")
ax.set_ylabel("Mean Fit Duration (s)")
ax.set_title("Effect of inference load on FL round duration (AOM off)")
ax.set_xticks(B_loads)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
ax.set_ylim(0, max(B_avgs) * 1.35)
plt.tight_layout()
savefig("3_load_effect_B_series.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 4 — AOM benefit: B2 vs C1 and B3 vs C2 (paired bar)
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 4: AOM benefit paired bar …")
pairs = [("B2", "C1", "100 req/s"), ("B3", "C2", "200–250 req/s")]
x = np.arange(len(pairs))
width = 0.32

fig, ax = plt.subplots(figsize=(7, 5))
b_vals = [np.mean([r["fit_dur"] for r in data[b]]) for b, _, _ in pairs]
c_vals = [np.mean([r["fit_dur"] for r in data[c]]) for _, c, _ in pairs]
b_stds = [np.std( [r["fit_dur"] for r in data[b]]) for b, _, _ in pairs]
c_stds = [np.std( [r["fit_dur"] for r in data[c]]) for _, c, _ in pairs]

bars_b = ax.bar(x - width/2, b_vals, width, yerr=b_stds, capsize=4,
                label="AOM off", color="#c44e52", alpha=0.85)
bars_c = ax.bar(x + width/2, c_vals, width, yerr=c_stds, capsize=4,
                label="AOM on", color="#64b5cd", alpha=0.85)

for bar, val in zip(bars_b, b_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f"{val:.1f}s", ha="center", fontsize=8)
for bar, val in zip(bars_c, c_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f"{val:.1f}s", ha="center", fontsize=8)

ax.set_xticks(x)
ax.set_xticklabels([label for _, _, label in pairs])
ax.set_ylabel("Mean Fit Duration (s)")
ax.set_title("AOM benefit: same load, with vs without client selection")
ax.legend()
ax.grid(True, axis="y", alpha=0.3)
ax.set_ylim(0, max(b_vals + c_vals) * 1.3)
plt.tight_layout()
savefig("4_aom_benefit_paired.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 5 — Accuracy curves: all experiments (does AOM hurt accuracy?)
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 5: accuracy curves …")
fig, ax = plt.subplots(figsize=(11, 5))
for e in EXPS:
    rows = data[e]
    ax.plot([r["round"] for r in rows], [r["accuracy"] for r in rows],
            marker="o", markersize=3, label=LABELS[e],
            color=COLORS[e], linewidth=1.6)

ax.set_xlabel("Global Round")
ax.set_ylabel("Accuracy")
ax.set_title("Accuracy per round — all experiments")
ax.legend(fontsize=8, loc="lower right")
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 1.0)
plt.tight_layout()
savefig("5_accuracy_per_round.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 6 — Final accuracy comparison (bar chart)
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 6: final accuracy bar …")
fig, ax = plt.subplots(figsize=(9, 5))
final_accs = [data[e][-1]["accuracy"] for e in EXPS]
bars = ax.bar(EXPS, final_accs, color=[COLORS[e] for e in EXPS], alpha=0.85, width=0.55)

for bar, val in zip(bars, final_accs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.003,
            f"{val:.3f}", ha="center", va="bottom", fontsize=8)

ax.axhline(data["A"][-1]["accuracy"], color=COLORS["A"], linestyle="--",
           linewidth=1.5, label=f"A baseline ({data['A'][-1]['accuracy']:.3f})")

ax.set_ylabel("Final Accuracy")
ax.set_title("Final round accuracy — all experiments")
ax.set_ylim(0, 1.0)
ax.legend(fontsize=9)
ax.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
savefig("6_final_accuracy_bar.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 7 — C2 client selection: which rounds had 2 vs 3 clients (AOM timeline)
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 7: C2 AOM selection timeline …")
fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)

for ax, exp, title in zip(axes, ["C1", "C2"],
                           ["C1 (100 req/s, AOM on) — client count per round",
                            "C2 (250 req/s, AOM on) — client count per round"]):
    rows = data[exp]
    rounds  = [r["round"] for r in rows]
    n_cli   = [r["n_clients"] for r in rows]
    fit_dur = [r["fit_dur"] for r in rows]

    color_map = {3: "#55a868", 2: "#c44e52"}
    bar_colors = [color_map[n] for n in n_cli]
    bars = ax.bar(rounds, fit_dur, color=bar_colors, alpha=0.85, width=0.7)

    patch3 = mpatches.Patch(color="#55a868", label="3 clients (orinnano-2 included)")
    patch2 = mpatches.Patch(color="#c44e52", label="2 clients (orinnano-2 excluded by AOM)")
    ax.legend(handles=[patch3, patch2], fontsize=8, loc="upper right")
    ax.set_ylabel("Fit Duration (s)")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)

axes[-1].set_xlabel("Global Round")
plt.tight_layout()
savefig("7_aom_selection_timeline_C1_C2.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 8 — Inflight 60s avg on orinnano-2 over time (B3 vs C2)
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 8: inflight avg orinnano-2 (B3 vs C2) …")
fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=False)

for ax, exp, color in zip(axes, ["B3", "C2"], ["#8172b2", "#64b5cd"]):
    pm = load_proxy_metrics(exp)
    if pm is None:
        ax.text(0.5, 0.5, "No proxy_metrics.csv", transform=ax.transAxes, ha="center")
        continue
    # filter orinnano-2 only
    rows = [r for r in pm if "orinnano-2" in r.get("client_name", "")]
    if not rows:
        ax.text(0.5, 0.5, "No orinnano-2 rows", transform=ax.transAxes, ha="center")
        continue
    ts    = [int(r["timestamp"]) / 1000 for r in rows]
    t0    = ts[0]
    ts    = [(t - t0) for t in ts]
    inflt = [float(r["inflight_60s_avg"]) for r in rows]

    ax.plot(ts, inflt, color=color, linewidth=1.2, alpha=0.8)
    ax.axhline(15, color="red", linestyle="--", linewidth=1.2, label="threshold=15")
    ax.set_ylabel("inflight_60s_avg")
    ax.set_title(f"{exp} — orinnano-2 inflight 60s avg over time")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

axes[-1].set_xlabel("Time since experiment start (s)")
plt.tight_layout()
savefig("8_inflight_orinnano2_B3_C2.png")

# ─────────────────────────────────────────────────────────────────────────────
# PLOT 9 — C2 fit duration split: 3-client rounds vs 2-client rounds
# ─────────────────────────────────────────────────────────────────────────────
print("Plot 9: C2 fit duration by client count …")
rows_c2 = data["C2"]
dur_3 = [r["fit_dur"] for r in rows_c2 if r["n_clients"] == 3]
dur_2 = [r["fit_dur"] for r in rows_c2 if r["n_clients"] == 2]

fig, ax = plt.subplots(figsize=(7, 5))
pos = [1, 2]
bp = ax.boxplot([dur_3, dur_2], positions=pos, widths=0.5, patch_artist=True,
                medianprops=dict(color="black", linewidth=2))
bp["boxes"][0].set_facecolor("#55a868")
bp["boxes"][1].set_facecolor("#c44e52")

# overlay individual points
for i, (durs, p) in enumerate(zip([dur_3, dur_2], pos)):
    jitter = np.random.default_rng(42).uniform(-0.08, 0.08, len(durs))
    ax.scatter([p + j for j in jitter], durs, color="black", s=20, zorder=5, alpha=0.7)

means = [np.mean(dur_3), np.mean(dur_2)]
for p, m in zip(pos, means):
    ax.text(p, m + 0.5, f"mean={m:.1f}s", ha="center", fontsize=9, color="black")

ax.set_xticks(pos)
ax.set_xticklabels(["3 clients\n(orinnano-2 in)", "2 clients\n(orinnano-2 out)"])
ax.set_ylabel("Fit Duration (s)")
ax.set_title("C2: fit duration when AOM includes vs excludes orinnano-2")
ax.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
savefig("9_C2_fit_dur_by_client_count.png")

print("\nAll plots saved to experiment_plots/")
