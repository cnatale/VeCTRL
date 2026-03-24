#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-auto}"
MPREMOTE="${MPREMOTE:-mpremote}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BOOT_DELAY_SECONDS="${BOOT_DELAY_SECONDS:-2}"

FILES=(
  config.py
  comm.py
  vms.py
  skill_runner.py
  controller.py
  boot.py
  main.py
)

cd "$SCRIPT_DIR"

if ! command -v "$MPREMOTE" >/dev/null 2>&1; then
  echo "mpremote not found in PATH. Activate your venv first (e.g. source .venv/bin/activate)." >&2
  exit 1
fi

for file in "${FILES[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file" >&2
    if [[ "$file" == "config.py" ]]; then
      echo "Create it from config.example.py and fill in your WiFi/coordinator settings before deploying." >&2
    fi
    exit 1
  fi
done

echo "Deploying Experiment 001 file set to device on port: $PORT (boot delay: ${BOOT_DELAY_SECONDS}s)"
printf '  - %s\n' "${FILES[@]}"

# sleep <seconds> between connect and fs gives the ESP32 time to finish booting after
# pyserial toggles DTR (which causes an auto-reset on most ESP32 dev boards).
"$MPREMOTE" connect "$PORT" sleep "$BOOT_DELAY_SECONDS" fs cp "${FILES[@]}" ":."
"$MPREMOTE" connect "$PORT" sleep "$BOOT_DELAY_SECONDS" soft-reset
echo "Copied ${#FILES[@]} files and soft-reset device"
