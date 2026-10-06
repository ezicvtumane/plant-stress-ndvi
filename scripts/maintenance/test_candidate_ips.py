import paramiko

for ip in ['192.168.1.156', '192.168.1.160']:
    print(f"Testing {ip}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, username='pi', password='1', timeout=2)
        print(f"FOUND ORANGE PI ON {ip}!")
        stdin, stdout, stderr = ssh.exec_command('lsusb && v4l2-ctl --list-devices')
        print(stdout.read().decode())
        ssh.close()
        break
    except Exception as e:
        print(f"Failed {ip}: {e}")
