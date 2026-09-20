import time
import gpiod
from gpiod.line import Direction, Value

print("Testing gpiod: setting PL7 and PL4 to ACTIVE (3.3V)...")
settings = gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)
with gpiod.request_lines('/dev/gpiochip1', consumer='test_active', config={(7,): settings, (4,): settings}) as r:
    print("Pins set to HIGH (3.3V). Holding for 5s... Is the light OFF now?")
    time.sleep(5)

print("Test complete.")
