import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/ | grep -A 25 "climate-bar"')
print(stdout.read().decode())
ssh.close()
