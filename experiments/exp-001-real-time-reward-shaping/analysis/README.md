# Analysis — Exp 001

Post-run analysis scripts for Exp 001 telemetry data.

Input: CSV files from `../data/`
Format: see `docs/architecture/telemetry-schema.md`

## Metric definitions

All metrics are computed from software-tracked telemetry values (`commanded_angle`, `error`, `action_value`), not from physical sensor feedback. No encoder, IMU, or position sensor is connected in the Exp 1 rig. These metrics describe the **control policy's** behavior — mechanical effects like backlash, inertia, and stalling are invisible without sensor feedback.

- **Settling time** — number of telemetry rows (and corresponding wall-clock ms) until `|error| < threshold` is sustained for N consecutive rows. `error` is `target_angle − commanded_angle`, so this measures how long the RL agent takes to converge its commanded position on the target — not how long the physical servo takes to reach it.
- **Overshoot** — max `|commanded_angle − target_angle|` observed after the commanded angle first enters the threshold band around the target. Measures how far the agent drives the commanded position past the target before correcting. A purely software phenomenon: the agent keeps applying positive deltas past the target.
- **Action jerk** — RMS of consecutive `action_value` differences. Measures how erratic the agent's action choices are from tick to tick. Low jerk means the agent picks similar actions in succession (e.g., +1, +1, +1); high jerk means it oscillates (e.g., +10, −5, +10). Entirely derived from the agent's policy output.
- **Control smoothness** — mean `|action_value|` per skill segment. Lower values mean the agent is choosing smaller, gentler deltas on average. A direct measure of how aggressively the policy acts.
- **Oscillation amplitude** — std dev of `error` in the 10-second window after settling.

## Metrics to compute

### Control metrics
- Settling time
- Overshoot
- Oscillation amplitude
- Control smoothness
- Action jerk

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
