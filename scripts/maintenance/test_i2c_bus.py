import sys
import time
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

print("=== 1. Тестирование шины I2C-0 (Сканирование) ===")
t0 = time.time()
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S i2cdetect -y 0')
res = stdout.read().decode()
dt = time.time() - t0
print(res)
print(f"Время сканирования: {dt:.3f} сек.")

print("\n=== 2. Проверка состояния адаптера I2C-0 ===")
stdin, stdout, stderr = ssh.exec_command('cat /sys/class/i2c-adapter/i2c-0/name')
print("Устройство:", stdout.read().decode().strip())

print("\n=== 3. Проверка dmesg на ошибки шины ===")
stdin, stdout, stderr = ssh.exec_command('dmesg | grep -i twi')
dmesg_out = stdout.read().decode().strip()
if dmesg_out:
    print(dmesg_out)
else:
    print("В dmesg чисто (нет сбоев, нет таймаутов, нет замыканий).")

ssh.close()
