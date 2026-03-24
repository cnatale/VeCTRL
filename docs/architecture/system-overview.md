# VeCTRL System Architecture

## Core Principle

The edge device is a fast, dumb executor of skill configs. It never knows or cares whether a skill was hand-authored, LLM-generated, or planner-sequenced. This separation is what makes the architecture composable across all experiments.

## Two-Layer Split

```
COORDINATOR (Python — Laptop → RPi 4b for Platform C)
  Owns: skill library, skill selection, global state, LLM interface, planner, telemetry logging
  Sends: skill config JSON (on switch), target angle, context packets (Exp 3+)
  Receives: telemetry stream (UDP)

                          ↕ WiFi / UDP

EDGE DEVICE (MicroPython — ESP32)
  Owns: vector memory store, KNN, Q-learning, skill evaluation, servo actuation
  Sends: telemetry stream (UDP)
  Receives: skill config JSON, target angle, context packets
```

## Platform Evolution

| Platform | Hardware | Experiments | Nominal Control Hz |
|---|---|---|---|
| A | ESP32 + 1–4 servos | Exp 1–3 | 20 Hz |
| B | ESP32 + servos + sensor(s) | Exp 4–8 | 20–60 Hz |
| C | RPi 4b + Freenove shield + motors | Exp 9–11 | 30–60 Hz |

Platform C is different: the RPi 4b connects directly to the Freenove shield. The RPi acts as both coordinator and edge device — no network hop in the control loop.

## Control Loop (Edge Device, per tick)

```
1.  Read target angle (from last coordinator message)
2.  Build state vector: [commanded_angle, target_angle, error, prev_error]
3.  Apply Mσ: filter memory candidates by required/excluded tags + partition
4.  KNN search with Wσ distance shaping over visible candidates
5.  Epsilon-greedy: select action from neighbor Q-values
6.  Clamp + apply action → commanded_angle += delta
7.  Send servo command via I2C (Freenove shield, 3× write for reliability)
8.  Compute reward using Rσ weight vector
9.  TD update: δ = r + γ·max_Q(s') − Q(s,a);  Q(s,a) += α·δ
10. Adaptive insertion check (Exp 2+): add memory entry per insertion_policy
11. Check Tσ: terminate skill if exit conditions are met
12. Send telemetry packet via UDP (non-blocking)
```

## Coordinator Layers (growth path across experiments)

```
coordinator/
  cli.py          — manual skill switching (Exp 1)
  comm.py         — UDP send/receive, device registry
  skill_store.py  — load + validate skill JSON from disk
  telemetry.py    — receive telemetry, write CSV
  llm_client.py   — LLM API calls for skill generation (Exp 5+)
  planner.py      — skill sequencer / state machine (Exp 7+)
  run.py          — wires everything together
```

Each layer is additive. Exp 1 uses only `comm`, `skill_store`, `telemetry`, and `cli`.

## Key Architectural Decisions

### Memory lives on the edge device
KNN lookup and Q-updates happen on the ESP32. Moving them to the coordinator introduces WiFi round-trip latency (1–30ms jitter) into the control loop, which exceeds the tick budget at 20+ Hz.

### Standard MicroPython for Exp 1–6
MicroPython allows edit → deploy → run in ~5 seconds, which is critical for research iteration speed. No custom firmware or external libraries are needed. State vectors are stored as `array.array('f')` (standard library) and the KNN distance loop uses `@micropython.native` for ~2x speedup over bytecode. At 20 Hz (50ms tick budget), brute-force KNN over 200 entries takes ~2–4ms — well within budget. See `docs/architecture/edge-device-setup.md`.

### Switch to Arduino/PlatformIO if GC jitter appears
If `tick_duration_ms` in telemetry shows unpredictable spikes, port the edge code to Arduino (PlatformIO). The skill config schema, telemetry format, and all coordinator code remain unchanged. The port is 2–3 days of work. See `docs/architecture/edge-device-setup.md`.

### Skill config is the only API between layers
The edge device accepts exactly one message type from the coordinator: a skill config JSON conforming to `docs/architecture/skill-config-schema.md`. LLM-generated skills (Exp 5+) and planner-sequenced skills (Exp 7+) use the exact same code path as hand-authored skills.

### device_id in every message
All telemetry packets and coordinator commands carry a `device_id`. A no-op for single-device experiments; required for routing in Exp 4+.
