---
name: reach-target-with-low-energy
description: VeCTRL servo control skill that minimizes total actuator movement while reaching the target. Penalizes large delta-angle commands. Use when energy efficiency or mechanical wear is a constraint.
metadata:
  vectrl-skill-type: servo-control
  vectrl-platforms: A, B
  vectrl-sigma-components: Rσ, Uσ
---

# reach-target-with-low-energy

A VeCTRL control skill that optimizes for minimal cumulative actuator effort. The controller learns to reach the target in fewer, smaller movements rather than in one fast sweep.

## When to activate

- Energy consumption or mechanical wear is a concern
- Task allows slower approach if total movement is reduced
- Compare against `reach-target-fast` to measure the energy vs. speed tradeoff
- Useful as a baseline for comparing action entropy across skills

## Reward structure (Rσ)

| Component | Weight | Effect |
|---|---|---|
| Error penalty | -0.5 | Moderate pull toward target |
| Action magnitude | -0.5 | Penalizes large delta-angle commands each tick |
| Smoothness | 0.0 | No jerk penalty |
| Target bonus | +5.0 | Awarded when \|error\| < 3° |

The action magnitude penalty directly discourages large moves. The controller learns to prefer `+1` or `+2` degree steps over `+10` degree steps, even when far from target.

## Hyperparameters (Uσ)

- `alpha`: 0.1
- `gamma`: 0.9
- `epsilon`: 0.15 — less exploration than `reach-target-fast`
- `neighbor_radius`: 15.0
- `insertion_policy`: always

## How to load

```python
skill = skill_store.load("reach-target-with-low-energy")
comm.send_skill_config(device_id, skill)
```

## Expected behavior

The controller will overwhelmingly select small-magnitude actions. Mean `|action_value|` in telemetry will be significantly lower than `reach-target-fast`. Settling time will be longer. This skill demonstrates that the same hardware exhibits measurably different energy profiles purely from reward function changes.

## Generating new skills based on this one

To tune the energy-speed tradeoff, adjust the ratio of `error_penalty` to `action_magnitude_penalty`. A 2:1 ratio (-1.0 / -0.5) favors speed; a 1:2 ratio (-0.5 / -1.0) strongly favors efficiency. You can combine with `smoothness_penalty` for smooth low-energy motion.
