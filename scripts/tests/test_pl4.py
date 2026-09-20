import gpiod
from gpiod.line import Direction, Value
import time

print("Testing Line 4 on gpiochip1 (Physical Pin 7)...")
try:
    with gpiod.request_lines(
        '/dev/gpiochip1',
        consumer='test_pin7',
        config={(4,): gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)}
    ) as r:
        print("Line 4 requested successfully as OUTPUT (0V)!")
        time.sleep(1)
        r.set_value(4, Value.ACTIVE)
        print("Set Line 4 to ACTIVE (1 / 3.3V)!")
        time.sleep(1)
        r.set_value(4, Value.INACTIVE)
        print("Set Line 4 back to INACTIVE (0 / 0V)!")
        print("SUCCESS!")
except Exception as e:
    print("Error:", e)
