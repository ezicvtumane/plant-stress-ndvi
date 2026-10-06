import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=5)

cmds = [
    'lsusb',
    'v4l2-ctl --list-devices',
    'v4l2-ctl -d /dev/video0 --all',
    'udevadm info /dev/video0',
    'dmesg | grep -i uvc'
]

for cmd in cmds:
    print('=== CMD:', cmd, '===')
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    print(out)
    if err:
        print('ERR:', err)

ssh.close()
