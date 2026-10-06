import sys
import time
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

print("=== 1. Сканирование шины I2C-0 ===")
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S i2cdetect -y 0')
i2c_grid = stdout.read().decode()
print(i2c_grid)

# Python script to run ON Orange Pi to read SHT30 and ADS1115
remote_test_script = '''
import time
import smbus2

print("=== Чтение датчиков через smbus2 (I2C-0) ===")
bus = smbus2.SMBus(0)

# 1. Проверка SHT30 (0x44)
try:
    # Команда одиночного замера с высокой точностью: 0x2C 0x06
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.05)
    data = bus.read_i2c_block_data(0x44, 0x00, 6)
    temp_raw = (data[0] << 8) | data[1]
    temp_c = -45.0 + (175.0 * temp_raw / 65535.0)
    hum_raw = (data[3] << 8) | data[4]
    hum_pct = 100.0 * (hum_raw / 65535.0)
    print(f"[SHT30 @ 0x44] УСПЕХ!")
    print(f"   Температура воздуха: {temp_c:.2f} °C")
    print(f"   Влажность воздуха:   {hum_pct:.1f} %")
except Exception as e:
    print(f"[SHT30 @ 0x44] Ошибка чтения: {e}")

# 2. Проверка ADS1115 (0x48)
try:
    # Чтение регистра конфигурации (регистр 0x01)
    cfg = bus.read_i2c_block_data(0x48, 0x01, 2)
    # Запуск замера на канале A0: 0x84, 0x83 (OS=1, MUX=100 (AIN0-GND), PGA=2.048V, MODE=Single)
    bus.write_i2c_block_data(0x48, 0x01, [0xC2, 0x83])
    time.sleep(0.05)
    conv = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw_val = (conv[0] << 8) | conv[1]
    if raw_val > 32767:
        raw_val -= 65536
    # PGA 4.096V -> 1 bit = 0.125 mV (0.000125 V)
    volts = raw_val * 0.000125
    print(f"[ADS1115 @ 0x48] УСПЕХ!")
    print(f"   Сырой отсчет АЦП (A0): {raw_val}")
    print(f"   Напряжение на входе A0: {volts:.3f} В")
except Exception as e:
    print(f"[ADS1115 @ 0x48] Ошибка чтения: {e}")

bus.close()
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_sensors.py', 'w') as f:
    f.write(remote_test_script)
sftp.close()

print("=== 2. Опрос показаний чипов ===")
stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_sensors.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("Stderr:", err)

ssh.close()
