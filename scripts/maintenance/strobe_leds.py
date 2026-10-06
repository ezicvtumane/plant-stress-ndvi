import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

# Stop station service to release GPIO lines
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()

strobe_script = '''
import time
import gpiod
from gpiod.line import Direction, Value

print("=== ЗАПУСК ПРОВЕРКИ СВЕТОДИОДОВ И РЕЛЕ ===")

settings = gpiod.LineSettings(
    direction=Direction.OUTPUT,
    active_low=True,
    output_value=Value.INACTIVE
)

req = gpiod.request_lines(
    '/dev/gpiochip1',
    consumer='led_strobe_test',
    config={(4,): settings, (7,): settings}
)

print("\\n1. Включение Канала 1 (ИК 850 нм) на 2 секунды...")
print("   -> СМОТРИТЕ НА ИК СВЕТОДИОД (глазом или через камеру смартфона)!")
req.set_value(4, Value.ACTIVE)
time.sleep(2.0)
req.set_value(4, Value.INACTIVE)
print("   -> Канал 1 выключен.")

time.sleep(1.0)

print("\\n2. Включение Канала 2 (Красный 660 нм) на 2 секунды...")
print("   -> СМОТРИТЕ НА КРАСНЫЙ СВЕТОДИОД!")
req.set_value(7, Value.ACTIVE)
time.sleep(2.0)
req.set_value(7, Value.INACTIVE)
print("   -> Канал 2 выключен.")

time.sleep(1.0)

print("\\n3. Серия синхронных вспышек (3 строба по 0.4 сек)...")
for i in range(3):
    print(f"   -> Строб {i+1}...")
    req.set_value(4, Value.ACTIVE)
    req.set_value(7, Value.ACTIVE)
    time.sleep(0.4)
    req.set_value(4, Value.INACTIVE)
    req.set_value(7, Value.INACTIVE)
    time.sleep(0.4)

req.release()
print("\\n=== ТЕСТ СВЕТОДИОДОВ ЗАВЕРШЕН УСПЕШНО ===")
'''

sftp = ssh.open_sftp()
with sftp.file('/home/pi/test_leds.py', 'w') as f:
    f.write(strobe_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/test_leds.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)

# Restart service
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
stdout.channel.recv_exit_status()

ssh.close()
