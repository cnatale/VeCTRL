# Edge Device Setup

## Option A: Standard MicroPython (Exp 1–6)

No custom firmware or external libraries required. The official ESP32 build from micropython.org includes everything needed: `array`, `math`, `json`, `socket`, and the `micropython` module (which provides `@micropython.native`).

### 1. Flash standard MicroPython firmware

Download the latest stable ESP32 firmware from [micropython.org/download/ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/).

```bash
source .venv/bin/activate
pip install esptool

# Erase existing firmware
esptool.py --port /dev/tty.usbserial-XXXX erase_flash

# Write new firmware
esptool.py --port /dev/tty.usbserial-XXXX --baud 460800 \
  write_flash -z 0x1000 ESP32_GENERIC-<version>.bin
```

### 2. Verify the build

```bash
mpremote connect /dev/tty.usbserial-XXXX repl
```

```python
import array
import micropython
a = array.array('f', [1.0, 2.0, 3.0])
print(a[0])   # 1.0 — float32 typed array, standard library
```

### 3. Create config.py (credentials + coordinator address)

Copy the template and fill in your values:

```bash
cp experiments/exp-001-real-time-reward-shaping/code/edge-device/vectrl-esp32/config.example.py \
   experiments/exp-001-real-time-reward-shaping/code/edge-device/vectrl-esp32/config.py
```

Edit `config.py` with your WiFi credentials and coordinator IP. This file is gitignored — never commit it.

### 4. Deploy to device

From the experiment's edge device directory:

```bash
source .venv/bin/activate
PORT=/dev/tty.usbserial-XXXX

mpremote connect $PORT fs cp config.py :config.py
mpremote connect $PORT fs cp vms.py :vms.py
mpremote connect $PORT fs cp skill_runner.py :skill_runner.py
mpremote connect $PORT fs cp controller.py :controller.py
mpremote connect $PORT fs cp boot.py :boot.py
mpremote connect $PORT fs cp main.py :main.py
mpremote connect $PORT reset
```

### 5. Watch output

```bash
mpremote connect $PORT repl
```

### Performance characteristics

At 20 Hz (50ms tick budget), brute-force KNN with `array.array('f')` storage and `@micropython.native` on the distance loop:

| VMS entries | State dims | Approx KNN time | Budget used (20 Hz) |
|---|---|---|---|
| 100 | 4 | ~1–2ms | 2–4% |
| 200 | 4 | ~2–4ms | 4–8% |
| 300 | 4 | ~3–6ms | 6–12% |

`MAX_ENTRIES = 200` is the default cap. This is comfortable through all of Exp 1–3. Exp 2 (adaptive density) may grow memory faster — watch `memory_size` in telemetry and raise the cap if needed.

### Watching for GC pressure

Monitor `tick_duration_ms` in telemetry. A healthy 20 Hz loop should be consistently under 20ms. Spikes to 40–80ms indicate GC pauses. Mitigate by avoiding object creation in the control loop hot path (the current `controller.py` is already written to avoid this). If spikes persist, switch to Option B.

---

## Option B: Arduino / PlatformIO (if GC jitter is observed)

Switch to this when `tick_duration_ms` spikes are frequent and not resolved by pre-allocation. The skill config schema, telemetry format, and all coordinator code remain unchanged. The port is 2–3 days of work.

### 1. Install PlatformIO

```bash
pip install platformio
```

Or install the PlatformIO VS Code extension.

### 2. Project structure

```
code/edge-device/vectrl-esp32-arduino/
  platformio.ini
  src/
    main.cpp
    vms.h / vms.cpp
    skill_runner.h / skill_runner.cpp
    controller.h / controller.cpp
    config.h                        # gitignored — copy from config.example.h
  lib/
    ArduinoJson/
```

### 3. `platformio.ini`

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps =
  bblanchon/ArduinoJson@^7.0.0
monitor_speed = 115200
```

### 4. Compile and flash

```bash
cd code/edge-device/vectrl-esp32-arduino
pio run --target upload --upload-port /dev/tty.usbserial-XXXX
pio device monitor --port /dev/tty.usbserial-XXXX
```

Incremental builds take 15–30 seconds. Cold builds take 60–120 seconds.

### Key differences from MicroPython

- No REPL — use `Serial.println()` for debugging
- Skill configs parsed with `ArduinoJson` (same JSON schema, no changes needed)
- Use `hw_timer_t` for a fixed-frequency ISR-driven control tick
- KNN with flat `float` arrays: deterministic timing, trivially achieves 200+ Hz

### KNN in C++ (reference)

```cpp
// Flat array layout — cache-friendly, no GC
float memory_states[MAX_ENTRIES][STATE_DIM];
float memory_q[MAX_ENTRIES];
int   memory_action[MAX_ENTRIES];
int   memory_size = 0;

int knn_best_action(float* query, float neighbor_radius_sq) {
    float best_q = -1e9f;
    int best_action = 4;  // default: no-op
    for (int i = 0; i < memory_size; i++) {
        float dist = 0;
        for (int d = 0; d < STATE_DIM; d++) {
            float diff = query[d] - memory_states[i][d];
            dist += diff * diff;
        }
        if (dist <= neighbor_radius_sq && memory_q[i] > best_q) {
            best_q = memory_q[i];
            best_action = memory_action[i];
        }
    }
    return best_action;
}
```
