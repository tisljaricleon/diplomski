# Experiment Plan

## Goal

1. Prove round duration is shorter when AOM selection excludes overloaded clients
2. Prove accuracy/loss does not degrade when using client selection + AOM

---

## Experiment Matrix

| Exp | Load rate (orinnano-2) | AOM              | Purpose                   |
| --- | ---------------------- | ---------------- | ------------------------- |
| A   | none                   | off              | Clean baseline            |
| B1  | 50 req/s               | off              | Low load, no selection    |
| B2  | 100 req/s              | off              | Medium load, no selection |
| B3  | 200 req/s              | off              | High load, no selection   |
| C1  | 100 req/s              | on, threshold=15 | Low load + selection      |
| C2  | 250 req/s              | on, threshold=15 | Medium load + selection   |
| C3  | 500 req/s              | on, threshold=15 | High load + selection     |

---

## What This Proves

- **B1 → B2 → B3**: round duration increases with load when overloaded client is always included (shows the problem grows with load)
- **B3 vs C3**: AOM cuts round duration at peak load (main claim)
- **A vs C1/C2/C3**: accuracy stays stable despite selection (second claim)
- **C1 → C2 → C3**: even with AOM on, accuracy doesn't degrade as load grows (strongest version of the second claim)

> At 50 req/s, orinnano-2 sits at ~1-5 inflight avg, so AOM probably won't trigger — B1 and C1 will look identical. This is useful: it proves selection doesn't interfere when there's no reason to use it.

---

## start.sh Settings

**Experiments A, B1, B2, B3 — AOM off:**

```json
"aomSelectionEnabled": false,
"inflightThreshold": 999999.0
```

**Experiments C1, C2, C3 — AOM on:**

```json
"aomSelectionEnabled": true,
"inflightThreshold": 35.0,
"aomRoundsThreshold": 3
```

**All experiments:**

```json
"globalRounds": 11,
"minFitClients": 3,
"minEvaluateClients": 3,
"minAvailableClients": 3
```

---

## test.py Load Rates (CLIENT_MAP orinnano-2)

```python
# B1 / C1 — low load
"load_rate": 50

# B2 / C2 — medium load
"load_rate": 100

# B3 / C3 — high load
"load_rate": 200
```

---

## Execution Steps (per experiment)

1. Reset cluster — clear old model checkpoints so all runs start identically
2. Start FL: `bash start.sh`
3. Immediately start load test (B and C experiments only):
   ```
   python test.py --scenario <name>
   ```
4. Let FL finish all 11 rounds
5. Save outputs:
   - `rounds_log.csv` from GA pod
   - `runtime_metrics_<name>.csv` from test.py

---

## Suggested Scenario Names

| Exp | Scenario name    |
| --- | ---------------- |
| A   | baseline_no_load |
| B1  | load50_no_aom    |
| B2  | load100_no_aom   |
| B3  | load200_no_aom   |
| C1  | load50_with_aom  |
| C2  | load100_with_aom |
| C3  | load200_with_aom |

---

## Metrics to Compare

| Metric                        | Source                               | A vs B   | B vs C              | A vs C                   |
| ----------------------------- | ------------------------------------ | -------- | ------------------- | ------------------------ |
| Per-round `duration_s`        | rounds_log.csv                       | baseline | B should be slowest | —                        |
| Final accuracy                | rounds_log.csv                       | baseline | C should match A    | C should match A         |
| Selected clients per round    | rounds_log.csv `selected_client_ids` | always 3 | always 3            | orinnano-2 often skipped |
| `inflight_60s_avg` orinnano-2 | runtime_metrics.csv                  | —        | confirm load level  | confirm load level       |
