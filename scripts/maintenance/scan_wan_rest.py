import paramiko

ssh_r = paramiko.SSHClient()
ssh_r.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_r.connect('192.168.0.2', username='root', password='1', timeout=5)

cmd = '''
for i in $(seq 41 254); do
    ping -c 1 -W 1 192.168.0.$i > /dev/null 2>&1 &
done
wait
cat /proc/net/arp | grep wan | grep -v "00:00:00:00:00:00"
'''

stdin, stdout, stderr = ssh_r.exec_command(cmd)
print(stdout.read().decode())
ssh_r.close()
