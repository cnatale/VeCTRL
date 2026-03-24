"""
UDP communication layer for the VeCTRL coordinator (Exp 1).

Two channels:
  Telemetry (edge → coordinator): port 5005, one packet per control tick
  Commands  (coordinator → edge): port 5006, event-driven

All messages are JSON-encoded. Every message includes device_id for
routing in multi-device setups (Exp 4+).
"""

import json
import socket


TELEMETRY_PORT = 5005
COMMAND_PORT = 5006
BUFFER_SIZE = 2048


class Comm:
    def __init__(
        self, telemetry_port: int = TELEMETRY_PORT, command_port: int = COMMAND_PORT
    ):
        self._telemetry_port = telemetry_port
        self._command_port = command_port

        # Device registry: device_id -> (ip, command_port)
        self._devices: dict = {}

        # Telemetry receive socket
        self._recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._recv_sock.bind(("0.0.0.0", self._telemetry_port))
        self._recv_sock.settimeout(0.0)  # non-blocking

        # Command send socket (shared for all devices)
        self._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def register_device(
        self, device_id: str, ip: str, command_port: int = COMMAND_PORT
    ):
        """Register an edge device so the coordinator can address it."""
        self._devices[device_id] = (ip, command_port)

    def send_skill_config(self, device_id: str, skill_config: dict):
        """Send a skill config to the named device."""
        msg = {
            "type": "skill_config",
            "device_id": device_id,
            "payload": skill_config,
        }
        self._send(device_id, msg)

    def send_target(self, device_id: str, angle: float):
        """Update the target angle on the named device."""
        msg = {
            "type": "target",
            "device_id": device_id,
            "angle": angle,
        }
        self._send(device_id, msg)

    def recv_telemetry(self) -> dict | None:
        """
        Non-blocking receive. Returns the next telemetry packet as a dict,
        or None if no packet is available.
        """
        try:
            data, addr = self._recv_sock.recvfrom(BUFFER_SIZE)
            packet = json.loads(data.decode("utf-8"))
            # Auto-register device on first telemetry packet
            device_id = packet.get("device_id")
            if device_id and device_id not in self._devices:
                self.register_device(device_id, addr[0])
            return packet
        except BlockingIOError, OSError:
            return None

    def drain_telemetry(self) -> list:
        """Return all pending telemetry packets (may be empty)."""
        packets = []
        while True:
            p = self.recv_telemetry()
            if p is None:
                break
            packets.append(p)
        return packets

    def close(self):
        self._recv_sock.close()
        self._send_sock.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(self, device_id: str, msg: dict):
        if device_id not in self._devices:
            print(f"Comm: unknown device_id '{device_id}' — register first")
            return
        ip, port = self._devices[device_id]
        data = json.dumps(msg).encode("utf-8")
        self._send_sock.sendto(data, (ip, port))
