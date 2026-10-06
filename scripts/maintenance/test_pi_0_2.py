import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("Connecting to 192.168.0.2:22...")
    ssh.connect('192.168.0.2', username='pi', password='1', timeout=5)
    print("SUCCESSFULLY CONNECTED TO 192.168.0.2!")
    stdin, stdout, stderr = ssh.exec_command('uname -a && whoami')
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print("Failed to connect to 192.168.0.2:", e)
