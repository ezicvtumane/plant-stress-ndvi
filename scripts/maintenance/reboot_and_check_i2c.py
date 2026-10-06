import time
import socket
import paramiko

print("Initiating reboot on Orange Pi to load i2c0 overlay...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)
try:
    ssh.exec_command('echo 1 | sudo -S reboot', timeout=2)
except Exception:
    pass
ssh.close()

print("Reboot signal sent. Waiting for board to restart (20 seconds)...")
time.sleep(10)

# Poll until SSH is alive again
connected = False
for attempt in range(30):
    time.sleep(2)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    res = s.connect_ex(('192.168.0.23', 22))
    s.close()
    if res == 0:
        print(f"Port 22 is open on attempt {attempt+1}! Connecting SSH...")
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=4)
            connected = True
            break
        except Exception as e:
            print(f"SSH handshake waiting... ({e})")
            time.sleep(2)

if not connected:
    print("Error: Could not reconnect to board within timeout.")
    exit(1)

print("\n--- Board successfully rebooted! Checking I2C adapters ---")
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S i2cdetect -l')
print("i2cdetect -l:")
print(stdout.read().decode())

print("--- Checking i2c devices in dmesg ---")
stdin, stdout, stderr = ssh.exec_command('dmesg | grep -i i2c')
print(stdout.read().decode())

print("--- Scanning /dev/i2c-0 (Pins 3 and 5: PB3/PB2) ---")
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S i2cdetect -y -r 0')
print(stdout.read().decode())

ssh.close()
