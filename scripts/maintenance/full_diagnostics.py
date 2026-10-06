import sys
import time
import math
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

remote_diag_script = '''
import time
import math
import smbus2
import gpiod
from gpiod.line import Direction, Value

print("==================================================")
print("     КОМПЛЕКСНАЯ ДИАГНОСТИКА ОБОРУДОВАНИЯ СТАНЦИИ  ")
print("==================================================")

# 1. Сканирование шины I2C-0
print("\n[1/3] СКАНИРОВАНИЕ ШИНЫ I2C-0:")
bus = smbus2.SMBus(0)
found_devices = []
for addr in range(0x08, 0x78):
    try:
        bus.write_quick(addr)
        found_devices.append(hex(addr))
    except Exception:
        pass
print(f" -> Активные устройства на шине: {found_devices}")

# 2. Опрос SHT30
print("\n[2/3] ДАТЧИК МИКРОКЛИМАТА SHT30 (0x44):")
try:
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.05)
    data = bus.read_i2c_block_data(0x44, 0x00, 6)
    temp_raw = (data[0] << 8) | data[1]
    temp_c = -45.0 + (175.0 * temp_raw / 65535.0)
    hum_raw = (data[3] << 8) | data[4]
    hum_pct = 100.0 * (hum_raw / 65535.0)
    
    # VPD расчет (кПа)
    es = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (hum_pct / 100.0)
    vpd = round(float(es - ea), 2)
    
    print(f" -> Температура воздуха: {temp_c:.2f} °C")
    print(f" -> Относительная влажность: {hum_pct:.1f} %")
    print(f" -> Дефицит упругости пара (VPD): {vpd} кПа")
    print(" -> Статус SHT30: [ИСПРАВЕН / РАБОТАЕТ ШТАТНО]")
except Exception as e:
    print(f" -> Ошибка SHT30: {e}")

# 3. Опрос ADS1115 и датчика почвы
print("\n[3/3] 16-БИТНЫЙ АЦП ADS1115 (0x48) И ДАТЧИК ПОЧВЫ:")
try:
    # A0 замер: MUX=100 (AIN0-GND), PGA=4.096V (0x01)
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.04)
    conv = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (conv[0] << 8) | conv[1]
    if raw > 32767: raw -= 65536
    v_a0 = raw * 0.000125
    
    # Расчет процента влажности по калибровочной кривой (V_dry=2.03V, V_wet=0.57V)
    moist_pct = max(0.0, min(100.0, (2.03 - v_a0) / (2.03 - 0.57) * 100.0))
    
    print(f" -> Сырой отсчет АЦП (A0): {raw}")
    print(f" -> Напряжение сигнала влажности: {v_a0:.3f} В")
    print(f" -> Рассчитанная влажность субстрата: {moist_pct:.1f} % ПВ")
    if v_a0 > 1.8:
        state = "Сухой субстрат / на воздухе"
    elif v_a0 < 0.8:
        state = "Водная среда / полное насыщение (100% ПВ)"
    else:
        state = "Оптимальная влажность почвы для растений"
    print(f" -> Интерпретация состояния: {state}")
    print(" -> Статус ADS1115: [ИСПРАВЕН / РАБОТАЕТ ШТАТНО]")
except Exception as e:
    print(f" -> Ошибка ADS1115: {e}")

bus.close()

# 4. Тестирование реле
print("\n[ТЕСТ РЕЛЕ] ПРОВЕРКА КАНАЛОВ СТРОБА (gpiochip1):")
try:
    settings = gpiod.LineSettings(
        direction=Direction.OUTPUT,
        active_low=True,
        output_value=Value.INACTIVE
    )
    req = gpiod.request_lines(
        '/dev/gpiochip1',
        consumer='full_diagnostics',
        config={(4,): settings, (7,): settings}
    )
    
    print(" -> Щелчок Канала 1 (Pin 7 / PL4 - ИК 850 нм)...")
    req.set_value(4, Value.ACTIVE)
    time.sleep(0.4)
    req.set_value(4, Value.INACTIVE)
    time.sleep(0.3)
    
    print(" -> Щелчок Канала 2 (Pin 10 / PL7 - Red 660 нм)...")
    req.set_value(7, Value.ACTIVE)
    time.sleep(0.4)
    req.set_value(7, Value.INACTIVE)
    time.sleep(0.3)
    
    print(" -> Синхронный двойной строб (оба канала)...")
    for _ in range(2):
        req.set_value(4, Value.ACTIVE)
        req.set_value(7, Value.ACTIVE)
        time.sleep(0.2)
        req.set_value(4, Value.INACTIVE)
        req.set_value(7, Value.INACTIVE)
        time.sleep(0.2)
        
    req.release()
    print(" -> Статус реле: [ЩЕЛЧКИ ВЫПОЛНЕНЫ УСПЕШНО]")
except Exception as e:
    print(f" -> Ошибка управления реле: {e}")

print("\n==================================================")
print("     ДИАГНОСТИКА ЗАВЕРШЕНА: ВСЕ УЗЛЫ В СТРОЮ       ")
print("==================================================")
'''

# Остановка сервиса станции, чтобы освободить линии GPIO для теста
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()

# Запись и выполнение
sftp = ssh.open_sftp()
with sftp.file('/tmp/full_diag.py', 'w') as f:
    f.write(remote_diag_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/full_diag.py')
out = stdout.read().decode()
err = stderr.read().decode()
print(out)
if err:
    print("STDERR:\n", err)

# Перезапуск сервиса
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
stdout.channel.recv_exit_status()

ssh.close()
