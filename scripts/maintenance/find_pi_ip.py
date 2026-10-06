import socket
import concurrent.futures

def check_ip(ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((ip, 22))
        s.close()
        return ip
    except Exception:
        s.close()
        return None

base = "192.168.1."
ips = [f"{base}{i}" for i in range(2, 255)]

print("Scanning 192.168.1.0/24 for SSH port 22...")
found = []
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    results = executor.map(check_ip, ips)
    for res in results:
        if res:
            found.append(res)
            print("Found SSH on:", res)

print("Scan complete. Found:", found)
