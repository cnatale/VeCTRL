# Can You Reshape a Controller's Behavior at Runtime, in the Physical World, on a $5 Chip?

*A technical deep dive into Experiment 001 of [VeCTRL](https://github.com/cnatale/veCTRL) — real-time reward shaping on a single-servo rig*

---

In modern AI systems, changing an agent’s behavior is often as simple as changing its objective.

In LLM-based systems, the quickest way to achieve this is updating a system prompt or modifying the context. The model stays the same, but the behavior shifts immediately.

That raises a more interesting question:

**Can that same idea work inside a real-time control loop, on constrained hardware, interacting with the physical world?**

Not in simulation. Not with a GPU.  
But on an ESP32, running at 20 Hz, driving a motor.

More concretely:

**Can you change what a controller is optimizing for in the middle of execution, without retraining, without redeploying code, and without interrupting the control loop?**

This experiment explores that question.

The short answer: yes, with caveats. The behavioral differences between skills are real and measurable. But the path to getting there involved multiple failure modes and one architectural tradeoff that reshaped a core assumption. I think the story is worth sharing, because the failures reveal as much as the successes.

---

## What VeCTRL Is

[VeCTRL](https://github.com/cnatale/veCTRL) represents an architectural bet:

**Can a higher-level planner that sits outside the fast control loop shape real-time physical behavior by changing the objective and learning dynamics of an on-device controller?**

In the version tested here, the low-latency loop runs on the edge device. It observes state, selects actions, and updates local action values in real time. That loop has to stay simple, cheap, and responsive enough to run on constrained hardware.

The higher-level layer lives off-device. Today that is a laptop coordinator. Eventually, the goal is for that layer to be an LLM-based agent.

But the LLM is not meant to micromanage motor actions at control-loop frequency. It is outside the loop. Its role is to inspect available skills, choose among them, or generate new ones by modifying things like:

- the cost function
- reward weights
- exploration parameters
- termination conditions
- other learning hyperparameters

In other words, the planner does not directly control the servo. It changes what the servo controller is trying to optimize, and how it learns while doing so.

Experiment 001 is a first test of that separation. Before asking whether an LLM can select or author useful skills, I wanted to know whether swapping structured objectives in real time would actually produce distinct physical behavior on-device.

That is the narrower question this experiment is trying to validate.

---

## Setup

The physical setup was deliberately minimal. A single 9g micro servo connected to an ESP32 microcontroller running MicroPython. The task: move the servo to a target angle and hold it there.

The software splits into two layers:

```
COORDINATOR (Python — Laptop)
  Owns: skill library, telemetry logging, CLI
  Sends: skill config JSON (on switch), target angle

              ↕ WiFi / UDP

EDGE DEVICE (MicroPython – ESP32)
  Owns: vector memory store, KNN, Q-learning, servo actuation
  Sends: telemetry stream (UDP)
```

The control loop targets **20 Hz** — one complete RL step every 50ms. The coordinator only sends structured JSON messages that the edge device picks up between ticks.

---

## The Skill Abstraction

Each "skill" is not a policy. It's an **objective configuration** — a structured description of what success looks like, how to measure it, and how to learn under it.

Formally, a skill σ is a six-tuple:

```
σ = ⟨ Mσ, Wσ, Rσ, Uσ, Tσ, Dσ ⟩
```

- **Mσ** (memory filter): which memory entries are visible during KNN retrieval — tags, partitions, exclusions. Changes the topology of what the controller can even consider.
- **Wσ** (distance bias): per-dimension scaling applied to the KNN distance metric. Certain state dimensions can be made more or less influential without changing stored vectors.
- **Rσ** (reward function): weights for error penalty, action magnitude cost, smoothness cost, and target bonus. This is where the objective lives.
- **Uσ** (update policy): learning rate α, discount γ, exploration rate ε, neighbor radius, insertion policy.
- **Tσ** (termination): minimum and maximum duration, exit conditions, interruptibility.
- **Dσ** (description): natural language description — readable by humans and by LLMs in future experiments.

Two skills were tested in this experiment:

**`reach_target_fast`**: Heavy penalty on angular error, no penalty on action magnitude or smoothness. Optimizes pure error reduction.

**`reach_target_smoothly`**: Error penalty paired with a smoothness penalty — cost applied to the delta between consecutive action values. The controller should prefer gradual moves over sharp ones.

The memory store architecture, KNN code, and hardware remain constant. Different reward weights lead to different behavior.

---

## The Control Loop in Detail

Each 50ms tick runs this sequence:

1. Build a 2D state vector: `[error, prev_error]` where `error = target_angle - commanded_angle`
2. Query the vector memory store (VMS) with KNN search, using Mσ filtering and Wσ distance shaping
3. Epsilon-greedy action selection over neighbor Q-values; random action if no candidates
4. Clamp the selected delta to servo limits and apply it
5. Compute the new error and evaluate Rσ to get the reward
6. TD update on the credited neighbor: `δ = r + γ·max_Q(s') − Q(s,a)`, then `Q(s,a) += α·δ`
7. Conditional insertion: write `(state, action, Q)` into the VMS per insertion policy
8. Check Tσ termination conditions
9. Emit telemetry over UDP every 10 ticks

When a new skill config arrives, the edge device loads it and clears the VMS. The next tick begins learning fresh under the new objective.

---

## What Broke, and Why It Matters

Three failure modes appeared before the experiment produced clean data. Each reveals something real about this class of controller.

### 1. Out-of-memory errors from JSON serialization

The initial telemetry code called `json.dumps()` on a nested dict every tick. On an ESP32 running MicroPython, this allocates multiple intermediate objects on a heap shared with everything else the runtime is doing. At 20 Hz the GC couldn't keep up.

The fix was to pre-bake the telemetry JSON as a format string and populate it with `%`-formatting:

```python
_TELEM_FMT = (
    '{"type":"telemetry","device_id":"%s","skill_id":"%s","ts":%d,'
    '"state":{"commanded_angle":%s,"target_angle":%s,"error":%s,"prev_error":%s},'
    '"action":{"idx":%d,"value":%d},'
    '"learning":{"reward":%s,"q_value":%s,"td_error":%s,"epsilon":%s},'
    '"memory":{"size":%d,"retrieval_k":%d,"neighbor_agreement":%s,'
    '"tick_duration_ms":%d},"skill":{"elapsed_ms":%d}}'
)
```

One string allocation instead of seven nested dict allocations led to peak heap cost dropping from ~1.2 KB per send to ~0.5 KB. State dimensionality was also reduced from 4D to 2D — keeping only `[error, prev_error]`, halving the memory footprint of every VMS entry.

The VMS itself uses pre-allocated parallel arrays initialized at startup:

```python
self._states = array.array("f", [0.0] * (n * d))
self._actions = array.array("B", [0] * n)
self._q_values = array.array("f", [0.0] * n)
self._visit_counts = array.array("H", [0] * n)
```

This eliminates per-entry object allocation. Heap footprint is fixed at init time.

### 2. Convergence failure: the "confident no-op" deadlock

After the OOM issues were resolved, a different failure appeared. The controller would settle at an angle 20–30 degrees from the target and stop moving.

The mechanism: once the VMS had accumulated enough entries, KNN retrieval in the neighborhood around the controller's current state would return a consensus of no-op actions — neighbors that had historically not moved the servo had accumulated visits, and therefore relatively high Q-values. The controller kept retrieving this cluster, confirming it with more visits, and remained deadlocked.

This is not a bug. It's correct behavior for a controller that has converged on a local optimum. But it's pathological when the local optimum is far from the target.

The fix was an escape heuristic: if error is above a threshold and the greedy action from KNN is a no-op, override with a random non-no-op:

```python
escape_deg = self.skill.noop_escape_error_deg()
if (
    abs(error_before) >= escape_deg
    and best_action_idx == self._noop_action_idx
):
    idx = random.randint(0, n_act - 2)
    if idx >= self._noop_action_idx:
        idx += 1
    return idx, 0.0, 0.0, -1, -1.0
```

This is credited as an exploratory action and breaks the deadlock without corrupting the existing Q-value surface.

### 3. TD update degradation from shared KNN state

To minimize tick duration, the initial implementation used a single KNN query per tick. The same neighbors found for action selection were also used to estimate `max_Q(s')` for the TD update. However, neighbors of `s` (the pre-action state) are not neighbors of `s'` (the post-action state). Using them as a proxy for `max_Q(s')` degraded the accuracy of the TD signal, because the wrong neighborhood was being used to estimate future value.

The correct approach requires separate neighbor sets for `s` and `s'`. But two full O(n) scans per tick doubles the compute budget, which is already tight at 20 Hz.

The solution: a dual-query method that computes distances to both `s` and `s'` in a **single O(n) pass**, maintaining two independent sorted top-k buffers:

```python
for idx in range(self._size):
    ds, dn = self._distance_pair(query_s, query_next, idx, distance_bias)
    if fill_first and ds <= radius_sq:
        count_s = self._insert_topk(knn_idxs, knn_dists, k, count_s, ds, idx)
    if dn <= radius_sq:
        count_next = self._insert_topk(
            knn_next_idxs, knn_next_dists, k, count_next, dn, idx
        )
```

Called with `fill_first=False` after action selection has already run `knn_search` on `s`, this second pass finds neighbors of `s'` only — giving correct, independent neighbor sets for both states in two O(n) passes total instead of one naive reuse.

This fix improves TD accuracy. But it comes with a timing cost that shows up clearly in the telemetry.

---

## The Timing Tradeoff

The tick timing data from a representative run (MAX_ENTRIES=256) shows a notable result:

```
Overall (205 ticks):
  Mean:   51.38 ms
  Median: 59.00 ms
  P95:    70.00 ms
  Max:    73.00 ms
  Ticks exceeding 30 ms: 163 (79.5%)
```

The 20 Hz tick budget is 50ms. The median tick is running at 59ms. Nearly 80% of ticks exceed 30ms. I found that the actual cause is the algorithmic work of the second scan.

The controller has two tick modes:

**Greedy ticks** (when a neighbor was credited for the action): `knn_search` over all entries, then `knn_search_dual` over all entries again for the TD bootstrap. Two full O(n) passes. These ticks consistently run 55–73ms.

**Exploration ticks** (epsilon-random action, escape heuristic, or empty memory): `knn_search` only. One O(n) pass. These ticks run roughly half as long — approximately 25–30ms.

With epsilon=0.2, roughly 20% of ticks are exploratory. The remaining 80% pay the cost of both scans. This explains the distribution: a fast cluster around 25–30ms and a slow cluster around 55–70ms, with the weighted mean pulling to ~51ms.

**This is a direct consequence of fixing the TD update.** Before the fix, the controller reused pre-action neighbors for `max_Q(s')` — one scan per tick, fast, but producing a degraded learning signal. After the fix, the controller uses correct post-action neighbors — two scans per tick, slower, but producing accurate TD targets. The timing cost is the price of correctness.

### The MAX_ENTRIES tradeoff

Since the scan is O(n), the memory cap directly sets the tick time ceiling. With MAX_ENTRIES=256, the greedy-tick scan is consistently over budget. With MAX_ENTRIES=128, the same two-scan architecture stays within the 50ms budget.

More memory entries means broader state-space coverage — the controller has more reference points for different (error, prev_error) combinations and can build a more detailed Q-value surface. With 128 entries, the memory fills faster and the eviction policy starts replacing entries earlier, which limits how finely the controller can represent the task geometry.

For this experiment, 128 entries is viable: the 2D state space is simple enough that 128 reference points provide reasonable coverage. Whether that holds as state dimensionality grows is an open question for later experiments.

The practical conclusion: **on ESP32 MicroPython at 20 Hz, MAX_ENTRIES=128 is the working point for a two-scan architecture.** Pushing to 256 entries trades timing reliability for pattern richness, and at 256 the timing budget is consistently blown. If higher memory capacity is needed at the same control rate, the path is Arduino/PlatformIO.

---

## Results

After resolving the three failure modes, the experiment produced measurable behavioral differences between the two skills. The data is worth looking at directly rather than summarizing cleanly.

### Settling time

```
Skill                  Target  Settle(ms)  Overshoot  Osc σ
reach-target-fast           0      7045ms       9.00°   2.85
reach-target-fast         180      7064ms      24.00°   8.83
reach-target-fast          90     12836ms      22.00°   4.14

reach-target-smoothly       0      4507ms      14.00°   1.90
reach-target-smoothly     180       N/A       122.00°    N/A   ← did not settle
reach-target-smoothly      90     14434ms      20.00°   9.19
```

Mean settling time: **fast = 8982ms, smooth = 9471ms** (among settled segments).

The smooth skill's 180° run never settled. With 32 telemetry rows (one every 10 ticks ≈ 320 control ticks ≈ 16 seconds), the controller was still oscillating at 122° of overshoot when the run ended. This is the smoothness penalty working against convergence on large-range targets: when reaching 180° requires moving aggressively across most of the servo range, penalizing large action deltas makes the controller reluctant to commit to moves large enough to get there. The escape heuristic helps but isn't sufficient to fully overcome the conflicting signals from the reward function.

### Hypothesis evaluation

```
Mean settling time (ms) — higher → slower:
  fast=8982   smooth=9471  → SUPPORTS (marginally)

Mean overshoot (deg) — lower → smoother:
  fast=18.33  smooth=52.00  → CONTRADICTS

Mean |action| magnitude — lower → less aggressive:
  fast=2.66   smooth=2.21   → SUPPORTS

Mean action jerk (RMS Δ) — lower → smoother:
  fast=5.79   smooth=5.64   → SUPPORTS (marginally)

Mean absolute error — higher → slower convergence:
  fast=13.13  smooth=37.33  → SUPPORTS

RESULT: 4/5 metrics support the hypothesis (partial).
```

The hypothesis, that `reach_target_smoothly` produces slower, smoother motion, receives partial support. Action magnitude and jerk both move in the expected direction. But the overshoot result is a clear contradiction, driven largely by the 122° overshoot in the failed 180° run. The mean absolute error gap (13.13° vs 37.33°) indicates `reach_target_smoothly` struggles to converge consistently, not just converging more gently.

One important note from the analysis: there is no IMU or encoder on this rig. The metrics describe the *control policy's* behavior — how the agent's decision sequence changes between skills — not what the servo physically does. Mechanical effects like backlash, inertia, and stalling are invisible. For the question being asked (does a skill config change alter agent behavior?) the software trajectory is the correct subject of measurement, but that limit is worth stating explicitly.

### What the data does show

Despite the mixed settling results, the behavioral differentiation between skills is real:

- Action magnitude is detectably lower under the smooth skill (2.21 vs 2.66)
- The smoothness penalty shapes action selection; the controller learns to prefer smaller deltas
- The failed 180° run is itself informative: the smoothness cost creates a regime where the agent won't pay the penalty to make the move required for large-range targets, and the escape heuristic alone isn't sufficient to overcome it

Skill switching produces immediate behavioral changes. The objectives are doing something real. The results are partial, but the core claim holds.

---

## What the Analysis Captures

The post-run analysis scripts measure four things per skill run:

**Memory growth rate**: slope of VMS size over ticks. Steep early → rapid exploration of new state regions. Flattening → revisiting known territory.

**Retrieval consistency** (neighbor agreement): fraction of KNN neighbors that agree on the selected action. Tracks exploration-to-exploitation transition.

**Q-value trajectory**: mean Q-value of retrieved neighbors over time. Monotonically increasing indicates healthy TD convergence.

**Cumulative reward**: total reward accumulated over the skill run. Primary outcome metric.

---

## The Open Question: Memory Reset on Skill Switch

The current implementation clears the VMS when a new skill is loaded. This is conservative and correct for this experiment. It isolates the behavioral signal to the skill's objective, not residual memory from prior learning.

But it means every skill switch starts from scratch. And given the max entry cap, the memory fills in the first few hundred ticks and the eviction policy starts replacing entries. Effective state coverage is limited by the total number of memories (256 in the test results).

The design question for later experiments: can skills tag and retain their own memory partitions across switches, bootstrapping re-evaluation under a new reward function? Or does cross-contamination between Q-value surfaces from different objectives destabilize control enough that starting fresh is always better?

Experiment 3 will test exactly this: skill-conditioned memory partitioning over a shared physical substrate.

---

## Why This Architecture

The coordinator/edge split is about latency. At 20 Hz, the tick budget is 50ms. A WiFi UDP round-trip has 1–30ms of jitter alone. KNN and Q-updates must happen on the ESP32, not the coordinator. The edge device needs to complete a full RL step without waiting on the network.

The coordinator owns everything that doesn't need to be in the hot path: skill library, telemetry logging, the CLI, and eventually the LLM interface and planner. It only touches the edge device between ticks, via JSON messages the edge device applies on its own schedule.

The skill config JSON is the only API between layers. This is a deliberate constraint: LLM-generated skills (Experiment 5) and planner-sequenced skills (Experiment 7) will use the exact same code path as the hand-authored skills from this experiment. The edge device doesn't know or care whether a skill was written by a human, generated by an LLM, or selected by a planner.

---

## Where This Sits in the Roadmap

This is experiment 1 of 11. The roadmap tests one central question:

> Can vector-memory reinforcement learning combined with LLM-generated Skills and planning form a practical control architecture for embodied agents?

Phase 1 (experiments 1–3) validates the control substrate on a single servo. The progression is deliberate: start as simple as physically possible, validate the load-bearing architectural claims before adding hardware complexity.

Experiment 1 shows that objective switching works and produces measurable behavioral differences on inexpensive hardware. The results are partial: the timing data shows the two-scan TD bootstrap pushes over budget at MAX_ENTRIES=256, and the smooth skill fails to settle on large-range targets. But the core claim holds: changing the reward function changes behavior within the same control loop, without retraining, without stopping actuation.

---

## What's Next

The immediate next step is adding an IMU to the servo rig (Experiment 2: adaptive vector density). The IMU closes the sensor gap that the skill comparison analysis explicitly flags: right now the only feedback is `commanded_angle`, which is what was sent, not what the servo did. Ground-truth position feedback changes what state representations are possible and what metrics mean.

The hypothesis for Experiment 2: the controller should allocate more memory points in frequently-visited state regions, improving local precision without increasing total memory footprint. Given the 128-entry cap discovered here, that tradeoff is sharper than expected going in.

After that, Experiment 3 tests skill-conditioned memory partitioning. And eventually, Experiments 5 and 6 ask an LLM to generate the skills: the objectives. The reward weights, learning hyperparameters, and termination conditions. Whether a language model can generate a structured objective that produces the right behavior from a KNN controller on an ESP32 is where this research is heading.

---

*[VeCTRL](https://github.com/cnatale/veCTRL) is open research in progress. If you're working on embodied AI, vector-memory control, or LLM-guided RL systems, I'm interested in comparing approaches.*
