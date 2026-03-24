# Telemetry Schema

The edge device sends one UDP packet per control tick to the coordinator. Packets are JSON-encoded.

## Packet Format

```json
{
  "type": "telemetry",
  "device_id": "esp32-arm",
  "skill_id": "reach_target_fast",
  "ts": 1234567890,

  "state": {
    "commanded_angle": 90.0,
    "target_angle": 120.0,
    "error": -30.0,
    "prev_error": -32.0
  },

  "action": {
    "idx": 6,
    "value": 2
  },

  "learning": {
    "reward": -29.8,
    "q_value": 0.43,
    "td_error": 0.12,
    "epsilon": 0.2
  },

  "memory": {
    "size": 47,
    "retrieval_k": 5,
    "neighbor_agreement": 0.6,
    "tick_duration_ms": 18.4
  },

  "skill": {
    "elapsed_ms": 1200
  }
}
```

---

## Field Reference

### Top-level

| Field | Type | Description |
|---|---|---|
| `type` | string | Always `"telemetry"`. Allows coordinator to route mixed message types. |
| `device_id` | string | Identifies the sending device. Routes telemetry in multi-device setups. |
| `skill_id` | string | Active skill at time of this tick. |
| `ts` | int | Milliseconds since ESP32 boot (`time.ticks_ms()`). Not wall-clock time. |

### `state`

Current control state. Extended in Exp 4+ when sensors are added.

| Field | Description |
|---|---|
| `commanded_angle` | Last angle commanded to the servo (degrees, 0–180). |
| `target_angle` | Current target from coordinator (degrees). |
| `error` | `target_angle − commanded_angle`. Negative = servo is past target. |
| `prev_error` | Error at previous tick. Together with `error`, captures angular velocity. |

### `action`

| Field | Description |
|---|---|
| `idx` | Index into `ACTION_SET = [-10, -5, -2, -1, 0, 1, 2, 5, 10]`. |
| `value` | Actual delta-degrees applied this tick (`ACTION_SET[idx]`). |

### `learning`

| Field | Description |
|---|---|
| `reward` | Rσ evaluated this tick. |
| `q_value` | Q-value of the retrieved (state, action) entry. 0.0 if no neighbors found. |
| `td_error` | TD error δ this tick. Key signal for Exp 2 insertion policies. |
| `epsilon` | Current exploration rate (from active skill config). |

### `memory`

| Field | Description |
|---|---|
| `size` | Total entries in the VMS. Watch for growth rate in Exp 2. |
| `retrieval_k` | Neighbors actually returned (may be < k when memory is sparse). |
| `neighbor_agreement` | Fraction of k neighbors that agree on the best action (0–1). Leading indicator of memory convergence. Low agreement = memory still exploring. |
| `tick_duration_ms` | Wall time for this control tick. **Monitor for GC pause spikes** — values > 30ms in MicroPython indicate GC pressure and may warrant switching to Arduino. |

### `skill`

| Field | Description |
|---|---|
| `elapsed_ms` | Time since current skill was loaded. Used to enforce Tσ `min_duration_ms`. |

---

## Coordinator CSV Format

The coordinator writes one row per packet to `experiments/exp-NNN-*/data/`:

```
ts,device_id,skill_id,commanded_angle,target_angle,error,prev_error,action_idx,action_value,reward,q_value,td_error,epsilon,memory_size,retrieval_k,neighbor_agreement,tick_duration_ms,skill_elapsed_ms
```

Files are named: `{device_id}_{experiment_id}_{YYYYMMDD_HHMMSS}.csv`

---

## Derived Metrics (computed post-run in `analysis/`)

These are not in the raw telemetry but are computed from it:

| Metric | Computation |
|---|---|
| Settling time | Ticks until `|error| < threshold` is sustained for N consecutive ticks |
| Overshoot | Max `commanded_angle` beyond `target_angle` after first crossing |
| Oscillation amplitude | Std dev of `error` after settling |
| Control smoothness | Mean `|action_value|` over a run segment |
| Reward accumulation | Cumulative sum of `reward` per skill |
| Memory growth rate | `memory_size` slope over time |
