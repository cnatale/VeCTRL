#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-auto}"
mpremote connect "$PORT" repl