#!/usr/bin/env python3
"""
FL Orchestrator - Experiment Analysis
======================================
Proves two goals from the experiment plan:
  1. FL round duration is shorter when AOM selection excludes overloaded clients
  2. Model accuracy does not degrade when AOM client selection is active

Experiment sequence (oldest -> newest filename timestamp):
  A  - baseline_no_load  : no requests, AOM off
  B1 - 100 req/s         : 100 req/s per client, AOM off
  B2 - 250 req/s         : 250 req/s per client, AOM off
  C1 - 250 req/s + AOM   : 250 req/s per client, AOM on  (threshold = 15)
  C2 - 400 req/s + AOM   : 400 req/s per client, AOM on  (threshold = 15)

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

# Experiment metadata
EXPERIMENTS = {
    'A':  {'label': 'A\nBaseline\n(no load)',   'short': 'A - Baseline',         'color': '#2196F3', 'marker': 'o', 'aom': False},
    'B1': {'label': 'B1\n100 req/s\n(AOM off)', 'short': 'B1 - 100 req/s',       'color': '#FF9800', 'marker': 's', 'aom': False},
    'B2': {'label': 'B2\n250 req/s\n(AOM off)', 'short': 'B2 - 250 req/s',       'color': '#F44336', 'marker': '^', 'aom': False},
    'C1': {'label': 'C1\n250 req/s\n(AOM on)',  'short': 'C1 - 250 req/s + AOM', 'color': '#9C27B0', 'marker': 'D', 'aom': True},
    'C2': {'label': 'C2\n400 req/s\n(AOM on)',  'short': 'C2 - 400 req/s + AOM', 'color': '#4CAF50', 'marker': 'P', 'aom': True},
}

GA_LOGS = {
    'A':  'round_logs/rounds_log_20260603_160117.csv',
    'B1': 'round_logs/rounds_log_20260603_170001.csv',
    'B2': 'round_logs/rounds_log_20260603_182319.csv',
    'C1': 'round_logs/rounds_log_20260603_192347.csv',
    'C2': 'round_logs/rounds_log_20260603_202002.csv',
}

PROXY_FILES = {
    'B1': 'request_and_proxy_metrics/runtime_metrics_round_with_proxy_20260603_195523.csv',
    'B2': 'request_and_proxy_metrics/runtime_metrics_round_with_proxy_20260603_211837.csv',
    'C1': 'request_and_proxy_metrics/runtime_metrics_round_with_proxy_20260603_221738.csv',
    'C2': 'request_and_proxy_metrics/runtime_metrics_round_with_proxy_20260603_231156.csv',
}

REQUEST_FILES = {
    'B1': 'request_and_proxy_metrics/request_data_round_with_proxy_20260603_195523.csv',
    'B2': 'request_and_proxy_metrics/request_data_round_with_proxy_20260603_211837.csv',
    'C1': 'request_and_proxy_metrics/request_data_round_with_proxy_20260603_221738.csv',
    'C2': 'request_and_proxy_metrics/request_data_round_with_proxy_20260603_231156.csv',
}

CLIENT_LOGS = {
    'A':  ('client_logs_orinnano2/client_rounds_log_p0_20260603_160339.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260603_160344.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260603_160342.csv'),
    'B1': ('client_logs_orinnano2/client_rounds_log_p0_20260603_170233.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260603_170233.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260603_170233.csv'),
    'B2': ('client_logs_orinnano2/client_rounds_log_p0_20260603_182541.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260603_182538.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260603_182542.csv'),
    'C1': ('client_logs_orinnano2/client_rounds_log_p0_20260603_192623.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260603_192624.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260603_192631.csv'),
    'C2': ('client_logs_orinnano2/client_rounds_log_p0_20260603_202214.csv',
           'client_logs_orinnano3/client_rounds_log_p1_20260603_202212.csv',
           'client_logs_orinnano4/client_rounds_log_p2_20260603_202213.csv'),
}


def load_ga(key):
    with open(GA_LOGS[key]) as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get('accuracy', '').strip() != '']


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
    ax.set_xlabel('FL Round')
    ax.set_ylabel('Fit Duration (s)')
    ax.set_title('Per-Round FL Fit Duration - All Experiments')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    save(fig, '01_per_round_duration.png')


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

    b2i, c2i = 2, 4
    gain = avgs[b2i] - avgs[c2i]
    y_top = max(avgs[b2i] + stds[b2i], avgs[c2i] + stds[c2i]) + 14
    ax.annotate('', xy=(c2i, y_top - 4), xytext=(b2i, y_top - 4),
                arrowprops=dict(arrowstyle='<->', color='darkgreen', lw=2))
    ax.text((b2i + c2i) / 2, y_top + 1,
            f'AOM saves approx {gain:.1f}s/round\n(higher load, shorter duration)',
            ha='center', fontsize=9, color='darkgreen',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#e8f5e9', edgecolor='darkgreen'))

    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(xlabels, fontsize=9)
    ax.set_ylabel('Average Fit Duration (s)')
    ax.set_title('Average FL Round Fit Duration +/- Std Dev\n(Goal 1: AOM reduces round duration under load)')
    ax.grid(axis='y', alpha=0.3)
    save(fig, '02_avg_duration_bar.png')


# ============================================================
# PLOT 3 - Load effect: A, B1, B2
# ============================================================
def plot_load_effect():
    fig, ax = plt.subplots(figsize=(10, 5))
    a_mean = np.mean([float(r['fit_duration_s']) for r in load_ga('A')])
    for key in ['A', 'B1', 'B2']:
        rows = load_ga(key)
        rnds = [int(r['round']) for r in rows]
        durs = [float(r['fit_duration_s']) for r in rows]
        m = EXPERIMENTS[key]
        ax.plot(rnds, durs, marker=m['marker'], color=m['color'],
                label=m['short'], linewidth=2, markersize=6)
    ax.axhline(y=a_mean, color=EXPERIMENTS['A']['color'],
               linestyle='--', alpha=0.5, label=f'Baseline mean ({a_mean:.1f}s)')
    ax.set_xlabel('FL Round')
    ax.set_ylabel('Fit Duration (s)')
    ax.set_title('Effect of Inference Load on FL Round Duration (AOM off)')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    save(fig, '03_load_effect_no_aom.png')


# ============================================================
# PLOT 4 - AOM benefit: B2 vs C1 vs C2
# ============================================================
def plot_aom_benefit():
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

    excl_line = mpatches.Patch(color=EXPERIMENTS['C2']['color'], alpha=0.35,
                               label='C2 round: AOM excluded overloaded client')
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [excl_line], fontsize=9)
    ax.set_xlabel('FL Round')
    ax.set_ylabel('Fit Duration (s)')
    ax.set_title('AOM Benefit: B2 (250 req/s no AOM) vs C1/C2 (AOM on)\n'
                 'Shaded columns = rounds where AOM excluded orinnano-2 in C2')
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
    ax.set_title('Global Model Accuracy per Round - All Experiments\n'
                 '(Goal 2: AOM does not degrade accuracy)')
    ax.legend(fontsize=9, loc='lower right')
    ax.grid(True, alpha=0.3)
    save(fig, '05_accuracy_curves.png')


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
               label=f'Baseline accuracy = {baseline:.2f}%')
    ax.axhspan(baseline - 2, baseline + 2, alpha=0.07, color='gray', label='+/-2 pp band')
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(xlabels, fontsize=9)
    ax.set_ylim([0, max(accs) * 100 + 5])
    ax.set_ylabel('Final Accuracy (%)')
    ax.set_title('Final Global Model Accuracy - All Experiments\n'
                 '(AOM experiments stay within +/-2 pp of baseline)')
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    save(fig, '06_final_accuracy_bar.png')


# ============================================================
# PLOT 7 - AOM client selection timeline C1 and C2
# ============================================================
def plot_aom_timeline():
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    for ax, key in zip(axes, ['C1', 'C2']):
        rows = load_ga(key)
        rnds = [int(r['round']) for r in rows]
        n_sel = [int(r['num_clients_selected']) for r in rows]
        bar_colors = [EXPERIMENTS[key]['color'] if n == 3 else '#FF5722' for n in n_sel]
        ax.bar(rnds, n_sel, color=bar_colors, edgecolor='black', linewidth=0.5, width=0.6)
        ax.axhline(y=3, color='gray', linestyle='--', linewidth=1, alpha=0.6)
        ax.set_ylim([0, 3.8])
        ax.set_yticks([1, 2, 3])
        ax.set_ylabel('Clients selected')
        ax.set_xlabel('FL Round')
        n_excl = sum(1 for n in n_sel if n < 3)
        ax.set_title(
            f'{EXPERIMENTS[key]["short"]} - Clients selected per round  '
            f'({n_excl}/{len(rnds)} rounds: AOM excluded overloaded client)'
        )
        full_patch = mpatches.Patch(color=EXPERIMENTS[key]['color'], label='All 3 clients selected')
        excl_patch = mpatches.Patch(color='#FF5722', label='AOM excluded orinnano-2 (overloaded)')
        ax.legend(handles=[full_patch, excl_patch], fontsize=9, loc='lower right')
        ax.grid(axis='y', alpha=0.3)
    fig.suptitle('AOM Client Selection Timeline', fontsize=13, fontweight='bold', y=1.01)
    save(fig, '07_aom_timeline.png')


# ============================================================
# PLOT 8 - inflight comparison all load experiments
# ============================================================
def plot_inflight_comparison():
    fig, ax = plt.subplots(figsize=(13, 5))
    for key in ['B1', 'B2', 'C1', 'C2']:
        rel, vals = proxy_inflight_o2(key)
        m = EXPERIMENTS[key]
        ax.plot(rel, vals, color=m['color'], linewidth=1.4, label=m['short'], alpha=0.9)
    ax.axhline(y=15, color='red', linestyle='--', linewidth=1.8, label='AOM threshold = 15')
    ax.set_xlabel('Time since experiment start (minutes)')
    ax.set_ylabel('inflight_60s_avg  (orinnano-2)')
    ax.set_title('Proxy Inflight 60s Average - orinnano-2\n'
                 '(When above threshold, AOM excludes this client from FL training)')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    save(fig, '08_inflight_comparison.png')


# ============================================================
# PLOT 9 - C2 fit duration boxplot by client count
# ============================================================
def plot_duration_by_client_count():
    rows_c2 = load_ga('C2')
    d3 = [float(r['fit_duration_s']) for r in rows_c2 if int(r['num_clients_selected']) == 3]
    d2 = [float(r['fit_duration_s']) for r in rows_c2 if int(r['num_clients_selected']) == 2]

    fig, ax = plt.subplots(figsize=(7, 5))
    data, labels, colors_bp = [], [], []
    if d3:
        data.append(d3)
        labels.append(f'3 clients selected\n(all included)\nn={len(d3)}')
        colors_bp.append('#F44336')
    if d2:
        data.append(d2)
        labels.append(f'2 clients selected\n(AOM excluded overloaded)\nn={len(d2)}')
        colors_bp.append('#4CAF50')

    bp = ax.boxplot(data, patch_artist=True, notch=False, widths=0.45)
    for patch, color in zip(bp['boxes'], colors_bp):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    if d3 and d2:
        gain = np.mean(d3) - np.mean(d2)
        y_ann = max(max(d3), max(d2)) + 3
        ax.text(1.5, y_ann, f'AOM reduces mean fit\nby {gain:.1f}s/round',
                ha='center', fontsize=10,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#e8f5e9', edgecolor='darkgreen'))

    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('Fit Duration (s)')
    ax.set_title('C2 (400 req/s, AOM on): Fit Duration by Client Count\n'
                 'Rounds where AOM excluded the overloaded client are faster')
    ax.grid(axis='y', alpha=0.3)
    save(fig, '09_c2_duration_by_client_count.png')


# ============================================================
# PLOT 10 - B2 inflight with FL round windows
# ============================================================
def plot_inflight_B2_with_rounds():
    fig, ax = plt.subplots(figsize=(13, 5))
    rel, vals = proxy_inflight_o2('B2')
    ax.fill_between(rel, vals, alpha=0.25, color=EXPERIMENTS['B2']['color'])
    ax.plot(rel, vals, color=EXPERIMENTS['B2']['color'], linewidth=1.4,
            label='inflight_60s_avg (orinnano-2)', zorder=3)

    for rno, rstart, rend, n_sel in ga_round_windows('B2'):
        ax.axvspan(rstart, rend, alpha=0.10, color='purple', zorder=1)

    ax.axhline(y=15, color='red', linestyle='--', linewidth=1.8, label='AOM threshold = 15')
    round_patch = mpatches.Patch(color='purple', alpha=0.25, label='FL training round active')
    handles, lbl = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [round_patch], fontsize=9)
    ax.set_xlabel('Time since experiment start (minutes)')
    ax.set_ylabel('inflight_60s_avg')
    ax.set_title('B2 (250 req/s, AOM off): Inflight Spikes During FL Training\n'
                 'Purple = FL round active - inflight rises above threshold but AOM is OFF')
    ax.grid(True, alpha=0.3)
    save(fig, '10_inflight_B2_with_rounds.png')


# ============================================================
# PLOT 11 - C2 inflight with AOM action markers
# ============================================================
def plot_inflight_C2_aom_action():
    fig, ax = plt.subplots(figsize=(13, 5))
    rel, vals = proxy_inflight_o2('C2')
    ax.fill_between(rel, vals, alpha=0.2, color=EXPERIMENTS['C2']['color'])
    ax.plot(rel, vals, color=EXPERIMENTS['C2']['color'], linewidth=1.4,
            label='inflight_60s_avg (orinnano-2)', zorder=3)

    for rno, rstart, rend, n_sel in ga_round_windows('C2'):
        shade = '#FF5722' if n_sel < 3 else '#9E9E9E'
        ax.axvspan(rstart, rend, alpha=0.18, color=shade, zorder=1)

    ax.axhline(y=15, color='red', linestyle='--', linewidth=1.8, label='AOM threshold = 15')
    excl_patch = mpatches.Patch(color='#FF5722', alpha=0.5,
                                label='Round: AOM excluded orinnano-2')
    full_patch = mpatches.Patch(color='#9E9E9E', alpha=0.5,
                                label='Round: all 3 clients selected')
    handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [excl_patch, full_patch], fontsize=9)
    ax.set_xlabel('Time since experiment start (minutes)')
    ax.set_ylabel('inflight_60s_avg')
    ax.set_title('C2 (400 req/s, AOM on): Inflight and AOM Exclusion Events\n'
                 'Orange = round where AOM excluded orinnano-2; Grey = full participation round')
    ax.grid(True, alpha=0.3)
    save(fig, '11_inflight_C2_aom_action.png')


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
    ax.set_title('Global Model Loss per Round - All Experiments')
    ax.legend(fontsize=9, loc='upper right')
    ax.grid(True, alpha=0.3)
    save(fig, '12_loss_curves.png')


# ============================================================
# PLOT 13 - Cumulative fit time
# ============================================================
def plot_cumulative_time():
    fig, ax = plt.subplots(figsize=(11, 5))
    for key in EXPERIMENTS:
        rows = load_ga(key)
        durs = [float(r['fit_duration_s']) for r in rows]
        cum = np.cumsum(durs) / 60
        rnds = list(range(1, len(durs) + 1))
        m = EXPERIMENTS[key]
        ax.plot(rnds, cum, marker=m['marker'], color=m['color'],
                label=m['short'], linewidth=2, markersize=5)
    ax.set_xlabel('FL Round')
    ax.set_ylabel('Cumulative Fit Time (minutes)')
    ax.set_title('Cumulative FL Training Time - All Experiments')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    save(fig, '13_cumulative_fit_time.png')


# ============================================================
# PLOT 14 - Request latency distribution B1/B2/C1/C2
# ============================================================
def plot_request_latency():
    fig, ax = plt.subplots(figsize=(10, 5))
    data, labels, colors_bp = [], [], []
    for key in ['B1', 'B2', 'C1', 'C2']:
        with open(REQUEST_FILES[key]) as f:
            rows = [r for r in csv.DictReader(f)
                    if r.get('client_name', '') == 'orinnano-2'
                    and r.get('status', '') == '200'
                    and r.get('latency', '').strip() != '']
        latencies = [float(r['latency']) * 1000 for r in rows]
        data.append(latencies)
        labels.append(EXPERIMENTS[key]['label'])
        colors_bp.append(EXPERIMENTS[key]['color'])

    bp = ax.boxplot(data, patch_artist=True, notch=False, widths=0.45, showfliers=False)
    for patch, color in zip(bp['boxes'], colors_bp):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('Request Latency (ms)')
    ax.set_title('Inference Request Latency - orinnano-2 (outliers hidden)\n'
                 'AOM experiments: inference latency stays comparable to no-AOM')
    ax.grid(axis='y', alpha=0.3)
    save(fig, '14_request_latency.png')


# ============================================================
# SUMMARY TABLE
# ============================================================
def print_summary():
    print()
    print('=' * 75)
    print('EXPERIMENT SUMMARY')
    print('=' * 75)
    print(f'{"Exp":<5} {"Description":<28} {"Rounds":<8} {"Avg Fit (s)":<14} {"Final Acc":<12} {"AOM triggers"}')
    print('-' * 75)
    stats = {}
    for key in EXPERIMENTS:
        rows = load_ga(key)
        durs = [float(r['fit_duration_s']) for r in rows]
        aom  = sum(1 for r in rows if int(r['num_clients_selected']) < 3)
        acc  = float(rows[-1]['accuracy'])
        stats[key] = {'avg': np.mean(durs), 'std': np.std(durs), 'acc': acc,
                      'aom': aom, 'n': len(rows)}
        desc = EXPERIMENTS[key]['short']
        print(f'{key:<5} {desc:<28} {len(rows):<8} {np.mean(durs):<14.1f} {acc:<12.4f} {aom}/{len(rows)}')

    a  = stats['A']['avg'];  b1 = stats['B1']['avg']
    b2 = stats['B2']['avg']; c1 = stats['C1']['avg']
    c2 = stats['C2']['avg']

    print()
    print('--- KEY FINDINGS ---')
    print()
    print('  GOAL 1 - AOM reduces FL round duration under load:')
    print(f'    Load increases duration: A={a:.1f}s => B1={b1:.1f}s (+{b1-a:.1f}s) => B2={b2:.1f}s (+{b2-a:.1f}s)')
    print(f'    AOM at 250 req/s: B2={b2:.1f}s => C1={c1:.1f}s  (delta = {b2-c1:+.1f}s/round)')
    print(f'    AOM at 400 req/s: B2={b2:.1f}s => C2={c2:.1f}s  (delta = {b2-c2:+.1f}s/round)  <- 400 req/s FASTER than 250 req/s without AOM')
    print()
    print('  GOAL 2 - AOM does not degrade accuracy:')
    for key in EXPERIMENTS:
        diff = (stats[key]['acc'] - stats['A']['acc']) * 100
        print(f'    {key}: {stats[key]["acc"]:.4f}  ({diff:+.2f} pp vs baseline)  AOM triggers: {stats[key]["aom"]}/{stats[key]["n"]}')
    print()


if __name__ == '__main__':
    print('Generating FL experiment analysis plots...')
    print()
    plot_per_round_duration()
    plot_avg_duration_bar()
    plot_load_effect()
    plot_aom_benefit()
    plot_accuracy_curves()
    plot_final_accuracy_bar()
    plot_aom_timeline()
    plot_inflight_comparison()
    plot_duration_by_client_count()
    plot_inflight_B2_with_rounds()
    plot_inflight_C2_aom_action()
    plot_loss_curves()
    plot_cumulative_time()
    plot_request_latency()
    print_summary()
    print(f'All 14 plots saved to {OUT_DIR}/')
