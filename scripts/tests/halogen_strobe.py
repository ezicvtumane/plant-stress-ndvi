import cv2
import gpiod
from gpiod.line import Direction, Value
import time
import numpy as np

LINE_OFFSET = 7

print('1. Открываем камеру /dev/video0...')
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print('ОШИБКА: Не удалось открыть камеру')
    exit(1)

# Сброс буфера кадров
for _ in range(5):
    cap.read()

with gpiod.request_lines(
    '/dev/gpiochip1',
    consumer='strobe_halogen',
    config={
        (LINE_OFFSET,): gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE
        )
    }
) as relay:
    print('2. Лампа выключена. Делаем контрольный снимок (Ambient)...')
    time.sleep(0.5)
    for _ in range(5):
        cap.read()
    ret, frame_ambient = cap.read()
    if not ret:
        print('ОШИБКА: Не удалось захватить контрольный кадр')
        exit(1)
    cv2.imwrite('/home/pi/plant-stress-ndvi/ambient_halogen.jpg', frame_ambient)
    mean_amb = np.mean(frame_ambient)
    print(f'   Контрольный снимок сохранен. Средняя яркость: {mean_amb:.2f}')

    print('3. ВКЛЮЧАЕМ ЛАМПУ 12В (реле ON)...')
    relay.set_value(LINE_OFFSET, Value.ACTIVE)
    # Даем галогенке 0.4 секунды на прогрев спирали
    time.sleep(0.4)
    for _ in range(5):
        cap.read()
    ret, frame_flash = cap.read()
    if not ret:
        print('ОШИБКА: Не удалось захватить кадр со вспышкой')
        relay.set_value(LINE_OFFSET, Value.INACTIVE)
        exit(1)
    cv2.imwrite('/home/pi/plant-stress-ndvi/flash_halogen.jpg', frame_flash)
    mean_flash = np.mean(frame_flash)
    print(f'   Снимок с лампой сохранен. Средняя яркость: {mean_flash:.2f}')

    print('4. ВЫКЛЮЧАЕМ ЛАМПУ (реле OFF)...')
    relay.set_value(LINE_OFFSET, Value.INACTIVE)

cap.release()

# 5. Сравнение и вычитание фоновой засветки
diff = cv2.subtract(frame_flash, frame_ambient)
cv2.imwrite('/home/pi/plant-stress-ndvi/diff_halogen.jpg', diff)

# С тепловой картой прироста освещенности (colormap)
diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
diff_heatmap = cv2.applyColorMap(diff_gray, cv2.COLORMAP_JET)
cv2.imwrite('/home/pi/plant-stress-ndvi/diff_heatmap.jpg', diff_heatmap)

delta = mean_flash - mean_amb
print(f'=== ИТОГ: Прирост освещенности от галогенки: +{delta:.2f} единиц ===')
