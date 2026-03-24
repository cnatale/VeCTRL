"""
Coordinator entry point for Exp 001 — Real-time reward shaping.

Usage:
    cd experiments/exp-001-real-time-reward-shaping/code/coordinator
    python run.py --device esp32-arm --ip 192.168.1.101 (or the current edge device network ip address)

The coordinator:
  1. Registers the edge device
  2. Sends the default skill config (reach_target_fast)
  3. Starts the telemetry logger in a background thread
  4. Runs the CLI for interactive skill switching

Telemetry is written to experiments/exp-001-.../data/.
"""

from comm import Comm
from skill_store import SkillStore
from telemetry import TelemetryLogger
from cli import CLI

import argparse
import os
import sys

# Resolve paths relative to this file
HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILLS_DIR = os.path.join(EXPERIMENT_DIR, "skills")
DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")

sys.path.insert(0, HERE)

DEFAULT_DEVICE_ID = "esp32-arm"
DEFAULT_SKILL = "reach-target-fast"
DEFAULT_TARGET = 90.0


def main():
    parser = argparse.ArgumentParser(description="VeCTRL Coordinator — Exp 001")
    parser.add_argument("--device", default=DEFAULT_DEVICE_ID, help="Device ID")
    parser.add_argument("--ip", required=True, help="ESP32 IP address")
    parser.add_argument(
        "--target",
        type=float,
        default=DEFAULT_TARGET,
        help="Initial target angle (default 90)",
    )
    parser.add_argument(
        "--skill",
        default=DEFAULT_SKILL,
        help="Initial skill (default: reach_target_fast)",
    )
    args = parser.parse_args()

    comm = Comm()
    skill_store = SkillStore(SKILLS_DIR)
    logger = TelemetryLogger(comm, DATA_DIR, experiment_id="exp-001")
    cli = CLI(comm, skill_store, device_id=args.device)

    # Register edge device
    comm.register_device(args.device, args.ip)

    # Wire telemetry callback to CLI for live stats display
    logger.add_callback(cli.set_last_packet)

    # Start telemetry logger in background
    logger.start()
    print(f"Telemetry logger started. Data → {DATA_DIR}")

    # Send initial target and skill config
    comm.send_target(args.device, args.target)
    try:
        initial_skill = skill_store.load(args.skill)
        comm.send_skill_config(args.device, initial_skill)
        print(f"Initial skill: {args.skill}  target: {args.target}°")
    except (FileNotFoundError, ValueError) as e:
        print(f"Warning: could not load initial skill '{args.skill}': {e}")

    # Run CLI (blocks until user quits)
    try:
        cli.run()
    finally:
        logger.stop()
        comm.close()
        print("Coordinator stopped.")


if __name__ == "__main__":
    main()
