#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-auto}"
MPREMOTE="${MPREMOTE:-mpremote}"

if ! command -v "$MPREMOTE" >/dev/null 2>&1; then
  echo "mpremote not found in PATH. Activate your venv first (e.g. source .venv/bin/activate)." >&2
  exit 1
fi

BOOT_DELAY_SECONDS="${BOOT_DELAY_SECONDS:-2}"

echo "Deploying main.py to device on port: $PORT (boot delay: ${BOOT_DELAY_SECONDS}s)"

# sleep <seconds> between connect and fs gives the ESP32 time to finish booting after
# pyserial toggles DTR (which causes an auto-reset on most ESP32 dev boards).
"$MPREMOTE" connect "$PORT" sleep "$BOOT_DELAY_SECONDS" fs cp main.py :

"$MPREMOTE" connect "$PORT" sleep "$BOOT_DELAY_SECONDS" soft-reset
echo "Copied main.py and soft-reset device"
