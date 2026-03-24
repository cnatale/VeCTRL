# Communication Protocol

## Transport

UDP over WiFi (IEEE 802.11). All messages are JSON-encoded byte strings.

Two unidirectional channels:

| Direction | Port | Rate | Purpose |
|---|---|---|---|
| Edge → Coordinator | 5005 | 20 Hz (one per tick) | Telemetry stream |
| Coordinator → Edge | 5006 | Event-driven | Skill configs, targets, context |

UDP is fire-and-forget — no acknowledgement. Dropped telemetry packets are acceptable (the coordinator logs gaps). Dropped skill config packets are also acceptable because the coordinator retries on its next send cycle.

---

## Coordinator → Edge Message Types

All messages include `type` and `device_id` for routing.

### `skill_config`

Sent once when switching skills. The edge applies the new config on the next tick.

```json
{
  "type": "skill_config",
  "device_id": "esp32-arm",
  "payload": {
    "skill_id": "reach_target_fast",
    "description": "...",
    "memory_filter": { ... },
    "distance_bias": {},
    "reward": { ... },
    "learning": { ... },
    "termination": { ... }
  }
}
```

`payload` must fully conform to `docs/architecture/skill-config-schema.md`. Validated by coordinator before sending; invalid configs are rejected and logged, never forwarded.

### `target`

Sent when the target angle changes. The edge updates `_target_angle` on next tick.

```json
{
  "type": "target",
  "device_id": "esp32-arm",
  "angle": 120.0
}
```

### `context` (Exp 3+)

Sent each coordinator tick to augment edge state with global context. Enables the global-local KNN architecture described in `docs/knn-context-projection.md`.

```json
{
  "type": "context",
  "device_id": "esp32-arm",
  "skill_id": 1,
  "phase_id": 2,
  "target_delta": -6.0,
  "motion_mode": 0
}
```

---

## Edge → Coordinator Message Types

### `telemetry`

Sent once per control tick. See `docs/architecture/telemetry-schema.md` for full field reference.

```json
{
  "type": "telemetry",
  "device_id": "esp32-arm",
  ...
}
```

---

## Timing

| Message | Rate | Notes |
|---|---|---|
| Telemetry | 20 Hz (one per tick) | Non-blocking send; dropped if UDP buffer full |
| Skill config | Event-driven | On CLI switch or planner transition |
| Target update | Event-driven | On coordinator state change; also sent at 1 Hz as keepalive |
| Context packet | Coordinator tick rate (Exp 3+) | 1–5 Hz typically |

---

## WiFi Setup (Edge Device)

Credentials and coordinator address are stored in `config.py` on the ESP32 filesystem. This file is **gitignored** — copy from `config.example.py` and edit locally.

```python
# config.py (gitignored — do not commit)
WIFI_SSID = "your-network"
WIFI_PASSWORD = "your-password"
COORDINATOR_IP = "192.168.1.100"
TELEMETRY_PORT = 5005
COMMAND_PORT = 5006
DEVICE_ID = "esp32-arm"
```

The edge device connects at startup in `boot.py` and retries on disconnect. The control loop does not block on WiFi — telemetry sends fail silently if not connected.

---

## Multi-Device Routing (Exp 4+)

When multiple ESP32 devices are active, the coordinator maintains a device registry keyed by `device_id`. Each device:

- Sends telemetry to the same coordinator port (5005)
- Receives skill configs addressed to its own `device_id`
- Has an independent skill runner and memory store

The coordinator differentiates devices by the `device_id` field in every message. Adding a new device requires only registering its IP in the coordinator's device registry — no protocol changes.
