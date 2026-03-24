"""
UDP communication layer for VeCTRL edge device (MicroPython).

Sends telemetry to the coordinator (non-blocking fire-and-forget).
Receives commands from the coordinator (non-blocking poll).

Reads COORDINATOR_IP, TELEMETRY_PORT, COMMAND_PORT, and DEVICE_ID from config.py.
"""

import json
import socket


class Comm:
    def __init__(self, coordinator_ip, telemetry_port, command_port, device_id):
        self.device_id = device_id
        self._coordinator_ip = coordinator_ip
        self._telemetry_port = telemetry_port
        self._telemetry_sent = 0
        self._telemetry_send_errors = 0
        self._last_telemetry_error = ""
        self._commands_received = 0
        self._command_receive_errors = 0
        self._last_command_error = ""

        # Receive socket: binds to command port, non-blocking
        self._recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._recv_sock.bind(("0.0.0.0", command_port))
        self._recv_sock.setblocking(False)

        # Send socket: used for telemetry (fire-and-forget)
        self._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_telemetry(self, packet: dict):
        """
        Serialize and send a telemetry packet to the coordinator.
        Non-blocking — increments counters on error for debug visibility.
        """
        try:
            data = json.dumps(packet).encode("utf-8")
            self._send_sock.sendto(data, (self._coordinator_ip, self._telemetry_port))
            self._telemetry_sent += 1
        except Exception as e:
            self._telemetry_send_errors += 1
            self._last_telemetry_error = repr(e)

    def recv_command(self):
        """
        Non-blocking receive of a command packet from the coordinator.
        Returns the decoded dict, or None if no packet is waiting.
        """
        try:
            data, _ = self._recv_sock.recvfrom(2048)
        except OSError:
            return None

        try:
            msg = json.loads(data.decode("utf-8"))
            self._commands_received += 1
            return msg
        except Exception as e:
            self._command_receive_errors += 1
            self._last_command_error = repr(e)
            return None

    def stats(self) -> dict:
        """Return lightweight transport counters for periodic debug logging."""
        return {
            "telemetry_sent": self._telemetry_sent,
            "telemetry_send_errors": self._telemetry_send_errors,
            "last_telemetry_error": self._last_telemetry_error,
            "commands_received": self._commands_received,
            "command_receive_errors": self._command_receive_errors,
            "last_command_error": self._last_command_error,
        }
