# Analysis — Exp 001

Post-run analysis scripts for Exp 001 telemetry data.

Input: CSV files from `../data/`
Format: see `docs/architecture/telemetry-schema.md`

## Metrics to compute

### Control metrics
- **Settling time** — ticks until `|error| < threshold` is sustained for N consecutive ticks
- **Overshoot** — max `commanded_angle` beyond `target_angle` after first crossing
- **Oscillation amplitude** — std dev of `error` in the 10-second window after settling
- **Control smoothness** — mean `|action_value|` per skill segment

### Memory metrics
- **Memory growth rate** — `memory_size` slope over time
- **Retrieval consistency** — mean `neighbor_agreement` per skill
- **Mean Q-value** — running mean per skill segment

### Skill metrics
- **Reward accumulation** — cumulative `reward` per skill segment
- **Behavior change latency** — ticks until metrics diverge after a skill switch

## Planned scripts

| Script | Purpose |
|---|---|
| `settling_time.py` | Compute settling time per trial per skill |
| `skill_comparison.py` | Side-by-side metric comparison across the three Exp 1 variants |
| `memory_growth.py` | Plot `memory_size` vs. ticks, per skill |
| `tick_timing.py` | Plot `tick_duration_ms` distribution — GC health check |

## Skill switch detection

Skill switches are identifiable in the CSV by a change in the `skill_id` column. All metrics should be segmented by `(device_id, skill_id, run_start_ts)`.
