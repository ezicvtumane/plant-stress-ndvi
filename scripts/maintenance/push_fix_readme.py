import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)
sftp = ssh.open_sftp()

local_path = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\README.md'
remote_path = '/home/pi/plant-stress-ndvi/README.md'
print('Uploading README.md...')
sftp.put(local_path, remote_path)
sftp.close()

cmd = 'cd /home/pi/plant-stress-ndvi && git add README.md && git commit -m "fix(docs): fix Mermaid diagram syntax error in README.md" && git push origin main'
stdin, stdout, stderr = ssh.exec_command(cmd)
print('STDOUT:\n', stdout.read().decode('utf-8', errors='ignore'))
print('STDERR:\n', stderr.read().decode('utf-8', errors='ignore'))

ssh.close()
print('Finished!')
