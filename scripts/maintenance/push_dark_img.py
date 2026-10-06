import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=10)

sftp = ssh.open_sftp()
sftp.put(
    r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\docs\images\dark_room_strobe_verification.jpg',
    '/home/pi/plant-stress-ndvi/docs/images/dark_room_strobe_verification.jpg'
)
sftp.close()

msg = "docs(images): add dark room 3-frame strobe verification quadtych"
stdin, stdout, stderr = ssh.exec_command(f'cd /home/pi/plant-stress-ndvi && git add docs/images/dark_room_strobe_verification.jpg && git commit -m "{msg}" && git push origin main')
print(stdout.read().decode())
err = stderr.read().decode()
if err: print('ERR:', err)
ssh.close()
