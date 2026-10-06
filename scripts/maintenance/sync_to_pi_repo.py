import paramiko
import os

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)
sftp = ssh.open_sftp()

files_to_sync = [
    'README.md',
    'hardware/SCHEMATIC.md',
    'hardware/BOM.md',
    'docs/STEP_BY_STEP_ALGORITHM.md',
    'docs/SCIENTIFIC_PASSPORT.md',
    'docs/ЛАБОРАТОРНЫЙ_ЖУРНАЛ_ИССЛЕДОВАНИЯ.md',
    'docs/Схема_подключения_электроники_Orange_Pi.pdf',
    'docs/images/strobe_verification_collage.jpg',
    'web_station.py'
]

def ensure_remote_dir(remote_dir):
    parts = remote_dir.strip('/').split('/')
    cur = ''
    for p in parts:
        cur += '/' + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass

base_local = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi'
base_remote = '/home/pi/plant-stress-ndvi'

for rel in files_to_sync:
    local_p = os.path.join(base_local, rel)
    remote_p = f"{base_remote}/{rel}"
    if os.path.exists(local_p):
        remote_dir = os.path.dirname(remote_p)
        ensure_remote_dir(remote_dir)
        print(f"Uploading {rel}...")
        sftp.put(local_p, remote_p)
    else:
        print(f"Warning: {local_p} does not exist!")

sftp.close()

# Check git status
stdin, stdout, stderr = ssh.exec_command(f'cd {base_remote} && git status -s')
print("\nGit Status on Orange Pi:")
print(stdout.read().decode('utf-8', errors='ignore'))
ssh.close()
