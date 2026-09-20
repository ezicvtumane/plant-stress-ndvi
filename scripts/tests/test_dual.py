import gpiod
from gpiod.line import Direction, Value

settings = gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)
with gpiod.request_lines(
    "/dev/gpiochip1",
    consumer="dual_test",
    config={(4,): settings, (7,): settings}
) as r:
    r.set_value(4, Value.ACTIVE)
    r.set_value(7, Value.ACTIVE)
    r.set_value(4, Value.INACTIVE)
    r.set_value(7, Value.INACTIVE)
    print("DUAL PINS 4 AND 7 TEST SUCCESS!")
