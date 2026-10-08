import os
import sys
import time
import subprocess
import gpiod
from gpiod.line import Direction, Value, Bias

print("=== Starting I2C-0 Bus Recovery via GPIO Clocking ===")

# 1. Unbind sunxi-twi driver so pins are free
subprocess.run("echo 2510000.twi > /sys/bus/platform/drivers/sunxi-twi/unbind", shell=True, check=False)
time.sleep(0.1)

# Orange Pi 4 Pro PB2 = line 34 (SCL), PB3 = line 35 (SDA) on /dev/gpiochip0
chip_path = '/dev/gpiochip0'
LINE_SCL = 34
LINE_SDA = 35

try:
    with gpiod.request_lines(
        chip_path,
        consumer='i2c_recovery',
        config={
            LINE_SCL: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),
            LINE_SDA: gpiod.LineSettings(direction=Direction.INPUT)
        }
    ) as request:
        print("Pins acquired. Checking initial SDA state...")
        sda_val = request.get_value(LINE_SDA)
        print(f"Initial SDA value: {sda_val}")

        # Clock SCL 18 times to clear any stuck slave state machine
        for cycle in range(18):
            request.set_value(LINE_SCL, Value.INACTIVE) # SCL LOW
            time.sleep(0.001)
            request.set_value(LINE_SCL, Value.ACTIVE)   # SCL HIGH
            time.sleep(0.001)
            cur_sda = request.get_value(LINE_SDA)
            if cur_sda == Value.ACTIVE and cycle >= 9:
                print(f"SDA released HIGH on cycle {cycle + 1}!")
                break

        sda_final = request.get_value(LINE_SDA)
        print(f"SDA state after clocking: {sda_final}")

except Exception as e:
    print(f"Error during GPIO clocking: {e}")

# Rebind driver
time.sleep(0.1)
subprocess.run("echo 2510000.twi > /sys/bus/platform/drivers/sunxi-twi/bind", shell=True, check=False)
time.sleep(0.2)
print("sunxi-twi driver rebound.")
