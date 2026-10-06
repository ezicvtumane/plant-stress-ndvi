import sys
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=10)

msg = "feat(capture): implement true sequential 3-frame hardware protocol with separate relay clicks"
stdin, stdout, stderr = ssh.exec_command(f'cd /home/pi/plant-stress-ndvi && git add web_station.py && git commit -m "{msg}" && git push origin main')
print(stdout.read().decode())
err = stderr.read().decode()
if err: print('ERR:', err)
ssh.close()
