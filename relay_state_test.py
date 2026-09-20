import time
import gpiod
from gpiod.line import Direction, Value

print("=== ТЕСТ СОСТОЯНИЯ РЕЛЕ ===")
print("1. Захватываем пин и ставим LOW (0)")
with gpiod.request_lines(
    "/dev/gpiochip1",
    consumer="relay_probe",
    config={(7,): gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)}
) as r:
    print("Состояние LOW (0V). Ждем 3 сек...")
    time.sleep(3)
    print("2. Переключаем в HIGH (3.3V)")
    r.set_value(7, Value.ACTIVE)
    print("Состояние HIGH (3.3V). Ждем 3 сек...")
    time.sleep(3)
    print("3. Возвращаем в LOW (0V)")
    r.set_value(7, Value.INACTIVE)
    time.sleep(3)

print("Линия освобождена (вернулась в INPUT).")
