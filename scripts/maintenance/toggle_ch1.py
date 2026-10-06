import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

# Stop station service to release GPIO lines
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()

ch1_script = '''
import time
import gpiod
from gpiod.line import Direction, Value

print("=== ВКЛЮЧЕНИЕ ТОЛЬКО КАНАЛА №1 (Pin 7 / PL4) ===")

settings = gpiod.LineSettings(
    direction=Direction.OUTPUT,
    active_low=True,
    output_value=Value.INACTIVE
)

req = gpiod.request_lines(
    '/dev/gpiochip1',
    consumer='test_ch1',
    config={(4,): settings, (7,): settings}
)

# Убеждаемся, что Канал 2 строго ВЫКЛЮЧЕН
req.set_value(7, Value.INACTIVE)

print("-> Канал №1 ВКЛЮЧЕН на 4 секунды...")
req.set_value(4, Value.ACTIVE)
time.sleep(4.0)

print("-> Канал №1 ВЫКЛЮЧЕН на 1 секунду...")
req.set_value(4, Value.INACTIVE)
time.sleep(1.0)

print("-> Канал №1 снова ВКЛЮЧЕН на 2 секунды...")
req.set_value(4, Value.ACTIVE)
time.sleep(2.0)

req.set_value(4, Value.INACTIVE)
print("-> Канал №1 окончательно ВЫКЛЮЧЕН.")

req.release()
print("=== ТЕСТ КАНАЛА №1 ЗАВЕРШЕН ===")
'''

sftp = ssh.open_sftp()
with sftp.file('/home/pi/test_ch1.py', 'w') as f:
    f.write(ch1_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/test_ch1.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)

# Restart service
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
stdout.channel.recv_exit_status()

ssh.close()
