"""
VeCTRL edge device entry point — Exp 001 (Platform A, single servo).

Connects to WiFi, initializes all modules, and runs the control loop.
"""

import network  # type: ignore
import time
from machine import Pin, I2C  # type: ignore

import config
from comm import Comm
from vms import VectorMemoryStore
from skill_runner import SkillRunner
from controller import ACTION_SET, Controller

# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------


WIFI_STATUS_NAMES = {
    getattr(network, "STAT_IDLE", 1000): "IDLE",
    getattr(network, "STAT_CONNECTING", 1001): "CONNECTING",
    getattr(network, "STAT_WRONG_PASSWORD", -3): "WRONG_PASSWORD",
    getattr(network, "STAT_NO_AP_FOUND", -2): "NO_AP_FOUND",
    getattr(network, "STAT_CONNECT_FAIL", -1): "CONNECT_FAIL",
    getattr(network, "STAT_GOT_IP", 1010): "GOT_IP",
}

WIFI_FAILURE_STATUSES = (
    getattr(network, "STAT_WRONG_PASSWORD", -3),
    getattr(network, "STAT_NO_AP_FOUND", -2),
    getattr(network, "STAT_CONNECT_FAIL", -1),
)


def wifi_status_name(status):
    return WIFI_STATUS_NAMES.get(status, "UNKNOWN(%s)" % status)


def scan_for_target_ssid(wlan, target_ssid):
    try:
        networks = wlan.scan()
    except Exception as exc:
        print("WiFi scan failed:", exc)
        return

    print("Visible WiFi networks:", len(networks))
    target_found = False
    for entry in networks:
        ssid_bytes, bssid, channel, rssi, authmode, hidden = entry
        try:
            name = ssid_bytes.decode("utf-8")
        except Exception:
            name = str(ssid_bytes)
        if name == target_ssid:
            target_found = True
            print(
                "Target SSID visible:",
                name,
                "channel=%s" % channel,
                "rssi=%s" % rssi,
                "authmode=%s" % authmode,
                "hidden=%s" % hidden,
                "bssid=%s" % "".join("%02x" % byte for byte in bssid),
            )

    if not target_found:
        print("Target SSID not found in scan results:", target_ssid)


def connect_wifi(ssid, password, timeout_s=20):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print("WiFi station active:", wlan.active())
    print("Initial WiFi status:", wifi_status_name(wlan.status()))

    if wlan.isconnected():
        print("WiFi already connected:", wlan.ifconfig())
        return wlan.ifconfig()[0]

    try:
        wlan.disconnect()
    except Exception:
        pass

    scan_for_target_ssid(wlan, ssid)
    print("Connecting to WiFi:", ssid)
    wlan.connect(ssid, password)

    deadline = time.time() + timeout_s
    last_status = None
    while not wlan.isconnected():
        status = wlan.status()
        if status != last_status:
            print("WiFi status changed:", wifi_status_name(status))
            last_status = status
        if status in WIFI_FAILURE_STATUSES:
            raise RuntimeError("WiFi connect failed: %s" % wifi_status_name(status))
        if time.time() > deadline:
            raise RuntimeError(
                "WiFi connection timed out (last status: %s)" % wifi_status_name(status)
            )
        time.sleep(0.5)

    ip = wlan.ifconfig()[0]
    print("WiFi connected:", wlan.ifconfig())
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
vms = VectorMemoryStore(state_dim=2, action_set=ACTION_SET)
skill_runner = SkillRunner()
controller = Controller(vms, skill_runner, servo, comm)

# Run — blocks forever (Ctrl-C or hardware reset to stop)
controller.run()
