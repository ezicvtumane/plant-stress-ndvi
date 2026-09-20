import time
import sys
import gpiod
from gpiod.line import Direction, Value

print("="*60)
print("CLICKING PL7 (line 7 on gpiochip1) AND PL4 (line 4 on gpiochip1)")
print("="*60)

# We will pulse line 7 (PL7 / Pin 10) 10 times, then line 4 (PL4 / Pin 7) 10 times!
for target_line, name in [(7, "PL7 (Pin 10)"), (4, "PL4 (Pin 7)")]:
    print(f"\n>>> ACTIVATING {name} ON /dev/gpiochip1 <<<", flush=True)
    try:
        settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE
        )
        with gpiod.request_lines(
            "/dev/gpiochip1",
            consumer="relay-clicker",
            config={target_line: settings}
        ) as request:
            print(f"Clicking {name} 10 times (щелкаем!)...", flush=True)
            for i in range(1, 11):
                request.set_value(target_line, Value.ACTIVE)
                print(f"[{name}] CLICK #{i} ON", flush=True)
                time.sleep(0.4)
                request.set_value(target_line, Value.INACTIVE)
                print(f"[{name}] CLICK #{i} OFF", flush=True)
                time.sleep(0.4)
    except Exception as e:
        print(f"Error on {name}: {e}", flush=True)

print("\n" + "="*60)
print("TEST FINISHED!")
print("="*60)
