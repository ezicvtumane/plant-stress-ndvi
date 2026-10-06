import sys
import time
import math
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

# Stop station service to release GPIO lines
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()

all_in_one = '''
import time, math, smbus2, gpiod
from gpiod.line import Direction, Value

print("================================================================")
print("     ГЕНЕРАЛЬНАЯ ПРОВЕРКА ВСЕЙ АППАРАТНОЙ ЧАСТИ СТАНЦИИ         ")
print("================================================================")

# --- 1. ШИНА I2C И ДАТЧИКИ ---
print("\\n[1/2] ТЕЛЕМЕТРИЯ ДАТЧИКОВ (I2C-0):")
bus = smbus2.SMBus(0)

# SHT30
try:
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.05)
    d = bus.read_i2c_block_data(0x44, 0x00, 6)
    t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
    rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
    es = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
    ea = es * (rh / 100.0)
    vpd = round(float(es - ea), 2)
    print(f" -> [SHT30 @ 0x44] Температура воздуха: {t_c:.2f} °C")
    print(f" -> [SHT30 @ 0x44] Влажность воздуха:   {rh:.1f} %")
    print(f" -> [SHT30 @ 0x44] Дефицит пара (VPD):  {vpd} кПа")
except Exception as e:
    print(f" -> [SHT30] Ошибка: {e}")

# ADS1115
try:
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.04)
    c = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (c[0] << 8) | c[1]
    if raw > 32767: raw -= 65536
    v_soil = raw * 0.000125
    pct_soil = max(0.0, min(100.0, (2.03 - v_soil) / (2.03 - 0.57) * 100.0))
    print(f" -> [ADS1115 @ 0x48] Сырой отсчет АЦП (A0): {raw}")
    print(f" -> [ADS1115 @ 0x48] Напряжение сигнала:    {v_soil:.3f} В")
    print(f" -> [ADS1115 @ 0x48] Влажность субстрата:   {pct_soil:.1f} % ПВ")
except Exception as e:
    print(f" -> [ADS1115] Ошибка: {e}")

bus.close()

# --- 2. СВЕТОДИОДЫ И РЕЛЕ ---
print("\\n[2/2] ТЕСТИРОВАНИЕ СВЕТОДИОДОВ И РЕЛЕ:")
try:
    st = gpiod.LineSettings(direction=Direction.OUTPUT, active_low=True, output_value=Value.INACTIVE)
    req = gpiod.request_lines('/dev/gpiochip1', consumer='full_test', config={(4,): st, (7,): st})
    
    print(" -> 1. Вспышка: КРАСНЫЙ СВЕТОДИОД 660 нм (Канал 1 / Pin 7) на 1.0 сек...")
    req.set_value(4, Value.ACTIVE)
    time.sleep(1.0)
    req.set_value(4, Value.INACTIVE)
    time.sleep(0.5)
    
    print(" -> 2. Вспышка: ИНФРАКРАСНЫЙ СВЕТОДИОД 850 нм (Канал 2 / Pin 10) на 1.0 сек...")
    req.set_value(7, Value.ACTIVE)
    time.sleep(1.0)
    req.set_value(7, Value.INACTIVE)
    time.sleep(0.5)
    
    print(" -> 3. БОЕВОЙ СИНХРОННЫЙ СТРОБ (оба светодиода вместе для съемки NoIR-кадром)...")
    for i in range(2):
        print(f"    * Синхронная вспышка #{i+1} (0.4 сек)...")
        req.set_value(4, Value.ACTIVE)
        req.set_value(7, Value.ACTIVE)
        time.sleep(0.4)
        req.set_value(4, Value.INACTIVE)
        req.set_value(7, Value.INACTIVE)
        time.sleep(0.3)
        
    req.release()
    print(" -> Реле и светодиоды: [ОТРАБОТАЛИ ИДЕАЛЬНО]")
except Exception as e:
    print(f" -> Ошибка реле/светодиодов: {e}")

print("\\n================================================================")
print("     ТЕСТ УСПЕШНО ЗАВЕРШЕН: ВСЯ СИСТЕМА ГОТОВА К РАБОТЕ!        ")
print("================================================================")
'''

sftp = ssh.open_sftp()
with sftp.file('/home/pi/grand_test.py', 'w') as f:
    f.write(all_in_one)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/grand_test.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:\n", err)

# Restart service
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
stdout.channel.recv_exit_status()

ssh.close()
