import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to 192.168.0.23...")
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)

print("Uploading web_station.py...")
sftp = ssh.open_sftp()
sftp.put('web_station.py', '/home/pi/plant-stress-ndvi/web_station.py')
sftp.close()
print("SFTP transfer complete")

commands = [
    'python3 -m py_compile /home/pi/plant-stress-ndvi/web_station.py',
    'echo 1 | sudo -S systemctl restart plant-station.service',
    'sleep 2',
    'systemctl is-active plant-station.service',
    'curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/',
    'cd /home/pi/plant-stress-ndvi && git status -s'
]

for cmd in commands:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    print(f"CMD: {cmd}\nOUT: {out}\nERR: {err}\n" + "-"*40)

ssh.close()
