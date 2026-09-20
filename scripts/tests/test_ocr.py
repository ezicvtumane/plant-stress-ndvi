import pytesseract
import cv2
import re
import numpy as np

# Загружаем реальный кадр с тепловизора
img = cv2.imread('/home/pi/plant-stress-ndvi/static/last_thermal.jpg')
h, w, _ = img.shape

# Область центральной температуры (левый верхний угол: Y 0..60, X 0..120)
crop = img[0:70, 0:130]

# Бинаризуем белые цифры шрифта тепловизора
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)

# Распознаем цифры
text = pytesseract.image_to_string(thresh, config='--psm 6 -c tessedit_char_whitelist=0123456789.C°')
print('Распознанный сырой текст:', repr(text.strip()))

# Извлекаем первое число с точкой
m = re.search(r'(\d{1,2}[\.,]\d)', text)
if m:
    val = float(m.group(1).replace(',', '.'))
    print(f'✅ УСПЕХ: Настоящая температура листа распознана: {val} °C')
else:
    print('Поиск по регулярке не нашел, проверим весь угол...')
