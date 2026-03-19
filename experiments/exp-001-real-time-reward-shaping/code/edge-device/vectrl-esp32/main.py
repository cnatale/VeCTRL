from machine import Pin, I2C
import time

# Freenove Smart Car Shield for RPi exposes a controller at 0x18 over I2C.
# Its servo outputs are not driven by a raw PCA9685 at 0x40.
I2C_ADDR = 0x18
CMD_SERVO1 = 0
SERVO_MIN_US = 500
SERVO_MAX_US = 2500

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)


def clamp(value, low, high):
    return max(low, min(high, value))


def angle_to_pulse_us(angle):
    angle = clamp(angle, 0, 180)
    return int(SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * (angle / 180))


def write_reg(cmd, value):
    value = int(value)
    payload = bytes([(value >> 8) & 0xFF, value & 0xFF])

    # Freenove's reference driver writes the same command multiple times
    # to improve reliability with the shield firmware.
    for _ in range(3):
        i2c.writeto_mem(I2C_ADDR, cmd, payload)
        time.sleep_ms(2)


def set_servo1_angle(angle):
    pulse_us = angle_to_pulse_us(angle)
    print("Servo1 angle:", angle, "pulse_us:", pulse_us)
    write_reg(CMD_SERVO1, pulse_us)


print("Scanning I2C...")
devices = i2c.scan()
print("Found:", [hex(device) for device in devices])

if I2C_ADDR not in devices:
    raise Exception(
        "Shield controller not found at 0x18. Check P21->SDA, P22->SCL, common GND, and CTRL power."
    )

print("Found Freenove shield at 0x18")
print("Note: Servo ports need the shield LOAD power path enabled.")
print("Make sure the shield has external DC power and both CTRL and LOAD switches are ON.")

print("Centering servo...")
set_servo1_angle(90)
time.sleep(1)

while True:
    print("Left")
    set_servo1_angle(60)
    time.sleep(1)

    print("Center")
    set_servo1_angle(90)
    time.sleep(1)

    print("Right")
    set_servo1_angle(120)
    time.sleep(1)

    print("Center")
    set_servo1_angle(90)
    time.sleep(1)