import paramiko

ssh_r = paramiko.SSHClient()
ssh_r.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_r.connect('192.168.0.2', username='root', password='1', timeout=5)

alive_ips = ['192.168.0.3', '192.168.0.4', '192.168.0.5', '192.168.0.6', '192.168.0.8', 
             '192.168.0.9', '192.168.0.10', '192.168.0.11', '192.168.0.12', '192.168.0.21', 
             '192.168.0.36', '192.168.0.37']

for ip in alive_ips:
    cmd = f'nc -z -w 1 {ip} 22 && echo "SSH OPEN on {ip}" || echo "closed on {ip}"'
    stdin, stdout, stderr = ssh_r.exec_command(cmd)
    res = stdout.read().decode().strip()
    if "OPEN" in res:
        print(f"!!! {res} !!!")
    else:
        print(f"{ip}: {res}")

ssh_r.close()
