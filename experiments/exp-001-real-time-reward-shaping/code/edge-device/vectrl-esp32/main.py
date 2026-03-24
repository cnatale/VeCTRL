"""
VeCTRL edge device entry point — Exp 001 (Platform A, single servo).

Connects to WiFi, initializes all modules, and runs the control loop.
"""

import network
import time
from machine import Pin, I2C

import config
from comm import Comm
from vms import VectorMemoryStore
from skill_runner import SkillRunner
from controller import ACTION_SET, Controller


# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------


def connect_wifi(ssid, password, timeout_s=20):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi:", ssid)
        wlan.connect(ssid, password)
        deadline = time.time() + timeout_s
        while not wlan.isconnected():
            if time.time() > deadline:
                raise RuntimeError("WiFi connection timed out")
            time.sleep(0.5)
    ip = wlan.ifconfig()[0]
    print("WiFi connected — IP:", ip)
    return ip


# ---------------------------------------------------------------------------
# Servo driver (Freenove Smart Car Shield, I2C 0x18)
# ---------------------------------------------------------------------------

I2C_ADDR = 0x18
CMD_SERVO1 = 0
SERVO_MIN_US = 500
SERVO_MAX_US = 2500

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)


def _angle_to_pulse(angle):
    angle = max(0.0, min(180.0, angle))
    return int(SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * (angle / 180.0))


def servo(angle: float):
    """Send angle to servo 1 via I2C (written 3× for shield reliability)."""
    pulse = _angle_to_pulse(angle)
    payload = bytes([(pulse >> 8) & 0xFF, pulse & 0xFF])
    for _ in range(3):
        i2c.writeto_mem(I2C_ADDR, CMD_SERVO1, payload)
        time.sleep_ms(2)


# ---------------------------------------------------------------------------
# Boot sequence
# ---------------------------------------------------------------------------

connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)

# Verify shield is present
devices = i2c.scan()
if I2C_ADDR not in devices:
    raise RuntimeError(
        "Freenove shield not found at 0x18. "
        "Check SDA=GPIO21, SCL=GPIO22, common GND, and CTRL power switch."
    )
print("Freenove shield found at 0x18")

# Initialize modules
comm = Comm(
    coordinator_ip=config.COORDINATOR_IP,
    telemetry_port=config.TELEMETRY_PORT,
    command_port=config.COMMAND_PORT,
    device_id=config.DEVICE_ID,
)
vms = VectorMemoryStore(state_dim=4, action_set=ACTION_SET)
skill_runner = SkillRunner()
controller = Controller(vms, skill_runner, servo, comm)

# Run — blocks forever (Ctrl-C or hardware reset to stop)
controller.run()
