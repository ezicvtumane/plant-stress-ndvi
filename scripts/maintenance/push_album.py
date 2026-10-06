import os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=15)
sftp = ssh.open_sftp()

local_root = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi'
remote_root = '/home/pi/plant-stress-ndvi'

files_to_sync = [
    'docs/PHOTO_ALBUM.md',
    'docs/ФОТОАЛЬБОМ_ПРОЕКТА.md',
    'docs/images/creality_3d_printer_case_printing.jpg',
    'docs/images/electronics_3d_printed_case_assembly.jpg'
]

for rel in files_to_sync:
    local_p = os.path.join(local_root, rel.replace('/', os.sep))
    remote_p = f'{remote_root}/{rel}'
    sftp.put(local_p, remote_p)
    print(f'Uploaded: {rel}')

sftp.close()

commit_msg = "docs(album): add 3d-printed electronics case and creality printing photos to project photo album"

cmds = [
    'cd /home/pi/plant-stress-ndvi && git add docs/PHOTO_ALBUM.md docs/ФОТОАЛЬБОМ_ПРОЕКТА.md docs/images/creality_* docs/images/electronics_*',
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
print("All photos synced and pushed to GitHub album successfully!")
