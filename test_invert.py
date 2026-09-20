import gpiod
from gpiod.line import Direction, Value
import time

# Держим высокий уровень 3.3V в течение 10 секунд
with gpiod.request_lines(
    '/dev/gpiochip1',
    consumer='test_invert',
    config={(7,): gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)}
) as r:
    r.set_value(7, Value.ACTIVE)
    print('Подан сигнал 3.3V (ACTIVE). Лампа должна ПОГАСНУТЬ!')
    time.sleep(10)

print('Тест завершен')
