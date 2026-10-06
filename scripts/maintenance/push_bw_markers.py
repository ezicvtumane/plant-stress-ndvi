import os, paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)
sftp = ssh.open_sftp()

local_root = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi'
files = [
    'scripts/generators/generate_aruco_sheet.py',
    'static/aruco/aruco_1.png',
    'static/aruco/aruco_2.png',
    'static/aruco/aruco_3.png',
    'static/aruco/aruco_4.png',
    'static/aruco/aruco_5.png',
    'static/aruco_markers_sheet.html',
    'static/aruco_markers_sheet.pdf',
    'docs/aruco_markers_sheet.html',
    'docs/aruco_markers_sheet.pdf',
]

for rel in files:
    lp = os.path.join(local_root, rel.replace('/', os.sep))
    rp = '/home/pi/plant-stress-ndvi/' + rel
    sftp.put(lp, rp)

sftp.close()

stdin, stdout, stderr = ssh.exec_command('cd /home/pi/plant-stress-ndvi && git add -A && git commit -m "feat(aruco): update markers sheet to monochrome outline design for BW printing" && git push origin main')
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))
ssh.close()
print("Synced and pushed successfully!")
