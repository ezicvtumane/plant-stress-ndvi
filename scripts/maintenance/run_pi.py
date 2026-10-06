import paramiko
import sys

cmd = sys.argv[1] if len(sys.argv) > 1 else 'uptime'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')
print("STDOUT:\n" + out)
if err:
    print("STDERR:\n" + err)
ssh.close()
