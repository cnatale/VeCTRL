# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VeCTRL (Vector Control Loop) is an experimental research project for embodied AI systems. It combines vector-based reinforcement learning with LLM-guided skill generation and planning. The core idea: control policies emerge from `state embeddings → KNN retrieval → action selection → reinforcement updates` rather than from trained neural networks.

## Hardware

- **Coordinator**: Laptop or Raspberry Pi 4b (4GB) — runs global state fusion, skill selection, context generation
- **Edge device**: HiLetgo ESP32 (ESP-32S) — runs MicroPython, handles local KNN + Q-learning + servo actuation
- **Shield**: Freenove Smart Car Shield for RPi — exposes a servo controller at I2C address `0x18`
- **Servos**: MG995 and Smraza S51 micro servos (up to 4 channels: `CMD_SERVO1`–`CMD_SERVO4`)
- **Sensors (available)**: Raspberry Pi camera, LiDAR (I2C), MPU-6050 IMU, sonar, microphone

## Development Commands

Activate the virtual environment first:
```bash
source .venv/bin/activate
```

### Deploying to the ESP32 (MicroPython via mpremote)

List available serial ports:
```bash
python -m serial.tools.list_ports
```

Copy a file to the ESP32:
```bash
mpremote connect /dev/tty.usbserial-XXXX fs cp main.py :main.py
```

Run a script directly (without writing to flash):
```bash
mpremote connect /dev/tty.usbserial-XXXX run main.py
```

Open an interactive REPL:
```bash
mpremote connect /dev/tty.usbserial-XXXX repl
```

Reset the device (soft reset):
```bash
mpremote connect /dev/tty.usbserial-XXXX reset
```

### Running the coordinator (Exp 1)

```bash
source .venv/bin/activate
cd experiments/exp-001-real-time-reward-shaping/code/coordinator
python run.py --device esp32-arm --ip <ESP32_IP>
```

## Repository Structure

```
docs/
  architecture/                         # System design documents
    system-overview.md                  # Two-layer architecture, control loop, design decisions
    skill-config-schema.md              # Full JSON schema for skill configs
    telemetry-schema.md                 # Telemetry packet format and CSV columns
    communication-protocol.md          # UDP channels, message types, WiFi setup
    edge-device-setup.md                # MicroPython+ulab flash guide; Arduino fallback
  VeCTRL-SKILLS.md                      # Formal Skill definition (σ tuple)
  knn-context-projection.md            # Global-local KNN architecture (Exp 3+)
  comparison-with-other-rl-approaches.md
  on-hand-materials.md

experiments/
  exp-001-real-time-reward-shaping/
    description.md                      # Hypothesis, metrics, success criteria
    README.md                           # Servo pin mapping
    skills/                             # Skill config JSON files for this experiment
      reach_target_fast.json
      reach_target_smoothly.json
      reach_target_with_low_energy.json
    analysis/                           # Post-run analysis scripts (README describes planned scripts)
    data/                               # Telemetry CSVs written by coordinator (gitignored)
    code/
      edge-device/
        vectrl-esp32/
          boot.py                       # WiFi connect at startup
          main.py                       # Entry point — instantiates and runs Controller
          vms.py                        # VectorMemoryStore: KNN, Q-update, insertion, persistence
          skill_runner.py               # SkillRunner: evaluates Rσ, Mσ, Wσ, Uσ, Tσ
          controller.py                 # Control loop: 20 Hz tick, wires VMS + SkillRunner + servo
          config.example.py             # WiFi credentials template (copy to config.py, gitignored)
          servo-test.py                 # Standalone servo test
          led-test.py                   # LED test
      coordinator/
        run.py                          # Entry point — wires all coordinator modules
        comm.py                         # UDP send/receive, device registry
        skill_store.py                  # Load + validate skill JSON files
        telemetry.py                    # Receive telemetry, write CSV
        cli.py                          # Terminal CLI for skill switching and target control

experiments/roadmap.md                  # 11-experiment research roadmap across 4 phases
```

## Architecture

See `docs/architecture/system-overview.md` for the full design. Key points:

**Two-layer split:**
- **Coordinator** (Python, laptop) — skill selection, telemetry logging, LLM interface (Exp 5+), planner (Exp 7+)
- **Edge device** (MicroPython, ESP32) — vector memory store, KNN, Q-learning, servo actuation

**The edge device is a dumb executor of skill configs.** KNN and reward computation stay on the ESP32 — moving them to the coordinator adds WiFi latency to the control loop.

### Skill Config

A Skill `σ` is a 6-tuple that conditions the edge controller without encoding a policy:

```
σ = ⟨ Mσ, Wσ, Rσ, Uσ, Tσ, Dσ ⟩
  Mσ: memory filter (tags, partition)
  Wσ: distance shaping (per-dimension bias weights)
  Rσ: reward function (error, action, smoothness weights)
  Uσ: update policy (alpha, gamma, epsilon, insertion_policy)
  Tσ: termination (min/max duration, exit conditions)
  Dσ: description (for LLM planner readability)
```

Full schema: `docs/architecture/skill-config-schema.md`
Exp 1 skills: `experiments/exp-001-real-time-reward-shaping/skills/`

### Global-Local KNN (Exp 3+)

The coordinator sends compact **context packets** (skill_id, phase_id, target deltas) to each edge device. Edge devices concatenate local sensor readings with the context to form their KNN query vector. Documented in `docs/knn-context-projection.md`.

## ESP32 Servo Interface

The Freenove shield firmware requires the I2C write to be sent **3 times** for reliability. Pulse width range: 500–2500 µs over I2C bus 0 (SCL=GPIO22, SDA=GPIO21) at 100 kHz.

```python
I2C_ADDR = 0x18
# CMD_SERVO1=0, CMD_SERVO2=1, CMD_SERVO3=2, CMD_SERVO4=3
# Pulse: SERVO_MIN_US=500, SERVO_MAX_US=2500
```

Servo pin mapping (Exp 1 arm rig):
- Servo1: Base X Rotation
- Servo2: Base Y Rotation
- Servo3: Mid-Arm Y Rotation
- Servo4: Grabber

The shield requires **both CTRL and LOAD power switches** to be ON, and needs external DC power for the servo load path.

## Edge Device Language

**Standard MicroPython** for Exp 1–6 — no custom firmware or external libraries required. Flash the official ESP32 build from micropython.org. State vectors use `array.array('f')` from the standard library; the KNN distance loop uses `@micropython.native` for ~2x speedup. Keep `VectorMemoryStore.MAX_ENTRIES = 128` as the minimum for this experiment. Telemetry uses `%`-formatted JSON strings (not dict + `json.dumps`) to stay within the ESP32's heap budget at this capacity.

**Switch to Arduino/PlatformIO** if `tick_duration_ms` in telemetry shows GC pause spikes (values > 30ms that don't resolve). The skill config schema and all coordinator code remain unchanged. See `docs/architecture/edge-device-setup.md`.

## WiFi / Config

Copy `config.example.py` to `config.py` (gitignored) and fill in WiFi credentials and coordinator IP before deploying. Never commit `config.py`.
