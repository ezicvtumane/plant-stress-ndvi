import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

live_a0 = '''
import time
import smbus2

bus = smbus2.SMBus(0)
print("=== Мониторинг входа A0 (датчик почвы) на 25 секунд ===")
print("Попробуйте перевернуть разъём или прикоснуться пальцем к лезвию датчика:")

start = time.time()
while time.time() - start < 25:
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.04)
    conv = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (conv[0] << 8) | conv[1]
    if raw > 32767:
        raw -= 65536
    volts = raw * 0.000125
    print(f"[{time.strftime('%H:%M:%S')}] A0: raw = {raw:5d} | Напряжение = {volts:.3f} В")
    time.sleep(0.5)

bus.close()
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/live_a0.py', 'w') as f:
    f.write(live_a0)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/live_a0.py')
print(stdout.read().decode())
ssh.close()
