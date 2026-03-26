"""
Automated skill-comparison experiment for Exp 001.

Runs two back-to-back trials on the same edge device:
  1. reach-target-fast:     target 0° → 180° → 90°
  2. reach-target-smoothly: target 0° → 180° → 90°

Each target is held for --dwell seconds to allow the controller to settle.
Telemetry is logged to a single CSV via TelemetryLogger for post-hoc analysis.

Usage:
    cd experiments/exp-001-real-time-reward-shaping/code/coordinator
    python run_skill_comparison.py --ip <ESP32_IP> [--dwell 20] [--device esp32-arm]
"""

import argparse
import os
import time

from comm import Comm
from skill_store import SkillStore
from telemetry import TelemetryLogger

HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILLS_DIR = os.path.join(EXPERIMENT_DIR, "skills")
DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")

DEFAULT_DEVICE_ID = "esp32-arm"
TARGETS = [0.0, 180.0, 90.0]
SKILLS = ["reach-target-fast", "reach-target-smoothly"]


def wait_with_countdown(seconds: int, label: str):
    for remaining in range(seconds, 0, -1):
        print(f"  {label} — {remaining}s remaining", end="\r", flush=True)
        time.sleep(1)
    print(f"  {label} — done.               ")


def run_trial(comm, skill_store, device_id: str, skill_id: str, dwell: int):
    """Send a skill config then cycle through TARGETS, dwelling at each."""
    config = skill_store.load(skill_id)
    comm.send_skill_config(device_id, config)
    print(f"\n{'=' * 60}")
    print(f"  Skill: {skill_id}")
    print(f"{'=' * 60}")

    time.sleep(1)

    for target in TARGETS:
        comm.send_target(device_id, target)
        print(f"\n  Target → {target}°")
        wait_with_countdown(dwell, f"{skill_id} @ {target}°")


def main():
    parser = argparse.ArgumentParser(description="VeCTRL Skill Comparison — Exp 001")
    parser.add_argument("--device", default=DEFAULT_DEVICE_ID, help="Device ID")
    parser.add_argument("--ip", required=True, help="ESP32 IP address")
    parser.add_argument(
        "--dwell",
        type=int,
        default=20,
        help="Seconds to dwell at each target angle (default: 20)",
    )
    args = parser.parse_args()

    comm = Comm()
    skill_store = SkillStore(SKILLS_DIR)
    logger = TelemetryLogger(comm, DATA_DIR, experiment_id="exp-001")

    comm.register_device(args.device, args.ip)
    logger.start()
    print(f"Telemetry logger started. Data → {DATA_DIR}")

    total_time = args.dwell * len(TARGETS) * len(SKILLS)
    print(
        f"Running {len(SKILLS)} skills × {len(TARGETS)} targets × {args.dwell}s dwell"
    )
    print(f"Estimated total: {total_time}s ({total_time // 60}m {total_time % 60}s)")

    try:
        for skill_id in SKILLS:
            run_trial(comm, skill_store, args.device, skill_id, args.dwell)

        print(f"\n{'=' * 60}")
        print("  Experiment complete.")
        print(f"{'=' * 60}")
    finally:
        logger.stop()
        comm.close()
        print("Coordinator stopped.")


if __name__ == "__main__":
    main()
