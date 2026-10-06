import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.2', username='root', password='1', timeout=5)

cmd = '''
for i in $(seq 1 40); do
    ping -c 1 -W 1 192.168.0.$i > /dev/null 2>&1 &
done
wait
cat /proc/net/arp | grep wan
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
ssh.close()
