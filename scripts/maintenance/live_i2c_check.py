import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

live_script = '''
import time
import smbus2

bus = smbus2.SMBus(0)
print("=== Запущен живой монитор I2C-0 (15 секунд) ===")
print("Шевелите провода / контакты, сканер опрашивает шину каждые 0.5 сек...")

start_t = time.time()
last_found = set()
while time.time() - start_t < 15:
    found = set()
    for addr in range(0x08, 0x78):
        try:
            bus.write_quick(addr)
            found.add(hex(addr))
        except Exception:
            pass
    if found != last_found:
        print(f"[{time.strftime('%H:%M:%S')}] Обнаружены устройства: {list(found) if found else 'НЕТ (все прочерки)'}")
        last_found = found
    time.sleep(0.4)

bus.close()
print("Мониторинг завершен.")
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/live_i2c.py', 'w') as f:
    f.write(live_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/live_i2c.py')
print(stdout.read().decode())
ssh.close()
