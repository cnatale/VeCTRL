# config.example.py
#
# Copy this file to config.py and fill in your values.
# config.py is gitignored — do not commit credentials.
#
# Deploy to ESP32:
#   mpremote connect /dev/tty.usbserial-XXXX fs cp config.py :config.py

WIFI_SSID = "your-network-name"
WIFI_PASSWORD = "your-password"

# IP address of the machine running run.py (coordinator)
COORDINATOR_IP = "192.168.1.100"

# UDP ports — must match coordinator/comm.py defaults
TELEMETRY_PORT = 5005  # edge → coordinator
COMMAND_PORT = 5006  # coordinator → edge

# Unique identifier for this device — appears in all telemetry packets
DEVICE_ID = "esp32-arm"
