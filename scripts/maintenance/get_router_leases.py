import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.2', username='root', password='1', timeout=5)

cmds = [
    'cat /tmp/dhcp.leases',
    'cat /proc/net/arp',
    'ip neigh'
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())

ssh.close()
