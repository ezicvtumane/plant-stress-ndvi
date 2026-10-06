import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=10)

commit_msg = (
    "docs: comprehensive documentation update for physical assembly and sequential strobe\n\n"
    "- Document unified single 5V 3A Type-C power topology (Pin 2 and Pin 4 powering Mini-360 converters directly)\n"
    "- Detail authentic sequential 3-frame hardware protocol (Ambient -> Red solo -> 0.20s pause -> NIR solo -> differential NDVI) with 4 mechanical clicks\n"
    "- Add electronics junction box (IP54/IP65) layout and thermal isolation rule for Sensirion SHT30 at canopy level\n"
    "- Add dark room 3-frame strobe verification quadtych to README.md\n"
    "- Add Questions 14, 15, 16 to jury Q&A document (hardware vs software NIR, single power stability, SHT30 thermal barrier)\n"
    "- Synchronize BOM, Scientific Passport, Step-by-Step Algorithm, Lab Journal, 7-Minute Defense Speech, and Report Abstract"
)

escaped_msg = commit_msg.replace('"', '\\"')

cmds = [
    'cd /home/pi/plant-stress-ndvi && git add README.md hardware/ docs/',
    f'cd /home/pi/plant-stress-ndvi && git commit -m "{escaped_msg}"',
    'cd /home/pi/plant-stress-ndvi && git push origin main',
    'cd /home/pi/plant-stress-ndvi && git log -n 3 --oneline'
]

for cmd in cmds:
    print(f"Executing: {cmd[:60]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    if out:
        print(f"OUT: {out}")
    if err:
        print(f"ERR: {err}")
    print("=" * 50)

ssh.close()
