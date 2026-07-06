#!/usr/bin/env python3
"""
FL Orchestrator - Experiment Analysis
======================================
Proves two goals from the experiment plan:
  1. FL round duration is shorter when AoM selection excludes overloaded clients
  2. Model accuracy does not degrade when AoM client selection is active

Experiment sequence (oldest -> newest filename timestamp):
  A  - baseline_no_load  : no requests, AoM off
    B1 - 100 zahtjeva/s    : 100 zahtjeva/s po klijentu, AoM isključen
    B2 - 250 zahtjeva/s    : 250 zahtjeva/s po klijentu, AoM isključen
    C1 - 250 zahtjeva/s + AoM   : 250 zahtjeva/s po klijentu, AoM uključen  (prag = 15)
    C2 - 400 zahtjeva/s + AoM   : 400 zahtjeva/s po klijentu, AoM uključen  (prag = 15)

File mapping confirmed by aligning actual timestamps inside each CSV.
"""

import csv
import json
import os
import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Output directory
OUT_DIR = 'experiment_plots'
os.makedirs(OUT_DIR, exist_ok=True)
MAX_ROUND = 15

# Experiment metadata
'''
EXPERIMENTS = {
    'A':  {'label': 'A\nBaseline\n(no load)',   'short': 'A - 0 req/s',         'color': '#2196F3', 'marker': 'o', 'AoM': False},
    'B1': {'label': 'B1\n100 req/s\n(AoM off)', 'short': 'B1 - 100 req/s',        'color': '#FF9800', 'marker': 's', 'AoM': False},
    'B2': {'label': 'B2\n200 req/s\n(AoM off)', 'short': 'B2 - 200 req/s',        'color': '#F44336', 'marker': 's', 'AoM': False},
    'C1': {'label': 'C1\n250 req/s\n(AoM on)',  'short': 'C1 - 250 req/s + AoM',  'color': '#00BCD4', 'marker': '^', 'AoM': True},
    'C2': {'label': 'C2\n400 req/s\n(AoM on)',  'short': 'C2 - 400 req/s + AoM',  'color': '#4CAF50', 'marker': '^', 'AoM': True},
}
'''
EXPERIMENTS = {
    'A':  {'label': 'A\nReferentni slučaj\n(bez opterećenja)',   'short': 'A - 0 zahtjeva/s',         'color': '#2196F3', 'marker': 'o', 'AoM': False},
    'B1': {'label': 'B1\n100 zahtjeva/s\n(AoM isključen)', 'short': 'B1 - 100 zahtjeva/s',        'color': '#FF9800', 'marker': 's', 'AoM': False},
    'B2': {'label': 'B2\n200 zahtjeva/s\n(AoM isključen)', 'short': 'B2 - 200 zahtjeva/s',        'color': '#F44336', 'marker': 's', 'AoM': False},
    'C1': {'label': 'C1\n250 zahtjeva/s\n(AoM uključen)',  'short': 'C1 - 250 zahtjeva/s + AoM',  'color': '#00BCD4', 'marker': '^', 'AoM': True},
    'C2': {'label': 'C2\n400 zahtjeva/s\n(AoM uključen)',  'short': 'C2 - 400 zahtjeva/s + AoM',  'color': '#4CAF50', 'marker': '^', 'AoM': True},
}

GA_LOGS = {
    'A':  'round_logs/rounds_log_20260603_160117.csv',
    'C2': 'round_logs/rounds_log_20260603_202002.csv',
    'C1': 'round_logs/rounds_log_20260604_222726.csv',
    'B2': 'round_logs/rounds_log_20260604_232456.csv',
    'B1': 'round_logs/rounds_log_20260605_010228.csv',
}

PROXY_FILES = {
    'C2': 'request_and_proxy_metrics/runtime_metrics_round_with_proxy_20260603_231156.csv',
    'C1': 'runtime_metrics_round_with_proxy_20260605_011957.csv',
    'B2': 'runtime_metrics_round_with_proxy_20260605_021853.csv',
    'B1': 'runtime_metrics_round_with_proxy_20260605_035737.csv',
}

REQUEST_FILES = {
    'C2': 'request_and_proxy_metrics/request_data_round_with_proxy_20260603_231156.csv',
    'C1': 'request_data_round_with_proxy_20260605_011957.csv',
    'B2': 'request_data_round_with_proxy_20260605_021853.csv',
    'B1': 'request_data_round_with_proxy_20260605_035737.csv',
}

CLIENT_LOGS = {
    'A':  ('client_logs_orinnano2/client_rounds_log_p0_20260603_160339.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260603_160344.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260603_160342.csv'),
    'C2': ('client_logs_orinnano2/client_rounds_log_p0_20260603_202214.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260603_202212.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260603_202213.csv'),
    'C1': ('client_logs_orinnano2/client_rounds_log_p0_20260604_222951.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260604_223001.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260604_222956.csv'),
    'B2': ('client_logs_orinnano2/client_rounds_log_p0_20260604_232741.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260604_232728.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260604_232727.csv'),
    'B1': ('client_logs_orinnano2/client_rounds_log_p0_20260605_010502.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260605_010500.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260605_010500.csv'),
}

# Raspberry Pi (global aggregator) CPU logs mapped to experiments by nearest start timestamp.
RPI_LOGS = {
    'A':  'rpi_logs/rpi_logs_20260603_180206.csv',
    'C2': 'rpi_logs/rpi_logs_20260603_222226.csv',
    'C1': 'rpi_logs/rpi_logs_20260605_002937.csv',
    'B2': 'rpi_logs/rpi_logs_20260605_012756.csv',
    # No dedicated RPi CPU log segment found for B1.
}


def load_ga(key):
    with open(GA_LOGS[key]) as f:
        rows = list(csv.DictReader(f))
    filtered = []
    for r in rows:
        if r.get('accuracy', '').strip() == '':
            continue
        try:
            if int(r.get('round', 0)) > MAX_ROUND:
                continue
        except ValueError:
            continue
        filtered.append(r)
    return filtered


def load_proxy(key):
    with open(PROXY_FILES[key]) as f:
        return list(csv.DictReader(f))


def proxy_inflight_o2(key):
    ga_rows = load_ga(key)
    exp_start_ms = int(ga_rows[0]['fit_start_ts_ms'])
    rows = load_proxy(key)
    o2 = [r for r in rows if 'orinnano-2' in r.get('client_name', '')]
    rel = [(int(r['timestamp']) - exp_start_ms) / 60000 for r in o2]
    vals = [float(r['inflight_60s_avg']) for r in o2]
    return rel, vals


def ga_round_windows(key):
    ga_rows = load_ga(key)
    exp_start_ms = int(ga_rows[0]['fit_start_ts_ms'])
    result = []
    for r in ga_rows:
        rstart = (int(r['fit_start_ts_ms']) - exp_start_ms) / 60000
        rend   = (int(r['fit_end_ts_ms'])   - exp_start_ms) / 60000
        result.append((int(r['round']), rstart, rend, int(r['num_clients_selected'])))
    return result


def save(fig, name):
    path = f'{OUT_DIR}/{name}'
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved {path}')


# ============================================================
# PLOT 1 - Per-round fit duration line chart all experiments
# ============================================================
def plot_per_round_duration():
    fig, ax = plt.subplots(figsize=(11, 5))
    for key in EXPERIMENTS:
        rows = load_ga(key)
        rnds = [int(r['round']) for r in rows]
        durs = [float(r['fit_duration_s']) for r in rows]
        m = EXPERIMENTS[key]
        ax.plot(rnds, durs, marker=m['marker'], color=m['color'],
                label=m['short'], linewidth=1.8, markersize=5)
    #ax.set_xlabel('FL Round')
    #ax.set_ylabel('Fit Duration (s)')
    #ax.set_title('FL Fit Duration per Global Round')
    ax.set_xlabel('Redni broj globalne runde')
    ax.set_ylabel('Trajanje treniranja (s)')
    ax.set_title('Trajanje treniranja po globalnoj rundi')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    save(fig, '01_global_round_fit_duration.png')


# ============================================================
# PLOT 2 - Average fit duration bar chart  (GOAL 1)
# ============================================================
def plot_avg_duration_bar():
    keys = list(EXPERIMENTS.keys())
    avgs, stds, colors, xlabels = [], [], [], []
    for key in keys:
        durs = [float(r['fit_duration_s']) for r in load_ga(key)]
        avgs.append(np.mean(durs))
        stds.append(np.std(durs))
        colors.append(EXPERIMENTS[key]['color'])
        xlabels.append(EXPERIMENTS[key]['label'])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(range(len(keys)), avgs, yerr=stds, capsize=6,
           color=colors, alpha=0.85, edgecolor='black', linewidth=0.7)

    for i, (v, e) in enumerate(zip(avgs, stds)):
        ax.text(i, v + e + 1.5, f'{v:.1f}s', ha='center', va='bottom',
                fontsize=10, fontweight='bold')

    # indices in EXPERIMENTS order: A=0, B1=1, B2=2, C1=3, C2=4
    b2i, c2i = 2, 3
    gain = avgs[b2i] - avgs[c2i]
    y_top = max(avgs[b2i] + stds[b2i], avgs[c2i] + stds[c2i]) + 14
    ax.annotate('', xy=(c2i, y_top - 4), xytext=(b2i, y_top - 4),
                arrowprops=dict(arrowstyle='<->', color='darkgreen', lw=2))

    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(xlabels, fontsize=9)
    ax.set_ylabel('Average Fit Duration (s)')
    ax.set_title('Average Global FL Round Fit Duration (+/- Standard Deviation)\n')
    ax.grid(axis='y', alpha=0.3)
    save(fig, '02_avg_global_round_fit_duration.png')


# ============================================================
# ============================================================
# PLOT 4 - AoM benefit: B2 vs C1 vs C2 vs D1
# ============================================================
def plot_AoM_benefit():
    fig, ax = plt.subplots(figsize=(11, 5))
    for key in ['B2', 'C1', 'C2']:
        rows = load_ga(key)
        rnds = [int(r['round']) for r in rows]
        durs = [float(r['fit_duration_s']) for r in rows]
        m = EXPERIMENTS[key]
        ax.plot(rnds, durs, marker=m['marker'], color=m['color'],
                label=m['short'], linewidth=2, markersize=6)

    for r in load_ga('C2'):
        if int(r['num_clients_selected']) < 3:
            ax.axvline(x=int(r['round']), color=EXPERIMENTS['C2']['color'],
                       alpha=0.18, linewidth=6, zorder=0)

    for key_excl in ['C1', 'C2']:
        for r in load_ga(key_excl):
            if int(r['num_clients_selected']) < 3:
                ax.axvline(x=int(r['round']), color=EXPERIMENTS[key_excl]['color'],
                           alpha=0.18, linewidth=6, zorder=0)
    #excl_c2 = mpatches.Patch(color=EXPERIMENTS['C2']['color'], alpha=0.35,
    #                          label='Rounds where AoM excluded overloaded client')
    excl_c2 = mpatches.Patch(color=EXPERIMENTS['C2']['color'], alpha=0.35,
                              label='Globalne runde u kojima je AoM isključio preopterećenog klijenta')
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [excl_c2], fontsize=9)
    ax.set_xlabel('Redni broj globalne runde')
    ax.set_ylabel('Trajanje treniranja (s)')
    ax.set_title('Učinak selekcijskog algoritma: B2 (AoM isključen) naspram C1/C2 (AoM uključen)')
    #ax.set_xlabel('FL Round')
    #ax.set_ylabel('Fit Duration (s)')
    #ax.set_title('AoM Benefit: B2 (AoM off) vs C1/C2 (AoM on)')
    ax.grid(True, alpha=0.3)
    save(fig, '04_aom_benefit.png')


# ============================================================
# PLOT 5 - Accuracy curves all experiments  (GOAL 2)
# ============================================================
def plot_accuracy_curves():
    fig, ax = plt.subplots(figsize=(11, 5))
    for key in EXPERIMENTS:
        rows = load_ga(key)
        rnds = [int(r['round']) for r in rows]
        accs = [float(r['accuracy']) for r in rows]
        m = EXPERIMENTS[key]
        ax.plot(rnds, accs, marker=m['marker'], color=m['color'],
                label=m['short'], linewidth=2, markersize=5)
    ax.set_xlabel('FL Round')
    ax.set_ylabel('Global Accuracy')
    ax.set_title('Global Model Accuracy per Round')
    ax.legend(fontsize=9, loc='lower right')
    ax.grid(True, alpha=0.3)
    save(fig, '05_global_accuracy_curves.png')


# ============================================================
# PLOT 6 - Final accuracy bar chart
# ============================================================
def plot_final_accuracy_bar():
    keys = list(EXPERIMENTS.keys())
    accs, colors, xlabels = [], [], []
    for key in keys:
        rows = load_ga(key)
        accs.append(float(rows[-1]['accuracy']))
        colors.append(EXPERIMENTS[key]['color'])
        xlabels.append(EXPERIMENTS[key]['label'])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(range(len(keys)), [a * 100 for a in accs],
           color=colors, alpha=0.85, edgecolor='black', linewidth=0.7)
    for i, v in enumerate(accs):
        ax.text(i, v * 100 + 0.15, f'{v*100:.2f}%', ha='center', va='bottom',
                fontsize=10, fontweight='bold')

    baseline = accs[0] * 100
    ax.axhline(y=baseline, color='gray', linestyle='--', linewidth=1.3,
               label=f'Baseline accuracy - {baseline:.2f}%')
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(xlabels, fontsize=9)
    ax.set_ylim([0, max(accs) * 100 + 5])
    ax.set_ylabel('Final Accuracy (%)')
    ax.set_title('Final Global Model Accuracy')
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    save(fig, '06_final_global_accuracy.png')


# ============================================================
# ============================================================
# PLOT 8 - inflight comparison all load experiments
# ============================================================
def plot_inflight_comparison():
    fig, ax = plt.subplots(figsize=(13, 5))
    for key in ['B1', 'B2', 'C1', 'C2']:
        rel, vals = proxy_inflight_o2(key)
        m = EXPERIMENTS[key]
        ax.plot(rel, vals, color=m['color'], linewidth=1.4, label=m['short'], alpha=0.9)
    ax.axhline(y=15, color='red', linestyle='--', linewidth=1.8, label='AoM prag = 15 zahtjeva/s')
    ax.set_xlabel('Vrijeme od početka eksperimenta (min)')
    ax.set_ylabel('Prosječan broj zahtjeva na čekanju u sekundi (zahtjeva/s)')
    ax.set_title('Prosječan broj zahtjeva na čekanju kod posredničkog poslužitelja orinnano-2')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    save(fig, '08_orinnano2_inflight_comparison.png')


# ============================================================
# PLOT 10 - D2 inflight with FL round windows
# ============================================================
def plot_inflight_B2_with_rounds():
    fig, ax = plt.subplots(figsize=(13, 5))
    rel, vals = proxy_inflight_o2('B2')
    ax.fill_between(rel, vals, alpha=0.25, color=EXPERIMENTS['B2']['color'])
    ax.plot(rel, vals, color=EXPERIMENTS['B2']['color'], linewidth=1.4,
            label='Inflight Request Average', zorder=3)

    for rno, rstart, rend, n_sel in ga_round_windows('B2'):
        ax.axvspan(rstart, rend, alpha=0.10, color='purple', zorder=1)

    ax.axhline(y=15, color='red', linestyle='--', linewidth=1.8, label='AoM threshold = 15')
    round_patch = mpatches.Patch(color='purple', alpha=0.25, label='Active FL training')
    handles, lbl = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [round_patch], fontsize=9)
    ax.set_xlabel('Time since experiment start (min)')
    ax.set_ylabel('Prosjek istovremenih zahtjeva (zahtjeva/s)')
    ax.set_title('B2 (200 zahtjeva/s, AoM isključen): Prosjek istovremenih zahtjeva tijekom FL treniranja na orinnano-2')
    ax.grid(True, alpha=0.3)
    save(fig, '10_b2_inflight_with_rounds.png')


# ============================================================
# PLOT 11 - C2 inflight with AoM action markers
# ============================================================
def plot_inflight_C2_AoM_action():
    fig, ax = plt.subplots(figsize=(13, 5))
    rel, vals = proxy_inflight_o2('C1')
    ax.fill_between(rel, vals, alpha=0.2, color=EXPERIMENTS['C1']['color'])
    ax.plot(rel, vals, color=EXPERIMENTS['C1']['color'], linewidth=1.4,
            label='Inflight Request Average', zorder=3)

    for rno, rstart, rend, n_sel in ga_round_windows('C1'):
        if n_sel < 3:
            ax.axvspan(rstart, rend, alpha=0.18, color='#FF5722', zorder=1)

    ax.axhline(y=15, color='red', linestyle='--', linewidth=1.8, label='AoM threshold = 15')
    excl_patch = mpatches.Patch(color='#FF5722', alpha=0.5,
                                label='Rounds where AoM excluded orinnano-2')
    handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [excl_patch], fontsize=9)
    ax.set_xlabel('Time since experiment start (min)')
    ax.set_ylabel('Prosjek istovremenih zahtjeva (zahtjeva/s)')
    ax.set_title('C1 (250 zahtjeva/s, AoM uključen): Prosjek istovremenih zahtjeva tijekom FL treniranja na orinnano-2')
    ax.grid(True, alpha=0.3)
    save(fig, '11_c1_inflight_aom_action.png')


# ============================================================
# PLOT 12 - Loss curves all experiments
# ============================================================
def plot_loss_curves():
    fig, ax = plt.subplots(figsize=(11, 5))
    for key in EXPERIMENTS:
        rows = load_ga(key)
        rnds = [int(r['round']) for r in rows]
        loss = [float(r['loss']) for r in rows]
        m = EXPERIMENTS[key]
        ax.plot(rnds, loss, marker=m['marker'], color=m['color'],
                label=m['short'], linewidth=2, markersize=5)
    ax.set_xlabel('FL Round')
    ax.set_ylabel('Global Loss')
    ax.set_title('Global Model Loss per Round')
    ax.legend(fontsize=9, loc='upper right')
    ax.grid(True, alpha=0.3)
    save(fig, '12_global_loss_curves.png')


# ============================================================
# PLOT 15 - Combined: loss curves (top) + final accuracy bar (bottom)
# ============================================================
def plot_loss_and_accuracy_combined():
    keys = list(EXPERIMENTS.keys())

    fig, (ax_loss, ax_acc) = plt.subplots(2, 1, figsize=(11, 10))

    # --- top: loss curves ---
    for key in EXPERIMENTS:
        rows = load_ga(key)
        rnds = [int(r['round']) for r in rows]
        loss = [float(r['loss']) for r in rows]
        m = EXPERIMENTS[key]
        ax_loss.plot(rnds, loss, marker=m['marker'], color=m['color'],
                     label=m['short'], linewidth=2, markersize=5)
    ax_loss.set_xlabel('FL Round')
    ax_loss.set_ylabel('Funkcija gubitka')
    ax_loss.set_title('Funkcija gubitka po globalnoj rundi')
    ax_loss.legend(fontsize=9, loc='upper right')
    ax_loss.grid(True, alpha=0.3)

    # --- bottom: final accuracy bar ---
    accs, colors, xlabels = [], [], []
    for key in keys:
        rows = load_ga(key)
        accs.append(float(rows[-1]['accuracy']))
        colors.append(EXPERIMENTS[key]['color'])
        xlabels.append(EXPERIMENTS[key]['label'])

    ax_acc.bar(range(len(keys)), [a * 100 for a in accs],
               color=colors, alpha=0.85, edgecolor='black', linewidth=0.7)
    for i, v in enumerate(accs):
        ax_acc.text(i, v * 100 + 0.15, f'{v*100:.2f}%', ha='center', va='bottom',
                    fontsize=10, fontweight='bold')
    baseline = accs[0] * 100
    ax_acc.axhline(y=baseline, color='gray', linestyle='--', linewidth=1.3,
                   label=f'Referentna točnost ({baseline:.2f}%)')
    ax_acc.set_xticks(range(len(keys)))
    ax_acc.set_xticklabels(xlabels, fontsize=9)
    ax_acc.set_ylim([0, max(accs) * 100 + 8])
    ax_acc.set_ylabel('Konačna točnost globalnog modela (%)')
    ax_acc.set_title('Konačna točnost globalnog modela svih eksperimenata')
    ax_acc.legend(fontsize=9, loc='lower right')
    ax_acc.grid(axis='y', alpha=0.3)

    save(fig, '15_loss_and_final_accuracy_combined.png')


# ============================================================
# PLOT 14 - Average per-client fit duration (orinnano-2 vs orinnano-3)
# ============================================================
def plot_avg_client_fit():
    keys = list(EXPERIMENTS.keys())
    avg_o2, avg_o3, avg_o4 = [], [], []
    for key in keys:
        files = CLIENT_LOGS.get(key, ())
        # orinnano-2 is first file, orinnano-3 is second, orinnano-4 is third
        def mean_fit_from_file(path):
            try:
                with open(path) as f:
                    rows = list(csv.DictReader(f))
                fits = [
                    float(r['duration_s'])
                    for r in rows
                    if r.get('phase') == 'fit' and int(r.get('round', 0)) <= MAX_ROUND
                ]
                return np.mean(fits) if fits else np.nan
            except Exception:
                return np.nan

        o2 = mean_fit_from_file(files[0]) if len(files) > 0 else np.nan
        o3 = mean_fit_from_file(files[1]) if len(files) > 1 else np.nan
        o4 = mean_fit_from_file(files[2]) if len(files) > 2 else np.nan
        avg_o2.append(o2)
        avg_o3.append(o3)
        avg_o4.append(o4)

    x = np.arange(len(keys))
    width = 0.25
    fig, ax = plt.subplots(figsize=(13, 5))
    c2_color = '#F44336'  # orinnano-2 (red)
    c3_color = '#2196F3'  # orinnano-3 (blue)
    c4_color = '#4CAF50'  # orinnano-4 (green)
    bars1 = ax.bar(x - width, avg_o2, width, label='orinnano-2', color=c2_color, alpha=0.9)
    bars2 = ax.bar(x,         avg_o3, width, label='orinnano-3', color=c3_color, alpha=0.9)
    bars3 = ax.bar(x + width, avg_o4, width, label='orinnano-4', color=c4_color, alpha=0.9)

    # Annotate values
    for rects in (bars1, bars2, bars3):
        for rect in rects:
            h = rect.get_height()
            if not np.isnan(h):
                ax.text(rect.get_x() + rect.get_width() / 2, h + 1.0, f'{h:.1f}s', ha='center', va='bottom', fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([EXPERIMENTS[k]['label'] for k in keys], fontsize=9)
    ax.set_ylabel('Prosječno trajanje lokalne runde treniranja (s)')
    ax.set_title('Prosječno trajanje lokalne runde treniranja za orinnano-2, orinnano-3 i orinnano-4')
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    save(fig, '14_avg_client_fit_orinnano2_orinnano3_orinnano4.png')


# ============================================================
# PLOT 16 - Raspberry Pi CPU usage: time series + average bar
# ============================================================
def plot_rpi_cpu_usage_over_time():
    fig, (ax_ts, ax_avg) = plt.subplots(2, 1, figsize=(13, 9))
    
    # ===== TOP: Time series (skip A, B1 missing) =====
    cpu_avgs = {}
    for key in ['B2', 'C1', 'C2']:
        rel_path = RPI_LOGS.get(key)
        if not rel_path or not os.path.exists(rel_path):
            continue

        with open(rel_path) as f:
            rows = list(csv.DictReader(f))

        points = [
            (int(r['timestamp']), float(r['cpu_usage']))
            for r in rows
            if r.get('timestamp') and r.get('cpu_usage') not in ('', None)
        ]
        if not points:
            continue

        points.sort(key=lambda x: x[0])
        t0 = points[0][0]
        rel_min = [(t - t0) / 60000 for t, _ in points]
        cpu = [v for _, v in points]
        cpu_avgs[key] = np.mean(cpu)

        meta = EXPERIMENTS.get(key, {})
        ax_ts.plot(rel_min, cpu, linewidth=1.2, color=meta.get('color', None),
                   label=meta.get('short', key), marker=None)

    ax_ts.set_xlabel('Vrijeme od početka eksperimenta (min)')
    ax_ts.set_ylabel('CPU iskorištenje Raspberry Pi (%)')
    ax_ts.set_title('CPU iskorištenje Raspberry Pi (globalni agregator) kroz vrijeme')
    ax_ts.grid(True, alpha=0.3)
    ax_ts.legend(fontsize=9, loc='upper left')

    # ===== BOTTOM: Average CPU bar chart =====
    keys_with_data = ['A', 'B2', 'C1', 'C2']  # A has data, B1 missing
    bars_data = []
    bars_colors = []
    bars_labels = []
    
    for key in keys_with_data:
        if key == 'A':
            # Read A's RPi log to get average
            rel_path = RPI_LOGS.get('A')
            if rel_path and os.path.exists(rel_path):
                with open(rel_path) as f:
                    rows = list(csv.DictReader(f))
                cpu = [float(r['cpu_usage']) for r in rows if r.get('cpu_usage') not in ('', None)]
                if cpu:
                    bars_data.append(np.mean(cpu))
                    bars_colors.append(EXPERIMENTS['A'].get('color'))
                    bars_labels.append(EXPERIMENTS['A'].get('short', 'A'))
        else:
            if key in cpu_avgs:
                bars_data.append(cpu_avgs[key])
                bars_colors.append(EXPERIMENTS[key].get('color'))
                bars_labels.append(EXPERIMENTS[key].get('short', key))

    ax_avg.bar(range(len(bars_data)), bars_data, color=bars_colors, alpha=0.85, edgecolor='black', linewidth=0.7)
    for i, v in enumerate(bars_data):
        ax_avg.text(i, v + 1.5, f'{v:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax_avg.set_xticks(range(len(bars_data)))
    ax_avg.set_xticklabels(bars_labels, fontsize=9)
    ax_avg.set_ylabel('Prosječno CPU iskorištenje (%)')
    ax_avg.set_title('Prosječno CPU iskorištenje Raspberry Pi po eksperimentu')
    ax_avg.grid(axis='y', alpha=0.3)

    save(fig, '16_rpi_cpu_usage_and_average.png')


# ============================================================
# ============================================================
# SUMMARY TABLE
# ============================================================
def print_summary():
    print()
    print('=' * 75)
    print('EXPERIMENT SUMMARY')
    print('=' * 75)
    print(f'{"Exp":<5} {"Description":<28} {"Rounds":<8} {"Avg Fit (s)":<14} {"Final Acc":<12} {"AoM triggers"}')
    print('-' * 75)
    stats = {}
    for key in EXPERIMENTS:
        rows = load_ga(key)
        durs = [float(r['fit_duration_s']) for r in rows]
        AoM  = sum(1 for r in rows if int(r['num_clients_selected']) < 3)
        acc  = float(rows[-1]['accuracy'])
        stats[key] = {'avg': np.mean(durs), 'std': np.std(durs), 'acc': acc,
                      'AoM': AoM, 'n': len(rows)}
        desc = EXPERIMENTS[key]['short']
        print(f'{key:<5} {desc:<28} {len(rows):<8} {np.mean(durs):<14.1f} {acc:<12.4f} {AoM}/{len(rows)}')

    a  = stats['A']['avg']
    b1 = stats['B1']['avg']; b2 = stats['B2']['avg']
    c1 = stats['C1']['avg']; c2 = stats['C2']['avg']

    print()
    print('--- KEY FINDINGS ---')
    print()
    print('  GOAL 1 - AoM reduces FL round duration under load:')
    print(f'    Load increases duration: A={a:.1f}s => B1={b1:.1f}s (+{b1-a:.1f}s) => B2={b2:.1f}s (+{b2-a:.1f}s)')
    print(f'    AoM pri 250 zahtjeva/s: B2={b2:.1f}s => C1={c1:.1f}s  (delta = {b2-c1:+.1f}s/round)')
    print(f'    AoM pri 400 zahtjeva/s: B2={b2:.1f}s => C2={c2:.1f}s  (delta = {b2-c2:+.1f}s/round)')
    print()
    print('  GOAL 2 - AoM does not degrade accuracy:')
    for key in EXPERIMENTS:
        diff = (stats[key]['acc'] - stats['A']['acc']) * 100
        print(f'    {key}: {stats[key]["acc"]:.4f}  ({diff:+.2f} pp vs baseline)  AoM triggers: {stats[key]["AoM"]}/{stats[key]["n"]}')
    print()


if __name__ == '__main__':
    print('Generating FL experiment analysis plots...')
    print()
    plot_per_round_duration()
    plot_avg_duration_bar()
    plot_AoM_benefit()
    plot_accuracy_curves()
    plot_final_accuracy_bar()
    plot_inflight_comparison()
    plot_inflight_B2_with_rounds()
    plot_inflight_C2_AoM_action()
    plot_loss_curves()
    plot_avg_client_fit()
    plot_loss_and_accuracy_combined()
    plot_rpi_cpu_usage_over_time()
    print_summary()
    print(f'All plots saved to {OUT_DIR}/')
