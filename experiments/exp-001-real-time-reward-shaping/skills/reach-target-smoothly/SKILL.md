---
name: reach-target-smoothly
description: VeCTRL servo control skill that balances target acquisition with smooth motion. Penalizes abrupt action changes. Use when motion quality matters alongside arrival accuracy.
metadata:
  vectrl-skill-type: servo-control
  vectrl-platforms: A, B
  vectrl-sigma-components: Rσ, Uσ
---

# reach-target-smoothly

A VeCTRL control skill that trades some arrival speed for continuous, jerk-free motion. Useful for tasks where mechanical wear or visual smoothness matters.

## When to activate

- Task requires steady, continuous servo motion
- Oscillation or jerk is undesirable
- Compare against `reach-target-fast` to observe how smoothness_penalty reshapes behavior
- Post-target stability is as important as arrival time

## Reward structure (Rσ)

| Component | Weight | Effect |
|---|---|---|
| Error penalty | -0.5 | Moderate pull toward target |
| Action magnitude | 0.0 | No energy constraint |
| Smoothness | -0.5 | Penalizes change in action between ticks |
| Target bonus | +5.0 | Awarded when \|error\| < 3° |

The smoothness penalty discourages alternating between large positive and negative actions — the controller learns to commit to a direction and decelerate gradually.

## Hyperparameters (Uσ)

- `alpha`: 0.1
- `gamma`: 0.95 — slightly higher than `reach-target-fast`; values smooth long-horizon trajectories more
- `epsilon`: 0.15 — less exploration (smoother behavior is more predictable)
- `neighbor_radius`: 15.0
- `insertion_policy`: always

## How to load

```python
skill = skill_store.load("reach-target-smoothly")
comm.send_skill_config(device_id, skill)
```

## Expected behavior

The controller will prefer smaller, consistent delta-angle actions. Settling time will be longer than `reach-target-fast`, but action entropy and oscillation amplitude will be lower. Watch `action_value` in telemetry for reduced variance.

## Generating new skills based on this one

To increase smoothness emphasis, raise `smoothness_penalty` magnitude (e.g. -0.8). To balance with faster arrival, raise `error_penalty` magnitude simultaneously. Increasing `gamma` further (e.g. 0.98) makes the controller value smooth approach over the full trajectory.
