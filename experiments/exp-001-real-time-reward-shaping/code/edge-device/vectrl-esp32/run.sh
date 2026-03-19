#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-auto}"
MPREMOTE="${MPREMOTE:-mpremote}"
BOOT_DELAY_SECONDS="${BOOT_DELAY_SECONDS:-2}"

if ! command -v "$MPREMOTE" >/dev/null 2>&1; then
  echo "mpremote not found in PATH. Activate your venv first (e.g. source .venv/bin/activate)." >&2
  exit 1
fi

echo "Restarting deployed app on device port: $PORT"
"$MPREMOTE" connect "$PORT" sleep "$BOOT_DELAY_SECONDS"
echo "Device rebooted; deployed main.py should now be running"