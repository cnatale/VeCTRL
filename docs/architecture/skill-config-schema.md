# Skill Config Schema

## Package structure

Each VeCTRL skill is an [Agent Skills](https://agentskills.io/specification) package:

```
<skill-name>/
  SKILL.md          # Agent Skills frontmatter (name, description) + human/LLM instructions
  assets/
    config.json     # VeCTRL control config — loaded by SkillStore, sent to edge device
```

The `SKILL.md` `name` field must be lowercase with hyphens and match the directory name (e.g. `reach-target-fast`). The `assets/config.json` `skill_id` field should match the directory name.

## `assets/config.json` schema

A Skill config is a JSON object conforming to the VeCTRL Skill tuple:

```
σ = ⟨ Mσ, Wσ, Rσ, Uσ, Tσ, Dσ ⟩
```

The edge device's `SkillRunner` deserializes and evaluates this schema each tick. All top-level keys must be present; use `null` or `[]` for inactive components.

## Full Schema

```json
{
  "skill_id": "string",
  "description": "string",

  "memory_filter": {
    "required_tags": ["string"],
    "excluded_tags": ["string"],
    "partition": "string | null"
  },

  "distance_bias": {
    "<dimension_index_or_name>": 1.0
  },

  "reward": {
    "error_penalty": -1.0,
    "action_magnitude_penalty": 0.0,
    "smoothness_penalty": 0.0,
    "target_bonus": 5.0,
    "target_threshold_deg": 3.0
  },

  "learning": {
    "alpha": 0.1,
    "gamma": 0.9,
    "epsilon": 0.2,
    "neighbor_radius": 15.0,
    "k": 5,
    "initial_q": -45.0,
    "insertion_policy": "always",
    "min_td_error_to_insert": null,
    "min_visit_count_for_density_insert": null
  },

  "termination": {
    "min_duration_ms": 0,
    "max_duration_ms": null,
    "interruptible": true,
    "exit_conditions": []
  }
}
```

---

## Field Reference

### Top-level (Dσ)

| Field | Type | Description |
|---|---|---|
| `skill_id` | string | Unique identifier. Used for telemetry tagging and memory partitioning. |
| `description` | string | Human/planner-readable purpose of the skill. Used by LLM planner in Exp 7+. |

---

### `memory_filter` (Mσ)

Controls which memory entries are visible during KNN search. Active from Exp 3; use empty defaults for Exp 1–2.

| Field | Type | Description |
|---|---|---|
| `required_tags` | string[] | Entry must have **all** of these tags to be visible. `[]` = no filter. |
| `excluded_tags` | string[] | Entry must have **none** of these tags. `[]` = no exclusion. |
| `partition` | string\|null | If set, only entries whose `skill_id` matches this value are visible. Enables per-skill memory isolation. |

**Effect:** Filtering changes the topology of the action space. A skill with `"partition": "fast_reach"` only sees experience accumulated under that skill, preventing cross-contamination of learned behaviors.

---

### `distance_bias` (Wσ)

Per-dimension multipliers applied to KNN distance computation. `{}` = identity (uniform distance). Active from Exp 4.

```json
{ "2": 2.0, "3": 0.5 }
```

This doubles the weight of dimension 2 (error) and halves dimension 3 (prev_error) in the L2 distance, pulling retrieval toward states with similar current error regardless of velocity history.

Keys are dimension indices as strings (matching Python dict key behavior on the ESP32).

---

### `reward` (Rσ)

Evaluated each tick:

```
r = error_penalty          * |error|
  + action_magnitude_penalty * |action_value|
  + smoothness_penalty     * |action_value − prev_action_value|
  + target_bonus           if |error| < target_threshold_deg
```

| Field | Type | Description |
|---|---|---|
| `error_penalty` | float | Multiplied by absolute angle error. Negative = penalize distance from target. |
| `action_magnitude_penalty` | float | Multiplied by absolute action size. Negative = penalize large moves (energy). |
| `smoothness_penalty` | float | Multiplied by action change from previous step. Negative = penalize jerk. |
| `target_bonus` | float | Added when `|error| < target_threshold_deg`. Positive = reward arrival. |
| `target_threshold_deg` | float | Error tolerance for target_bonus. |

**Exp 1 variants:**

| Skill | `error_penalty` | `action_magnitude_penalty` | `smoothness_penalty` |
|---|---|---|---|
| `reach_target_fast` | -1.0 | 0.0 | 0.0 |
| `reach_target_smoothly` | -0.5 | 0.0 | -0.5 |
| `reach_target_with_low_energy` | -0.5 | -0.5 | 0.0 |

---

### `learning` (Uσ)

RL hyperparameters. Can be varied per-skill from Exp 3 onward.

| Field | Type | Description |
|---|---|---|
| `alpha` | float | Q-learning rate (0–1). Higher = faster adaptation, less stability. |
| `gamma` | float | Discount factor (0–1). Higher = weight future rewards more. |
| `epsilon` | float | Exploration rate for epsilon-greedy (0–1). |
| `neighbor_radius` | float | Max L2 distance for a candidate to count as a neighbor. Tune to match state space scale. |
| `k` | int | Number of nearest neighbors to retrieve. |
| `initial_q` | float | Q-value assigned to newly inserted memory entries. Pessimistic values (e.g. -45.0) prevent untested entries from appearing better than entries with learned Q-values. |
| `insertion_policy` | string | When to add new memory entries. See below. |
| `min_td_error_to_insert` | float\|null | Threshold for `td_error_threshold` policy. |
| `min_visit_count_for_density_insert` | int\|null | Threshold for `visit_density` policy. |

**Insertion policies (Exp 2):**

| Policy | Behavior |
|---|---|
| `"always"` | Insert a new entry every tick. Memory grows continuously. |
| `"td_error_threshold"` | Insert only when `|δ| > min_td_error_to_insert`. Focuses memory on surprising transitions. |
| `"visit_density"` | Insert only in low-density state regions. Prevents over-sampling common states. |

---

### `termination` (Tσ)

Skill exit conditions evaluated by the coordinator's `SkillManager`. Active from Exp 3.

| Field | Type | Description |
|---|---|---|
| `min_duration_ms` | int | Skill must be active at least this long before the coordinator can switch away. Prevents thrashing. |
| `max_duration_ms` | int\|null | Force skill exit after this duration. `null` = no limit. |
| `interruptible` | bool | Whether a planner can switch away before `min_duration_ms` on an urgent signal. |
| `exit_conditions` | array | Reserved for structured condition expressions (Exp 7+). |
