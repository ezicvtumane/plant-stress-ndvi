import time
import gpiod
from gpiod.line import Direction, Value

print("=== ТЕСТ ВСПЫШКИ НА 1 СЕКУНДУ ===")
with gpiod.request_lines(
    "/dev/gpiochip1",
    consumer="flash_test",
    config={(7,): gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)}
) as r:
    print("Включаем вспышку (ACTIVE = 1)...")
    r.set_value(7, Value.ACTIVE)
    time.sleep(1.0)
    print("Выключаем вспышку (INACTIVE = 0)...")
    r.set_value(7, Value.INACTIVE)
    time.sleep(0.5)

print("Готово!")
