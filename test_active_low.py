import time
import gpiod
from gpiod.line import Direction, Value

print("Testing active_low=True in gpiod...")
# When active_low=True:
# Value.INACTIVE -> outputs HIGH (3.3V) -> Active-LOW Relay is OFF!
# Value.ACTIVE   -> outputs LOW  (0.0V) -> Active-LOW Relay is ON!
settings = gpiod.LineSettings(
    direction=Direction.OUTPUT,
    active_low=True,
    output_value=Value.INACTIVE
)

with gpiod.request_lines(
    '/dev/gpiochip1',
    consumer='test_active_low',
    config={(4,): settings, (7,): settings}
) as r:
    print("1. Set to INACTIVE: Relay should be OFF (лампа не горит) for 3s...")
    r.set_value(4, Value.INACTIVE)
    r.set_value(7, Value.INACTIVE)
    time.sleep(3)

    print("2. Set to ACTIVE: Relay should CLICK ON (лампа горит) for 2s...")
    r.set_value(4, Value.ACTIVE)
    r.set_value(7, Value.ACTIVE)
    time.sleep(2)

    print("3. Set back to INACTIVE: Relay should CLICK OFF (лампа погасла) for 3s...")
    r.set_value(4, Value.INACTIVE)
    r.set_value(7, Value.INACTIVE)
    time.sleep(3)

print("Test complete.")
