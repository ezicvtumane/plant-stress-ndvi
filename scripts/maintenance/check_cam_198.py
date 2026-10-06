import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('198.18.0.164', username='pi', password='1', timeout=5)
    print("SUCCESSFULLY CONNECTED TO ORANGE PI via 198.18.0.164!")
    
    cmds = [
        'lsusb',
        'v4l2-ctl --list-devices',
        'v4l2-ctl -d /dev/video0 --all',
        'dmesg | grep -i -E "camera|imx|video|uvc"'
    ]
    for cmd in cmds:
        print(f"\n=== CMD: {cmd} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode('utf-8', errors='ignore'))
        err = stderr.read().decode('utf-8', errors='ignore')
        if err:
            print("STDERR:", err)
    ssh.close()
except Exception as e:
    print("SSH Connection failed:", e)
