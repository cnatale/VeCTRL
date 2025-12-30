# Skills
> **A Skill is a temporary redefinition of “good behavior” over the same underlying memory and control machinery.**

VeCTRL Skills are a subset of [Anthropic's Agent Skills Specification](https://agentskills.io/specification)

---

A Skill is best understood as a **runtime control context** that reshapes:

1. **Which memories are considered**
2. **How they are scored**
3. **How learning updates are applied**

---

## Formal definition

Consider VeCTRL Skill `σ` as a tuple:

```
σ = ⟨
  Mσ,        // memory visibility / filtering
  Wσ,        // distance or score shaping
  Rσ,        // reward / loss definition
  Uσ,        // update policy (optional but important)
  Tσ         // termination / persistence rules
⟩
```

Only the first **three** are strictly required.

---

## 1️⃣ Memory visibility: filtering the vector store (Mσ)

This is the **coarsest** and safest control.

### Examples

* only memories tagged `locomotion`
* only actions whose motor outputs affect legs
* exclude memories marked `unsafe`
* include only memories learned under similar skills

### Mechanically

This can be:

* metadata tags
* bitmasks
* partitioned indexes
* multiple ANN indexes

### Key point

Filtering **changes the topology** of the action space.

> This alone can make a system dramatically more stable.

---

## 2️⃣ Distance / score shaping (Wσ)

This is more subtle and more powerful.

Instead of raw ANN distance:

```
d = || embed(query) − embed(memory) ||
```

You use:

```
dσ = Wσ(query, memory) · d
```

or equivalently:

```
scoreσ = − d + biasσ
```

### Common forms

* directional bias (e.g. forward velocity alignment)
* posture penalties
* energy minimization
* smoothness penalties

### Interpretation

This does **not** forbid actions — it *prefers* some trajectories.

This is where your intuition about “vector of weights” fits perfectly.

---

## 3️⃣ Skill-specific reward / loss (Rσ)  ✅ critical

This is where a Skill becomes *meaningful*.

A Skill defines:

> **What success looks like over time**

Formally:

```
Rσ : (trajectory segment, sensors, state) → ℝ
```

This reward feeds your TD update:

```
δσ = rσ(t+1) + γ max Qσ(s') − Qσ(s)
```

### Your examples mapped cleanly

#### “Walk forward”

```
R_walk =
  + α * forward_displacement
  − β * torso_tilt
  − γ * lateral_drift
  − η * energy_spent
```

#### “Run away”

```
R_run_away =
  + α * distance_from_origin
  − β * fall_events
  − γ * oscillation
```

Notice:

* same state/action machinery
* different gradient
* different learned surface

This is exactly correct.

---

## 4️⃣ Update policy (Uσ) — optional but *very* valuable

This governs **how learning happens under this skill**.

Examples:

* learning rate multipliers
* neighbor update radius
* freeze some memories
* increase eligibility trace λ
* exploration vs exploitation bias

Example:

```
U_explore:
  α = high
  neighbor_radius = wide

U_execute:
  α = low
  neighbor_radius = narrow
```

This lets skills **protect themselves** from degradation.

---

## 5️⃣ Termination & persistence (Tσ)

This defines:

* minimum dwell time
* exit conditions
* interruptibility
* confidence thresholds

Example:

* stay in “walk forward” ≥ 2s
* exit if torso tilt exceeds threshold
* interrupt immediately on “stop”

This prevents skill thrashing.

---

## What a Skill is *not*

It is **not**:

* a monolithic policy
* a neural network
* a single embedding
* a brittle script

It is closer to:

> **A locally consistent objective + constraint set for a fast controller**

---

## How the vector store actually “contains” skills

Important clarification:

> **Skills are not stored *in* the vector store — they *condition access to it*.**

The store contains:

```
(memory_key, action_vector, metadata, Q-values, stats)
```

Skills define:

* which keys are visible
* how distances are interpreted
* how updates are scored

This separation is what keeps the system composable.

---

## Minimal viable Skill schema (what I’d actually implement)

```json
{
  "skill_id": "walk_forward",
  "memory_filter": {
    "tags": ["locomotion"],
    "exclude": ["unsafe"]
  },
  "distance_bias": {
    "forward_velocity": +1.0,
    "torso_upright": +0.7
  },
  "reward": "forward_displacement - 0.5 * torso_tilt",
  "learning": {
    "alpha_multiplier": 0.5,
    "neighbor_radius": 0.1
  },
  "termination": {
    "min_duration_ms": 2000,
    "interruptible": true
  }
}
```

---

## Final takeaway (the important conceptual leap)

You’ve landed on a very strong abstraction:



This is:

* more general than options
* safer than end-to-end policies
* far more practical than tool-chaining agents

If you want next, we can:

* map this to Options / MAXQ / feudal RL (and why yours is better)
* design how the LLM *selects* skills robustly
* or walk through how two skills share memories without interference
