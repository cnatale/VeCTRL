---
name: reach-target-fast
description: VeCTRL servo control skill that optimizes for fast target acquisition. Applies a strong error penalty with no smoothness or energy constraints. Use when speed of arrival is the primary objective and overshoot is acceptable.
metadata:
  vectrl-skill-type: servo-control
  vectrl-platforms: A, B
  vectrl-sigma-components: Rσ, Uσ
---

# reach-target-fast

A VeCTRL control skill that configures the edge device's reward function for fast servo target acquisition. Prioritizes settling speed over motion quality.

## When to activate

- Task requires rapid servo positioning
- Settling time is the primary success metric
- Smoothness and energy consumption are not constraints
- Compare against `reach-target-smoothly` and `reach-target-with-low-energy` to demonstrate reward shaping

## Reward structure (Rσ)

| Component | Weight | Effect |
|---|---|---|
| Error penalty | -1.0 | Strong pull toward target — large actions preferred |
| Action magnitude | 0.0 | No energy constraint |
| Smoothness | 0.0 | No jerk penalty |
| Target bonus | +5.0 | Awarded when \|error\| < 3° |

## Hyperparameters (Uσ)

- `alpha`: 0.1 — moderate learning rate
- `gamma`: 0.9 — standard discount
- `epsilon`: 0.2 — 20% exploration
- `neighbor_radius`: 15.0 — broad retrieval
- `insertion_policy`: always

## How to load

The VeCTRL control config is in `assets/config.json`. Load and send via the coordinator:

```python
skill = skill_store.load("reach-target-fast")
comm.send_skill_config(device_id, skill)
```

## Expected behavior

The controller will select large delta-angle actions early in the trajectory, accepting overshoot in exchange for fast first arrival. Memory accumulates aggressive approach trajectories. Compare `tick_duration_ms` and settling time in telemetry against the other Exp 1 variants.

## Generating new skills based on this one

To generate a variant, adjust the `reward` weights in `assets/config.json`:
- Increase `error_penalty` magnitude for more aggressive approach
- Add a nonzero `action_magnitude_penalty` to introduce energy awareness
- Add a nonzero `smoothness_penalty` to reduce jerk
Keep all other fields unchanged unless explicitly varying hyperparameters.
