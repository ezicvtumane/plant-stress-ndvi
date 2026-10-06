import subprocess
import concurrent.futures

def ping(ip):
    subprocess.run(f"ping -n 1 -w 100 {ip}", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

ips = [f"192.168.1.{i}" for i in range(1, 255)]
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    list(executor.map(ping, ips))

out = subprocess.check_output("arp -a", shell=True).decode('cp866', errors='ignore')
print(out)
