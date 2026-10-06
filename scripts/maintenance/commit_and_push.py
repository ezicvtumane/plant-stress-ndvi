import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=10)

commit_msg = (
    "docs(hardware): update full documentation, schematics and web station for physical build\n\n"
    "- Update README.md with physical dual-band strobe (660nm + 850nm) and direct I2C-0 sensor telemetry\n"
    "- Document complete 40-pin GPIO pinout, Mini-360 calibration voltages (2.20V and 1.60V), and safety rules in hardware/SCHEMATIC.md\n"
    "- Add official PDF electrical schematic (docs/Схема_подключения_электроники_Orange_Pi.pdf)\n"
    "- Add optical strobe verification collage (docs/images/strobe_verification_collage.jpg)\n"
    "- Update BOM.md with Sensirion SHT30 (0x44) and ADS1115 (0x48) calibrations\n"
    "- Synchronize STEP_BY_STEP_ALGORITHM.md and SCIENTIFIC_PASSPORT.md with physical build\n"
    "- Record Oct 1-2 hardware integration milestone in research lab journal\n"
    "- Update web_station.py with direct I2C-0 hardware reads for SHT30 and ADS1115"
)

# Escape double quotes for shell
escaped_msg = commit_msg.replace('"', '\\"')

commands = [
    'cd /home/pi/plant-stress-ndvi && git config user.name "Alisa Kovaleva"',
    'cd /home/pi/plant-stress-ndvi && git config user.email "kovaleva.alisa@sirius2026.ru"',
    f'cd /home/pi/plant-stress-ndvi && git commit -m "{escaped_msg}"',
    'cd /home/pi/plant-stress-ndvi && git push origin main',
    'cd /home/pi/plant-stress-ndvi && git log -n 2 --oneline'
]

for cmd in commands:
    print(f"Executing: {cmd[:60]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    if out:
        print(f"OUT: {out}")
    if err:
        print(f"ERR: {err}")
    print("-" * 50)

ssh.close()
