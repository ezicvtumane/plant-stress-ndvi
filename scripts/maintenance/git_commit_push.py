import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=30)

commit_msg = "feat(hardware): finalize 210x210x297 enclosure specs, clean finger-joint cuts, magnetic facade and doc updates"

cmds = [
    f'cd /home/pi/plant-stress-ndvi && git commit -m "{commit_msg}"',
    'cd /home/pi/plant-stress-ndvi && git push origin main'
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("ERR/PROGRESS:", err)

ssh.close()
print("Git commit & push complete!")
