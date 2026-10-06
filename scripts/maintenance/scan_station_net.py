import socket
import concurrent.futures

def scan_target(target):
    ip, port = target
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.8)
    try:
        s.connect((ip, port))
        s.close()
        return (ip, port)
    except Exception:
        s.close()
        return None

# Generate targets for 192.168.1.x and 192.168.0.x on ports 22 and 8000
targets = []
for i in range(1, 255):
    targets.append((f"192.168.1.{i}", 22))
    targets.append((f"192.168.1.{i}", 8000))
    targets.append((f"192.168.0.{i}", 22))
    targets.append((f"192.168.0.{i}", 8000))

print(f"Scanning {len(targets)} targets...")
found = []
with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
    results = executor.map(scan_target, targets)
    for res in results:
        if res:
            found.append(res)
            print("FOUND OPEN PORT:", res)

print("Scan complete. All found:", found)
