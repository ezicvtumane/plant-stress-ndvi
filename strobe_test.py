"""
Strobe & Camera Synchronized Test
Toggles relay on PL7 (gpiochip1, line 7, Pin 10) and captures ambient vs flash frames.
"""
import time
import cv2
import numpy as np
import gpiod
from gpiod.line import Direction, Value

GPIO_CHIP = "/dev/gpiochip1"
RELAY_LINE = 7  # PL7 (Pin 10)

print("="*60)
print("STARTING STROBE + CAMERA ACQUISITION TEST (PL7 / Pin 10)")
print("="*60)

# 1. Initialize Camera
print("1. Initializing camera on /dev/video0...", flush=True)
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
if not cap.isOpened():
    print("ERROR: Could not open camera.")
    exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# Flush buffer
for _ in range(5):
    cap.grab()

# 2. Control Relay on PL7
settings = gpiod.LineSettings(
    direction=Direction.OUTPUT,
    output_value=Value.INACTIVE
)

with gpiod.request_lines(GPIO_CHIP, consumer="strobe-test", config={RELAY_LINE: settings}) as relay:
    # Ensure relay is OFF
    relay.set_value(RELAY_LINE, Value.INACTIVE)
    time.sleep(0.5)

    # Frame 1: Ambient (LED OFF)
    print("2. Capturing AMBIENT frame (Relay OFF)...", flush=True)
    for _ in range(3):
        cap.grab()
    ret, ambient = cap.read()
    if not ret or ambient is None:
        print("Failed to capture ambient frame.")
        exit(1)
    cv2.imwrite("/home/pi/plant-stress-ndvi/ambient_test.jpg", ambient)
    print("   -> Saved ambient_test.jpg")

    # Turn Relay ON (Flash)
    print("3. Turning RELAY ON (FLASH)...", flush=True)
    relay.set_value(RELAY_LINE, Value.ACTIVE)
    time.sleep(0.5)  # Let light stabilize

    # Frame 2: Flash (LED ON)
    print("4. Capturing FLASH frame (Relay ON)...", flush=True)
    for _ in range(3):
        cap.grab()
    ret, flash = cap.read()
    if not ret or flash is None:
        print("Failed to capture flash frame.")
        exit(1)
    cv2.imwrite("/home/pi/plant-stress-ndvi/flash_test.jpg", flash)
    print("   -> Saved flash_test.jpg")

    # Turn Relay OFF
    print("5. Turning RELAY OFF...", flush=True)
    relay.set_value(RELAY_LINE, Value.INACTIVE)
    time.sleep(0.2)

cap.release()

# 3. Calculate Difference Matrix (Background Subtraction)
diff = np.maximum(0, flash.astype(np.float32) - ambient.astype(np.float32)).astype(np.uint8)
cv2.imwrite("/home/pi/plant-stress-ndvi/diff_subtracted.jpg", diff)

mean_amb = np.mean(ambient)
mean_fls = np.mean(flash)
mean_dif = np.mean(diff)

print("="*60)
print(f"RESULTS:")
print(f"Mean Ambient Intensity: {mean_amb:.2f}")
print(f"Mean Flash Intensity:   {mean_fls:.2f}")
print(f"Mean Net Delta Light:   +{mean_dif:.2f}")
print(f"Files saved in /home/pi/plant-stress-ndvi:")
print("  - ambient_test.jpg")
print("  - flash_test.jpg")
print("  - diff_subtracted.jpg")
print("="*60)
