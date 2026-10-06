import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

code = '''import gpiod, time
from gpiod.line import Direction, Value

settings = gpiod.LineSettings(direction=Direction.OUTPUT, active_low=True, output_value=Value.INACTIVE)
req = gpiod.request_lines('/dev/gpiochip1', consumer='test_nir_solo', config={(7,): settings})

print(">>> Включаем ТОЛЬКО ИК-светодиод 850 нм (Канал 2 / Pin 10) на 3.0 секунды...")
req.set_value(7, Value.ACTIVE)
time.sleep(3.0)
print(">>> Выключаем ИК-светодиод 850 нм...")
req.set_value(7, Value.INACTIVE)
time.sleep(0.5)

# Двойной проверочный щелчок
print(">>> Двойной щелчок ИК-реле...")
for i in range(2):
    req.set_value(7, Value.ACTIVE)
    time.sleep(0.3)
    req.set_value(7, Value.INACTIVE)
    time.sleep(0.3)

req.release()
print(">>> Тест канала 2 завершен.")
'''

# Stop station to release GPIO
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()
import time
time.sleep(1)

sftp = ssh.open_sftp()
with sftp.file('/home/pi/test_nir.py', 'w') as f:
    f.write(code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/test_nir.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err: print('ERR:', err)

# Restart plant station
ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
ssh.close()
