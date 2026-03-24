"""
Telemetry receiver and CSV logger for the VeCTRL coordinator.

Receives UDP telemetry packets from edge devices and writes them to CSV.
One CSV file per run, named: {device_id}_{experiment_id}_{timestamp}.csv

See docs/architecture/telemetry-schema.md for packet format.
"""

import csv
import datetime
import os
import threading


CSV_COLUMNS = [
    "ts",
    "device_id",
    "skill_id",
    "commanded_angle",
    "target_angle",
    "error",
    "prev_error",
    "action_idx",
    "action_value",
    "reward",
    "q_value",
    "td_error",
    "epsilon",
    "memory_size",
    "retrieval_k",
    "neighbor_agreement",
    "tick_duration_ms",
    "skill_elapsed_ms",
]


class TelemetryLogger:
    def __init__(self, comm, output_dir: str, experiment_id: str = "exp-001"):
        """
        Args:
            comm:          Comm instance (provides recv_telemetry)
            output_dir:    directory to write CSV files (experiments/.../data/)
            experiment_id: label used in CSV filenames
        """
        self._comm = comm
        self._output_dir = output_dir
        self._experiment_id = experiment_id
        self._writers: dict = {}  # device_id -> csv.DictWriter
        self._files: dict = {}  # device_id -> file handle
        self._running = False
        self._thread = None
        self._callbacks: list = []  # callables(packet) for streaming display

        os.makedirs(output_dir, exist_ok=True)

    def add_callback(self, fn):
        """Register a callable(packet) invoked on each received packet."""
        self._callbacks.append(fn)

    def start(self):
        """Start receiving telemetry in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background thread and flush/close all CSV files."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        for f in self._files.values():
            f.flush()
            f.close()
        self._files.clear()
        self._writers.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _loop(self):
        import time

        while self._running:
            packets = self._comm.drain_telemetry()
            for packet in packets:
                self._handle(packet)
            time.sleep(0.01)  # 100 Hz poll — faster than 20 Hz edge

    def _handle(self, packet: dict):
        device_id = packet.get("device_id", "unknown")
        writer = self._get_writer(device_id)

        row = {
            "ts": packet.get("ts", ""),
            "device_id": device_id,
            "skill_id": packet.get("skill_id", ""),
            "commanded_angle": packet.get("state", {}).get("commanded_angle", ""),
            "target_angle": packet.get("state", {}).get("target_angle", ""),
            "error": packet.get("state", {}).get("error", ""),
            "prev_error": packet.get("state", {}).get("prev_error", ""),
            "action_idx": packet.get("action", {}).get("idx", ""),
            "action_value": packet.get("action", {}).get("value", ""),
            "reward": packet.get("learning", {}).get("reward", ""),
            "q_value": packet.get("learning", {}).get("q_value", ""),
            "td_error": packet.get("learning", {}).get("td_error", ""),
            "epsilon": packet.get("learning", {}).get("epsilon", ""),
            "memory_size": packet.get("memory", {}).get("size", ""),
            "retrieval_k": packet.get("memory", {}).get("retrieval_k", ""),
            "neighbor_agreement": packet.get("memory", {}).get(
                "neighbor_agreement", ""
            ),
            "tick_duration_ms": packet.get("memory", {}).get("tick_duration_ms", ""),
            "skill_elapsed_ms": packet.get("skill", {}).get("elapsed_ms", ""),
        }
        writer.writerow(row)
        self._files[device_id].flush()

        for fn in self._callbacks:
            try:
                fn(packet)
            except Exception:
                print(f"TelemetryLogger._handle: error handling packet: {Exception}")
                pass

    def _get_writer(self, device_id: str) -> csv.DictWriter:
        if device_id not in self._writers:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{device_id}_{self._experiment_id}_{ts}.csv"
            path = os.path.join(self._output_dir, filename)
            f = open(path, "w", newline="")
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            self._files[device_id] = f
            self._writers[device_id] = writer
            print(f"TelemetryLogger: writing to {path}")
        return self._writers[device_id]
