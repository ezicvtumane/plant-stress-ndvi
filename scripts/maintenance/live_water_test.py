import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

live_a0_water = '''
import time
import smbus2

bus = smbus2.SMBus(0)
print("=== Живой монитор датчика почвы (90 секунд) ===")
print("Опустите кончик лезвия на 2-3 см в воду (или сожмите пальцами):")

start = time.time()
while time.time() - start < 90:
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.04)
    conv = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (conv[0] << 8) | conv[1]
    if raw > 32767:
        raw -= 65536
    volts = raw * 0.000125
    
    status = "СУХОЙ ВОЗДУХ"
    if volts < 2.2:
        status = "ВЛАЖНО / ВОДА! 💧"
    
    print(f"[{time.strftime('%H:%M:%S')}] A0: raw = {raw:5d} | {volts:.3f} В  --> {status}")
    time.sleep(0.8)

bus.close()
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/live_water.py', 'w') as f:
    f.write(live_a0_water)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/live_water.py')
print(stdout.read().decode())
ssh.close()
