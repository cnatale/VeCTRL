# VeCTRL

VeCTRL (Vector Control Loop) is an experimental architecture for **embodied AI systems that combine vector-based reinforcement learning with LLM-guided skill generation and planning.**

The system explores a hybrid approach to control where:

• **Vector memory retrieval** performs real-time action selection  
• **Q-learning updates** adapt behavior through experience  
• **LLMs generate skills, reward functions, and plans** that shape the learning system  

The core idea is that **control policies do not need to be learned purely through neural networks**.

Instead, behavior can emerge through:

state embeddings → vector memory retrieval → action selection → reinforcement updates

This enables a system that can:

• adapt behavior instantly through reward shaping  
• dynamically refine the representation of frequently visited states  
• integrate symbolic planning with continuous control  
• learn from experience without retraining large neural policies  

---

# Core Hypothesis

The central hypothesis of VeCTRL is:

> Vector-based reinforcement learning combined with LLM-generated skill structures can produce adaptive embodied agents that learn efficiently while remaining interpretable and controllable.

The architecture separates **three layers of intelligence**:

| Layer | Role |
|------|------|
| Control Loop | Real-time action selection using vector Q-learning |
| Skills | Structured behavior definitions that shape state and action spaces |
| Planning | High-level reasoning using transformer models |

---

# Architecture Overview
Planner (LLM)
↓
Plan generation

Skill Layer
↓
Skills define:
	•	state filters
	•	action subsets
	•	reward functions
	•	hyperparameters

Vector RL Controller
↓
state embedding → KNN retrieval → action selection

Fast Control Loop
↓
real-world interaction

---

# Why Vector Memory Instead of Neural Policies?

Most reinforcement learning systems rely on neural networks that require training to update behavior.

Vector-based policies allow:

### Real-Time Behavior Shaping

Reward functions and action scoring can be modified dynamically without retraining.

### Experience-Dense State Representation

Regions of the state space that the system visits frequently naturally accumulate more memory points, producing higher control precision where it matters most.

### Interpretable Control Policies

Memory entries directly represent experienced states and actions rather than opaque neural weights.

---

# Key Research Questions

The project investigates several open questions:

1. **Can LLM-generated skills effectively shape reinforcement learning behavior?**

2. **Can LLMs dynamically tune reinforcement learning hyperparameters during operation?**

3. **Does adaptive vector memory density improve control stability in frequently visited states?**

4. **Can vector memory controllers serve as a substrate for reusable agent skills?**

---

# Current Status

VeCTRL is an experimental research project exploring architectures for **embodied AI systems that integrate reinforcement learning and language models.**

The current focus is on:

• vector-space Q-learning controllers  
• LLM-generated agent skills  
• real-time reward shaping  
• hierarchical planning over skills  

---

# Long-Term Vision

The long-term goal of VeCTRL is to explore architectures for agents that combine:

* fast, experience-driven control loops
* structured skill libraries
* language-model reasoning

This combination could enable agents that can **learn continuously while remaining interpretable and controllable.**

---

# Code Quality Standards

VeCTRL spans both **Python 3** code that runs on the coordinator and **MicroPython** code that runs on the ESP32 edge device. The quality bar should reflect both environments:

## Supported Runtimes

- Coordinator and analysis code should target a modern Python 3 runtime.
- Edge-device code should remain compatible with the MicroPython build used on the ESP32.
- Shared logic should be written against the overlap of Python 3 and MicroPython features whenever practical.

## Linting And Formatting

- All Python 3 code should pass `ruff check`.
- All Python 3 code should use a consistent formatter, with `ruff format` as the default choice.
- MicroPython code should also be linted with Ruff where possible, but contributors must avoid introducing imports or language features that are unavailable on the device.
- New modules should keep functions small, names explicit, and side effects localized so that coordinator and edge logic remain easy to reason about.
- Hardware constants, protocol fields, and servo limits should be defined once and referenced symbolically rather than duplicated inline.

## Test Expectations

- Python 3 coordinator, analysis, and shared-library code should have automated tests using `pytest`.
- New features should include tests for the main success path plus the most important edge case or failure mode.
- Bug fixes should include a regression test whenever the behavior can be reproduced in an automated test.
- MicroPython modules should separate pure logic from hardware I/O so the logic can be tested on a host machine under `pytest`.
- Hardware-facing MicroPython code should have a documented smoke-test procedure for real-device verification when full automation is not practical.

## Coverage Thresholds

- Python 3 coordinator and shared logic should maintain at least **90% line coverage** and **85% branch coverage**.
- Testable MicroPython logic that runs under host-side tests should maintain at least **80% line coverage**.
- Hardware adapter layers, direct servo control, and board-specific integration code are not expected to hit the same coverage threshold, but they should be exercised by documented smoke tests before merge.
- Changes should not reduce coverage in the area they modify without a clear reason documented in the pull request.

## Minimum Merge Bar

- Linting passes for all changed Python files.
- Relevant automated tests pass locally.
- New behavior is covered by tests, or the lack of automation is justified for hardware-specific code.
- README or architecture docs are updated when a change affects setup, protocols, telemetry, or skill configuration.

## Practical Guidance For This Repo

- Keep coordinator code, experiment analysis, and reusable utilities test-first where possible.
- Keep ESP32 modules optimized for clarity and determinism: prefer simple data structures, explicit bounds, and predictable control-loop timing over clever abstractions.
- Mock or fake network, filesystem, and device interfaces in host-side tests rather than coupling tests to live hardware.
- Treat performance-sensitive edge code as production-critical even in experiments: changes that affect tick timing, memory growth, or servo safety should be validated on device.