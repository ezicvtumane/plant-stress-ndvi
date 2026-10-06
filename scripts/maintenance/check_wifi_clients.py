import paramiko

ssh_r = paramiko.SSHClient()
ssh_r.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_r.connect('192.168.0.2', username='root', password='1', timeout=5)

cmd = '''
iw dev wlan0 station dump | grep Station
iw dev wlan1 station dump | grep Station
'''

stdin, stdout, stderr = ssh_r.exec_command(cmd)
print("Wi-Fi connected stations:")
print(stdout.read().decode())
ssh_r.close()
