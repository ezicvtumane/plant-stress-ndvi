import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

remote_code = '''import smbus2, time

bus = smbus2.SMBus(0)

# SHT30
try:
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.05)
    d = bus.read_i2c_block_data(0x44, 0x00, 6)
    t_c = -45.0 + (175.0 * ((d[0] << 8) | d[1]) / 65535.0)
    rh = 100.0 * (((d[3] << 8) | d[4]) / 65535.0)
    print(f"[SHT30] T={t_c:.2f} °C, RH={rh:.1f} %")
except Exception as e:
    print("[SHT30 ERR]:", e)

# ADS1115
try:
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.05)
    c = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (c[0] << 8) | c[1]
    if raw > 32767: raw -= 65536
    v_soil = raw * 0.000125
    pct_soil = max(0.0, min(100.0, (2.03 - v_soil) / (2.03 - 0.57) * 100.0))
    print(f"[ADS1115 A0] Raw={raw}, V={v_soil:.3f} V, Soil={pct_soil:.1f} %")
except Exception as e:
    print("[ADS1115 ERR]:", e)

bus.close()
'''

sftp = ssh.open_sftp()
with sftp.file('/home/pi/test_sensors_tmp.py', 'w') as f:
    f.write(remote_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/test_sensors_tmp.py && rm /home/pi/test_sensors_tmp.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err: print('ERR:', err)

# Also run i2cdetect -y 0
stdin, stdout, stderr = ssh.exec_command('i2cdetect -y 0')
print("i2cdetect -y 0:")
print(stdout.read().decode())

ssh.close()
