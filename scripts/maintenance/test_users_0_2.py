import paramiko

for user, pwd in [('orangepi', 'orangepi'), ('root', '1'), ('pi', 'orangepi'), ('root', 'orangepi')]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('192.168.0.2', username=user, password=pwd, timeout=3)
        print(f"SUCCESS with {user}:{pwd} on 192.168.0.2!")
        stdin, stdout, stderr = ssh.exec_command('uname -a')
        print(stdout.read().decode())
        ssh.close()
        break
    except Exception as e:
        print(f"Failed {user}:{pwd}: {e}")
