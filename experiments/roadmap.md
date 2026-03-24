# Experimental Roadmap

This roadmap is designed to validate the most novel aspects of VeCTRL as quickly as possible using inexpensive hardware.

The goal is **not** to build a polished robot first.

The goal is to test the core architectural hypotheses behind VeCTRL:

1. **Vector-space Q-learning enables real-time behavior shaping**
2. **Adaptive vector-memory density improves control in frequently visited regions**
3. **LLM-generated Skills can reshape state/action space effectively**
4. **LLMs can generate useful reward functions and hyperparameters for control**
5. **Planning over Skills can organize behavior more effectively than flat control**

---

## Guiding principles

### 1. Fastest hardware first

Experiments should begin on the simplest physical systems possible:

- single-servo rigs
- 4 DoF robotic arms assemblies
- simple wheeled platforms

This reduces mechanical complexity and maximizes iteration speed.

### 2. Every experiment must produce a result

Each experiment should produce:

- a hypothesis
- a minimal implementation
- quantitative metrics
- analysis
- follow-up questions

A negative result is still useful if it clarifies architectural limits.

### 3. Skills before full autonomy

The project focus is not generic robotics.

The focus is on whether **Skills, reward shaping, and vector memory** can form a practical control substrate.

### 4. LLMs act as architecture-level controllers

Language models are not the fast loop.

They are used to:

- generate Skills
- generate reward/cost functions
- generate hyperparameters
- sequence Skills into plans

---

## Available hardware

The following hardware is sufficient for a strong first research program:

- Laptop or Raspberry Pi 4B (4GB)
- ESP32 development board
- MG995 25kg metal gear and 9g plastic gear servos
- MPU-6050 / GY-521 IMU modules
- Raspberry Pi camera
- I2C lidar range finder
- cheap sonar sensor
- microphone amplifier
- motor drivers
- 5V motors
- Freenove smart car shield

These support three fast-build experimental platforms:

### Platform A: Single-servo bench rig
Use:
- ESP32
- 1 servo
- IMU mounted to moving element after initial proof-of-concept experiment

Best for:
- reward shaping
- adaptive memory density
- hyperparameter experiments

### Platform B: Four-servo/DoF mini arm rig
Use:
- 4 servos
- optional camera, sonar, or lidar
- lightweight 3D printed frame/bracket

Best for:
- multi-dimensional state spaces
- skill switching
- visual target tracking
- plan → skill → control experiments

### Platform C: Minimal wheeled rover with Platform B arm attachment
Use:
- Raspberry Pi 4
- Freenove smart car shield
- motors
- lidar/sonar/IMU

Best for:
- navigation skills
- obstacle avoidance
- skill sequencing
- planner-driven behavior

---

## Research phases

The roadmap is broken into four phases:

| Phase | Goal |
|------|------|
| Phase 1 | Validate vector-memory control substrate |
| Phase 2 | Validate adaptive memory + reward shaping |
| Phase 3 | Validate LLM-generated Skills and hyperparameters |
| Phase 4 | Validate planning over Skills on a mobile platform |

---

## Phase 1 — Validate the control substrate

### Experiment 1 — Real-time reward shaping on a single-servo rig

**Platform:** A  
**Build time:** same day

#### Setup
Create a simple servo rig with one controllable degree of freedom. No IMU for this experiment.

Possible task ideas:
- move toward a target angle
- hold a target angle despite perturbation
- minimize oscillation while reaching a target

#### Hypothesis
A vectoro-memory controller can be behaviorally reshaped in real time by modifying reward/cost functions without retraining a policy network.

#### Why it matters
This directly tests one of the main reasons VeCTRL exists:
> dynamic update of scoring and behavior in near real time

#### Metrics
- settling time
- overshoot
- oscillation amplitude
- control smoothness
- number of memory entries used

#### Variants
Compare reward definitions like:

- `reach_target_fast`
- `reach_target_smoothly`
- `reach_target_with_low_energy`

#### Success criteria
Behavior changes immediately and measurably when the reward function changes.

#### Writeup angle
“Can control behavior be reshaped instantly without retraining?”

---

### Experiment 2 — Adaptive vector density in frequently visited regions

**Platform:** A  
**Build time:** 1 day after Experiment 1

#### Setup
Reuse the same servo rig.

Allow the controller to add more memory points in regions of the state space visited frequently or associated with high TD error.

#### Hypothesis
Increasing vector density in frequently visited regions improves local control precision and stability.

#### Why it matters
This tests your second major intuition:
> the controller should refine representation where experience actually concentrates

#### Metrics
- error near common target zones
- variance in action selection
- memory growth rate
- retrieval consistency
- performance before vs after densification

#### Variants
Compare:
- uniform memory insertion
- TD-error-triggered insertion
- visit-frequency-triggered insertion

#### Success criteria
Dense regions show better precision or smoother control than uniformly sampled memory.

#### Writeup angle
“Should an embodied controller allocate memory the way experience allocates attention?”

---

### Experiment 3 — Skill-conditioned reward shaping on the same physical task

**Platform:** A  
**Build time:** same week as Experiment 2

#### Setup
Keep the same physical rig but define two Skills over the same underlying substrate.

Example Skills:
- `fast_reach`
- `stable_hold`

Each Skill changes:
- reward definition
- score shaping
- hyperparameters
- memory visibility

#### Hypothesis
A Skill can be understood as a temporary redefinition of good behavior over a shared control substrate.

#### Why it matters
This is one of the clearest physical demonstrations of your Skill abstraction.

#### Metrics
- time to target
- post-target stability
- action variance
- memory regions selected under each Skill

#### Success criteria
The same hardware and controller behaves differently and predictably under different Skills.

#### Writeup angle
“A Skill is not a policy: it is a runtime objective lens over shared memory.”

---

## Phase 2 — Move from scalar control to structured state

### Experiment 4 — Two-servo target tracking with skill-conditioned control

**Platform:** B  
**Build time:** 1–2 days

#### Setup
Build a simple four-servo lightweight arm.
Use one or more of:
- camera
- lidar
- sonar
- IMUs attached to different parts of the arm

Possible task:
- point toward a target object
- keep a target centered
- approach a desired sensor reading

#### Hypothesis
Skill-conditioned memory filtering and reward shaping remain effective in a higher-dimensional state/action space.

#### Why it matters
The single-servo case may be too simple. This tests whether the architecture remains useful when coordination increases.

#### Example Skills
- `center_target_fast`
- `center_target_smoothly`
- `avoid_close_obstacle`
- `scan_for_target`

#### Metrics
- target acquisition time
- steady-state tracking error
- jitter
- memory growth
- retrieval concentration by Skill

#### Success criteria
Skill switching remains interpretable and behaviorally meaningful in a multi-dimensional task.

#### Writeup angle
“Do Skills still help when control gets less toy-like?”

---

### Experiment 5 — LLM-generated reward and hyperparameter proposals

**Platform:** A or B  
**Build time:** same week as Experiment 4

#### Setup
Use an LLM offline or in-the-loop to generate:
- reward functions
- penalties
- learning rates
- exploration settings
- neighbor radius

Constrain output to a structured schema.

#### Hypothesis
LLMs can produce usable reward/cost and hyperparameter proposals that measurably alter controller behavior.

#### Why it matters
This is one of the most novel parts of VeCTRL.

#### Important note
The goal is not to prove the LLM is always correct.
The goal is to test whether LLM-generated control configurations are:
- syntactically valid
- behaviorally meaningful
- sometimes useful
- debuggable when they fail

#### Metrics
- percentage of valid generated configs
- performance relative to hand-authored baseline
- frequency of pathological reward definitions
- human time saved

#### Success criteria
At least some generated configs are usable and produce sensible, inspectable behavior changes.

#### Writeup angle
“Can language models author control objectives instead of just code?”

---

### Experiment 6 — LLM-generated Skill objects

**Platform:** B  
**Build time:** 2–3 days

#### Setup
Define a structured Skill schema, for example:

- memory filter
- score bias
- reward function
- update policy
- termination rules

Ask the LLM to generate new Skills for constrained tasks such as:
- cautious centering
- aggressive target approach
- obstacle-aware tracking

#### Hypothesis
LLM-generated Skills can function as runtime control contexts that reshape action selection in a useful and interpretable way.

#### Metrics
- schema validity rate
- execution safety rate
- distinctiveness of resulting behavior
- performance relative to hand-authored Skills

#### Success criteria
Generated Skills cause distinct, explainable behavior changes without changing the base control loop architecture.

#### Writeup angle
“What if language models generated objectives instead of end-to-end policies?”

---

## Phase 3 — Planning over Skills

### Experiment 7 — Skill sequencing on a benchtop agent

**Platform:** B  
**Build time:** 2–3 days

#### Setup
Use a pan/tilt rig or simple arm-like rig with a staged task.

Example:
1. scan
2. detect target
3. center target
4. hold target

Each phase corresponds to a Skill.

#### Hypothesis
Planning over Skills is more manageable and interpretable than trying to produce one monolithic behavior policy.

#### Why it matters
This begins to validate the hierarchical architecture:
`plan -> skill -> vector control`

#### Metrics
- task completion rate
- number of skill transitions
- transition quality
- recovery from failure
- time spent thrashing between Skills

#### Success criteria
The system completes multi-stage tasks by sequencing Skills without needing one flat policy.

#### Writeup angle
“Planning as organization of objectives, not emission of motor actions.”

---

### Experiment 8 — Skill-specific hyperparameter adaptation

**Platform:** B  
**Build time:** same week as Experiment 7

#### Setup
Associate different update policies with different Skills.

Examples:
- exploration-heavy scan skill
- conservative execute skill
- stability-focused hold skill

#### Hypothesis
Hyperparameters tied to Skills outperform one global RL setting across a multi-stage task.

#### Metrics
- stage-specific task success
- convergence speed
- instability during transitions
- degradation from global-only settings

#### Success criteria
Different task phases benefit from different update policies.

#### Writeup angle
“One controller, multiple learning regimes.”

---

## Phase 4 — Minimal mobile embodiment

### Experiment 9 — Rover obstacle avoidance with hand-authored Skills

**Platform:** C  
**Build time:** 1–2 weekends

#### Setup
Build the simplest possible wheeled rover using:
- Raspberry Pi 4
- Freenove smart car shield
- motors
- sonar and/or lidar
- optional IMU

Start with a constrained environment:
- hallway
- cardboard obstacles
- tabletop boundaries with great care
- taped lanes on the floor

#### Skills
- `move_forward`
- `avoid_obstacle`
- `stabilize_heading`
- `stop`

#### Hypothesis
A shared vector-memory substrate with skill-conditioned behavior can support practical navigation behavior on low-cost hardware.

#### Metrics
- obstacle collisions
- path efficiency
- stopping reliability
- recovery events
- memory growth by skill

#### Success criteria
The rover can complete simple navigation tasks through skill-conditioned control rather than a monolithic policy.

#### Writeup angle
“What transfers from bench-top control to embodied navigation?”

---

### Experiment 10 — LLM-generated navigation Skills

**Platform:** C  
**Build time:** after Experiment 9 is stable

#### Setup
Allow the LLM to generate or modify Skills for constrained rover tasks.

Examples:
- cautious hallway traversal
- aggressive progress
- obstacle-biased navigation
- low-energy movement

#### Hypothesis
LLM-generated Skills can serve as usable control abstractions for embodied navigation when constrained by schema and safety rules.

#### Metrics
- valid skill generation rate
- safety violations
- performance delta vs hand-authored skills
- human intervention frequency

#### Success criteria
At least a subset of LLM-authored navigation Skills are useful and safe enough for constrained real-world testing.

#### Writeup angle
“Can language models design reusable navigation objectives?”

---

### Experiment 11 — Planner-generated skill plans

**Platform:** C  
**Build time:** after Experiment 10

#### Setup
Ask the planner to produce a task plan using existing Skills.

Example task:
- move until obstacle detected
- avoid obstacle
- reacquire corridor
- continue forward
- stop at target distance

#### Hypothesis
Plan generation over Skills is feasible and interpretable even when low-level control remains non-neural and retrieval-based.

#### Metrics
- task completion
- plan correctness
- number of unnecessary skill transitions
- time to recover from bad plans

#### Success criteria
The planner can organize existing Skills into useful sequences more often than chance, and failures are interpretable.

#### Writeup angle
“Can an LLM plan over objective-shaping primitives instead of tools?”

---

## First six weeks

| Week | Experiment | Platform |
|------|------------|----------|
| 1 | Real-time reward shaping | A |
| 2 | Adaptive vector density | A |
| 3 | Skill-conditioned reward shaping | A |
| 4 | Two-servo target tracking | B |
| 5 | LLM-generated reward / hyperparameters | B |
| 6 | LLM-generated Skills | B |

This sequence is ideal because it:
- starts simple
- validates your most novel ideas early
- avoids getting stuck in mechanical build complexity
- produces multiple strong technical writeups quickly

---

## Measurement framework

Every experiment should log:

### Control metrics
- settling time
- overshoot
- oscillation / jitter
- reward accumulation
- action entropy

### Memory metrics
- number of memory points
- retrieval concentration
- local density
- memory growth by state region
- neighbor agreement

### Skill metrics
- active skill
- transition count
- transition success
- thrashing frequency
- reward by skill

### LLM metrics
- schema validity
- execution success
- safety rejection rate
- human corrections required
- performance relative to hand-authored baseline

---

## Safety and scope constraints

To preserve iteration speed and reduce risk:

- prefer tabletop / benchtop experiments first
- constrain all action spaces tightly
- require LLM outputs to conform to schemas
- cap motor speeds
- define hard stop conditions
- treat generated Skills as proposals, not trusted truth

---

## What would count as a strong early result?

Any of the following would be meaningful:

1. **Reward shaping changes behavior immediately without retraining**
2. **Adaptive memory density improves local precision**
3. **Different Skills produce distinct policies over a shared substrate**
4. **LLM-generated reward or hyperparameter proposals sometimes outperform a baseline**
5. **Planner-generated skill sequences solve multi-stage tasks more cleanly than flat control**

Any one of these is worth writing about.

Multiple together would strongly support the VeCTRL thesis.

---

## Why this roadmap exists

This roadmap is designed to answer a specific question:

> Can vector-memory reinforcement learning combined with LLM-generated Skills and planning form a practical control architecture for embodied agents?

The aim is to generate evidence, failure modes, and architectural insight that can inform future research in:

- embodied AI
- hierarchical reinforcement learning
- memory-based control
- LLM-guided adaptive systems