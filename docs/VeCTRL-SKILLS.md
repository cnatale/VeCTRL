# Skills
> **A Skill is a temporary redefinition of “good behavior” over the same underlying memory and control machinery.**

VeCTRL Skills are a subset of [Agent Skills Open Specification](https://agentskills.io/specification)


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
  Uσ,        // update policy
  Tσ         // termination / persistence rules
⟩
```

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

> This alone can make a Temporal Distance Reinforcement Learning system dramatically more stable.

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

This does **not** forbid actions; instead it *prefers* some trajectories.

---

## 3️⃣ Skill-specific reward / loss (Rσ)  ✅ critical

This is where a Skill becomes *meaningful*.

A Skill defines:

> **What success looks like over time**

Formally:

```
Rσ : (trajectory segment, sensors, state) → ℝ
```

This reward feeds the Temporal Distance update:

```
δσ = rσ(t+1) + γ max Qσ(s') − Qσ(s)
```

### Examples for an autonomous robot

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

---

## 4️⃣ Update policy (Uσ) hyperparameters

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

## Minimal viable Skill schema

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


# LLM-Generated Skills

In VeCTRL, skills can be authored by humans or generated dynamically by language models.

The purpose of LLM-generated skills is to provide **structured abstractions over reinforcement learning control.**

A skill can define:

• state filters  
• available actions  
• reward/cost functions  
• reinforcement learning hyperparameters  

Example skill:
Skill: obstacle_avoidance

state_filter:
distance_sensor < 0.5m

actions:
rotate_left
rotate_right
step_back

reward_function:
	•	distance_from_obstacle

	•	energy_cost

hyperparameters:
gamma: 0.9
learning_rate: 0.05
Skills reshape the effective state space by restricting which actions and rewards are active.

This allows the planner to change agent behavior by activating or generating skills.

---

# Dynamic Skill Generation

Language models can generate new skills in response to:

• planning requirements  
• failure analysis  
• environment observations  

Example:
Goal: navigate around obstacles

LLM generates:

skill: cautious_navigation

actions:
slow_forward
rotate_small

reward:
	•	forward_progress

	•	proximity_to_obstacle

These skills then influence the reinforcement learning controller.

---

# Skill Composition

Plans are expressed as sequences or hierarchies of skills.

Example:
plan:
	1.	locate_object
	2.	walk_to_object
	3.	grasp_object
	4.	walk_to_target
	5.	place_object

Each step activates a different skill configuration.

---

# Skill Influence on Control

When a skill is active it modifies:
vector memory filtering
reward evaluation
action selection
learning hyperparameters

This allows the planner to shape the control system without retraining policies.