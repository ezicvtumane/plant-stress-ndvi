import paramiko

ssh_r = paramiko.SSHClient()
ssh_r.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_r.connect('192.168.0.2', username='root', password='1', timeout=5)

cmd = '''
logread | grep -i -E "orangepi|192.168.0.23|dhcp" | tail -n 30
'''

stdin, stdout, stderr = ssh_r.exec_command(cmd)
print(stdout.read().decode())
ssh_r.close()
