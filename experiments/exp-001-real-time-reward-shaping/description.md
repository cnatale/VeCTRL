### Experiment 001 — Real-time reward shaping on a single-servo rig

#### Hypothesis
A vector-memory controller can be behaviorally reshaped in real time by modifying reward/cost functions without retraining a policy network.

#### Setup
Create a simple servo rig with one controllable degree of freedom.

Possible task ideas:
- move toward a target angle
- hold a target angle despite perturbation
- minimize oscillation while reaching a target

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
