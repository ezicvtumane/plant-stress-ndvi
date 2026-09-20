import gpiod
from gpiod.line import Direction, Value
import time

LINE_OFFSET = 7

print('=== ЗАПУСК ТЕСТА СВЕТОДИОДА (5 вспышек) ===')
with gpiod.request_lines(
    '/dev/gpiochip1',
    consumer='led_cycle',
    config={
        (LINE_OFFSET,): gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE
        )
    }
) as request:
    for i in range(1, 6):
        print(f'Вспышка {i}/5: РЕЛЕ ВКЛ -> СВЕТОДИОД ДОЛЖЕН ЗАГОРЕТЬСЯ!')
        request.set_value(LINE_OFFSET, Value.ACTIVE)
        time.sleep(1.0)
        print(f'Вспышка {i}/5: РЕЛЕ ВЫКЛ -> ПОГАС')
        request.set_value(LINE_OFFSET, Value.INACTIVE)
        time.sleep(0.6)

print('=== ТЕСТ ЗАВЕРШЕН ===')
