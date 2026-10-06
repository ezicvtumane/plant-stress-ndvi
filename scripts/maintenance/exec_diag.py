import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

# Stop station service to release GPIO lines
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()

# Upload and run remote script
sftp = ssh.open_sftp()
with sftp.file('/home/pi/run_diag.py', 'w') as f:
    f.write('''import time
import math
import smbus2
import gpiod
from gpiod.line import Direction, Value

print("=== 1. SKANIROVANIE SHINY I2C-0 ===")
bus = smbus2.SMBus(0)
devs = []
for a in range(8, 120):
    try:
        bus.write_quick(a)
        devs.append(hex(a))
    except Exception:
        pass
print(f"Ustroystva na spine: {devs}")

print("\\n=== 2. DATChIK MIKROKLIMATA SHT30 ===")
try:
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.05)
    d = bus.read_i2c_block_data(0x44, 0x00, 6)
    t_raw = (d[0] << 8) | d[1]
    tc = -45.0 + (175.0 * t_raw / 65535.0)
    h_raw = (d[3] << 8) | d[4]
    rh = 100.0 * (h_raw / 65535.0)
    es = 0.61078 * math.exp((17.27 * tc) / (tc + 237.3))
    ea = es * (rh / 100.0)
    vpd = round(float(es - ea), 2)
    print(f"Temperatura: {tc:.2f} C")
    print(f"Vlazhnost:   {rh:.1f} %")
    print(f"VPD:         {vpd} kPa")
except Exception as e:
    print(f"Oshibka SHT30: {e}")

print("\\n=== 3. ACР ADS1115 I DATChIK POChVY ===")
try:
    bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
    time.sleep(0.04)
    c = bus.read_i2c_block_data(0x48, 0x00, 2)
    raw = (c[0] << 8) | c[1]
    if raw > 32767: raw -= 65536
    v = raw * 0.000125
    moist = max(0.0, min(100.0, (2.03 - v) / (2.03 - 0.57) * 100.0))
    print(f"Otschet A0:       {raw}")
    print(f"Napryazhenie A0:  {v:.3f} V")
    print(f"Vlazhnost pochvy: {moist:.1f} %")
except Exception as e:
    print(f"Oshibka ADS1115: {e}")

bus.close()

print("\\n=== 4. TEST RELE (SHTROB) ===")
try:
    st = gpiod.LineSettings(direction=Direction.OUTPUT, active_low=True, output_value=Value.INACTIVE)
    req = gpiod.request_lines('/dev/gpiochip1', consumer='diag', config={(4,): st, (7,): st})
    print("-> Vklyuchenie Kanala 1 (850 nm NIR)...")
    req.set_value(4, Value.ACTIVE)
    time.sleep(0.4)
    req.set_value(4, Value.INACTIVE)
    time.sleep(0.2)
    print("-> Vklyuchenie Kanala 2 (660 nm Red)...")
    req.set_value(7, Value.ACTIVE)
    time.sleep(0.4)
    req.set_value(7, Value.INACTIVE)
    time.sleep(0.2)
    print("-> Dvoynoy sinkhronny shtrob...")
    for _ in range(2):
        req.set_value(4, Value.ACTIVE)
        req.set_value(7, Value.ACTIVE)
        time.sleep(0.2)
        req.set_value(4, Value.INACTIVE)
        req.set_value(7, Value.INACTIVE)
        time.sleep(0.2)
    req.release()
    print("-> Rele: OTRABOTALO USPEShNO!")
except Exception as e:
    print(f"Oshibka rele: {e}")
''')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/run_diag.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)

# Restart service
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
stdout.channel.recv_exit_status()

ssh.close()
