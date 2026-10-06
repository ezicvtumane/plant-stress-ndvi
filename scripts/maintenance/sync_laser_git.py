import os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)
sftp = ssh.open_sftp()

src_dir = r'C:\Users\Администратор\Documents\Лазерный_раскрой_бокса_210х210х297'
dest_dir = '/home/pi/plant-stress-ndvi/hardware/laser_cutting'

for f in os.listdir(src_dir):
    if f.endswith('.svg') or f.endswith('.py') or f.endswith('.png'):
        lp = os.path.join(src_dir, f)
        rp = f'{dest_dir}/{f}'
        sftp.put(lp, rp)
        print(f'Uploaded: {f}')
sftp.close()

cmd = 'cd /home/pi/plant-stress-ndvi && git add hardware/laser_cutting/* && git commit -m "fix: precision alignment of facade magnets, zero light gap shoe slots, and light-tight lid" && git push origin main'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
