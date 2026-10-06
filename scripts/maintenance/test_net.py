import socket

try:
    ip = socket.gethostbyname("orangepi4pro.local")
    print("orangepi4pro.local resolved to:", ip)
except Exception as e:
    print("mDNS resolution failed:", e)

# Also test 192.168.0.23 with longer timeout
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2.0)
try:
    s.connect(("192.168.0.23", 22))
    print("Connected to 192.168.0.23:22 successfully!")
    s.close()
except Exception as e:
    print("192.168.0.23:22 failed:", e)
