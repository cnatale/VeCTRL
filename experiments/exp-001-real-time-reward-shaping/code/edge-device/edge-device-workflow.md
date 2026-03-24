# Edge Device Workflow

This experiment uses MicroPython on an ESP32-S Development Board. The app entrypoint on the device is `vectrl-esp32/main.py`. `vectrl-esp32/boot.py` is currently empty, so the device boots straight into `main.py`.

It should work on other ESP-32's, with minor changes to pin references.

## Setup

From the repo root:

```bash
uv venv
source .venv/bin/activate
uv pip install mpremote
```

Then change into the device directory:

```bash
cd experiments/exp-001-real-time-reward-shaping/code/edge-device/vectrl-esp32
```

## Serial Port

On this machine, the ESP32 has been showing up as:

```bash
/dev/cu.usbserial-0001
```

If `auto` is unreliable, pass the port explicitly to every script.

## Workflow

Before the first deploy, create the local device config:

```bash
cp config.example.py config.py
```

Then fill in `config.py` with your WiFi credentials and coordinator IP.

Deploy the full Experiment 001 runtime to the device and restart it:

```bash
./deploy.sh /dev/cu.usbserial-0001
```

Restart the already-deployed app without copying files again:

```bash
./run.sh /dev/cu.usbserial-0001
```

Reset the device:

```bash
./reset.sh /dev/cu.usbserial-0001
```

Open an interactive REPL:

```bash
./repl.sh /dev/cu.usbserial-0001
```

## What Each Script Does

- `deploy.sh` copies the full Experiment 001 MicroPython runtime to the ESP32 filesystem: `config.py`, `comm.py`, `vms.py`, `skill_runner.py`, `controller.py`, `boot.py`, and `main.py`. It then soft-resets the board so the new code starts.
- `run.sh` reboots the board so the deployed `main.py` runs again.
- `reset.sh` also reboots the board. Right now it is effectively the same as `run.sh`.
- `repl.sh` opens a serial REPL session.

## Important Notes

- Close `picocom` before using `mpremote`. Only one process can own the serial port at a time.
- This ESP32 appears to auto-reset when the serial port is opened. Because of that, `mpremote` raw-REPL commands can be flaky on this board.
- The helper scripts are written to avoid depending on raw REPL where possible.
- `deploy.sh` expects `config.py` to exist locally and will fail fast if it is missing.
- `deploy.sh` changes into its own directory before copying files, so you can invoke it either from the `vectrl-esp32/` directory or from the repo root via its full relative path.
- If deploy timing is flaky, try increasing the delay:

```bash
BOOT_DELAY_SECONDS=3 ./deploy.sh /dev/cu.usbserial-0001
```
