import gpiod
from gpiod.line import Direction, Value

with gpiod.request_lines(
    '/dev/gpiochip1',
    consumer='relay_kill',
    config={(7,): gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)}
) as r:
    r.set_value(7, Value.INACTIVE)
    print('PL7 forced INACTIVE')
