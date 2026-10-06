import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=5)

# Read armbianEnv.txt
stdin, stdout, stderr = ssh.exec_command('cat /boot/armbianEnv.txt')
content = stdout.read().decode()
print("Original armbianEnv.txt:")
print(content)

lines = [line.strip() for line in content.splitlines() if line.strip()]
has_overlays = False
new_lines = []
for line in lines:
    if line.startswith('overlays='):
        new_lines.append('overlays=i2c0')
        has_overlays = True
    else:
        new_lines.append(line)

if not has_overlays:
    new_lines.append('overlays=i2c0')

new_content = '\n'.join(new_lines) + '\n'

print("New content to write:")
print(new_content)

# Backup and write
sftp = ssh.open_sftp()
with sftp.file('/tmp/armbianEnv.txt', 'w') as f:
    f.write(new_content)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S cp /tmp/armbianEnv.txt /boot/armbianEnv.txt')
stdout.channel.recv_exit_status()

stdin, stdout, stderr = ssh.exec_command('cat /boot/armbianEnv.txt')
print("Verified /boot/armbianEnv.txt:")
print(stdout.read().decode())

ssh.close()
