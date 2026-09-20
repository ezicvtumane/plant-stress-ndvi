import time
import sys
import gpiod
from gpiod.line import Direction, Value

# Sweep all likely GPIO lines for Pin 7 / 40-pin header on Allwinner
# Port B: 32..40
# Port C: 71
# Port D: 96..116
# Port I: 256..261
candidates = [32, 33, 34, 35, 36, 37, 40, 71, 96, 97, 98, 99, 100, 101, 102, 103, 256, 257, 258, 259]

print("="*60)
print("STARTING ORANGE PI 4 PRO RELAY TOGGLE TEST")
print("="*60)

for line_idx in candidates:
    try:
        settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE
        )
        with gpiod.request_lines(
            "/dev/gpiochip0",
            consumer="relay-tester",
            config={line_idx: settings}
        ) as request:
            print(f"Testing line {line_idx} (clicking 4 times)...", flush=True)
            for _ in range(4):
                request.set_value(line_idx, Value.ACTIVE)
                time.sleep(0.25)
                request.set_value(line_idx, Value.INACTIVE)
                time.sleep(0.25)
    except Exception as e:
        print(f"Line {line_idx} skipped: {e}", flush=True)

print("="*60)
print("TEST COMPLETED!")
print("="*60)
