#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Комплексная аппаратная диагностика станции после пересборки электроники:
1. Сканирование шины I2C-0 (SHT30 @ 0x44, ADS1115 @ 0x48).
2. Опрос климатического датчика SHT30 (T, RH).
3. Опрос емкостного датчика влажности почвы через АЦП ADS1115 (A0: Raw, V, %).
4. Тестирование оптоизолированных реле Songle (GPIOchip 1, линии 4 и 7) для ИК 850 нм и Red 660 нм.
5. Проверка USB-камеры IMX179 NoIR (/dev/video0).
"""

import sys
import time
import socket
import paramiko

sys.stdout.reconfigure(encoding='utf-8')

HOST = '192.168.0.23'
PORT = 22
USER = 'pi'
PWD = '1'

def check_reachability(host, port, timeout=2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def main():
    print("=" * 65)
    print("  КОМПЛЕКСНАЯ ДИАГНОСТИКА ОБОРУДОВАНИЯ (Orange Pi 4 Pro)")
    print("=" * 65)
    
    if not check_reachability(HOST, PORT):
        print(f"\n[!] ОШИБКА ПОДКЛЮЧЕНИЯ: Orange Pi ({HOST}:{PORT}) недоступен по сети.")
        print("    -> Проверьте подключение кабеля питания (Type-C / 5V 3A)")
        print("    -> Проверьте подключение Ethernet или статус Wi-Fi соединения.")
        sys.exit(1)

    print(f"[OK] Сетевой узел {HOST} доступен. Подключение по SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=10)

    # Remote python diagnostic code to run on Orange Pi
    remote_code = '''import sys, os, time, smbus2, gpiod, cv2
from gpiod.line import Direction, Value

sys.stdout.reconfigure(encoding='utf-8')
results = []

print("\\n--- 1. СКАНИРОВАНИЕ ШИНЫ I2C (I2C-0) ---")
try:
    bus = smbus2.SMBus(0)
    found_addrs = []
    for addr in range(0x03, 0x78):
        try:
            bus.read_byte(addr)
            found_addrs.append(hex(addr))
        except Exception:
            pass
    print(f"Обнаруженные адреса на шине 0: {found_addrs}")
    if '0x44' in found_addrs:
        print("  [OK] SHT30 найден (адрес 0x44)")
    else:
        print("  [FAIL] SHT30 НЕ найден на 0x44")
        
    if '0x48' in found_addrs:
        print("  [OK] ADS1115 найден (адрес 0x48)")
    else:
        print("  [FAIL] ADS1115 НЕ найден на 0x48")
except Exception as e:
    print(f"  [FAIL] Ошибка I2C-0: {e}")

print("\\n--- 2. ОПРОС ДАТЧИКА SHT30 (Температура и влажность воздуха) ---")
try:
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.05)
    d = bus.read_i2c_block_data(0x44, 0x00, 6)
    t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
    rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
    print(f"  [OK] Температура воздуха: {t_c:.2f} °C")
    print(f"  [OK] Влажность воздуха:   {rh:.1f} %")
except Exception as e:
    print(f"  [FAIL] Ошибка чтения SHT30: {e}")

print("\\n--- 3. ОПРОС ДАТЧИКА ВЛАЖНОСТИ ПОЧВЫ (ADS1115, канал A0) ---")
try:
    # Config: Single-ended AIN0, FSR +-4.096V (gain 1), single-shot
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.05)
    c = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (c[0] << 8) | c[1]
    if raw > 32767:
        raw -= 65536
    v_soil = raw * 0.000125
    # Калибровка: воздух ~2.03V (0%), вода ~0.57V (100%)
    pct_soil = max(0.0, min(100.0, (2.03 - v_soil) / (2.03 - 0.57) * 100.0))
    print(f"  [OK] Raw ADC: {raw}")
    print(f"  [OK] Напряжение сенсора: {v_soil:.3f} В")
    print(f"  [OK] Расчетная влажность субстрата: {pct_soil:.1f} %")
except Exception as e:
    print(f"  [FAIL] Ошибка чтения ADS1115: {e}")

try:
    bus.close()
except Exception:
    pass

print("\\n--- 4. ТЕСТИРОВАНИЕ РЕЛЕ И СВЕТОДИОДОВ (Линии 4 и 7) ---")
try:
    settings = gpiod.LineSettings(
        direction=Direction.OUTPUT,
        active_low=True,
        output_value=Value.INACTIVE
    )
    req = gpiod.request_lines(
        '/dev/gpiochip1',
        consumer='hw_diag',
        config={(4,): settings, (7,): settings}
    )
    
    print("  -> Включение ИК 850 нм (Канал 1, GPIO 4) на 1.5 сек...")
    req.set_value(4, Value.ACTIVE)
    time.sleep(1.5)
    req.set_value(4, Value.INACTIVE)
    print("  [OK] Канал 1 отработал.")
    
    time.sleep(0.5)
    print("  -> Включение Red 660 нм (Канал 2, GPIO 7) на 1.5 сек...")
    req.set_value(7, Value.ACTIVE)
    time.sleep(1.5)
    req.set_value(7, Value.INACTIVE)
    print("  [OK] Канал 2 отработал.")
    
    time.sleep(0.5)
    print("  -> Синхронный строб (оба канала) 2 импульса...")
    for _ in range(2):
        req.set_value(4, Value.ACTIVE)
        req.set_value(7, Value.ACTIVE)
        time.sleep(0.3)
        req.set_value(4, Value.INACTIVE)
        req.set_value(7, Value.INACTIVE)
        time.sleep(0.3)
    print("  [OK] Стробирование реле завершено.")
    req.release()
except Exception as e:
    print(f"  [FAIL] Ошибка управления GPIO: {e}")

print("\\n--- 5. ТЕСТИРОВАНИЕ КАМЕРЫ (IMX179 NoIR) ---")
try:
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("  [FAIL] Камера /dev/video0 не открывается")
    else:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        time.sleep(0.5)
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            mean_b = frame[:, :, 0].mean()
            mean_g = frame[:, :, 1].mean()
            mean_r = frame[:, :, 2].mean()
            print(f"  [OK] Кадр успешно захвачен: {frame.shape[1]}x{frame.shape[0]} px")
            print(f"  [OK] Средняя яркость каналов: R={mean_r:.1f}, G={mean_g:.1f}, B={mean_b:.1f}")
        else:
            print("  [FAIL] Не удалось захватить кадр с сенсора камеры")
except Exception as e:
    print(f"  [FAIL] Ошибка камеры: {e}")
'''

    # Stop service temporarily to free GPIO
    print("[*] Временная остановка сервиса plant-station для освобождения GPIO...")
    ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
    time.sleep(1)

    sftp = ssh.open_sftp()
    with sftp.file('/home/pi/diag_script.py', 'w') as f:
        f.write(remote_code)
    sftp.close()

    print("[*] Выполнение аппаратной диагностики на Orange Pi...")
    stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/diag_script.py && rm /home/pi/diag_script.py')
    output = stdout.read().decode('utf-8', errors='replace')
    error = stderr.read().decode('utf-8', errors='replace')
    print(output)
    if error.strip():
        print("[STDERR]:", error)

    # Restart service
    print("[*] Перезапуск фонового сервиса plant-station...")
    ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
    
    ssh.close()
    print("=" * 65)
    print("  ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("=" * 65)

if __name__ == '__main__':
    main()
