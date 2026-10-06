import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

stdin, stdout, stderr = ssh.exec_command('curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:8000/ && journalctl -u plant-station -n 25 --no-pager')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
