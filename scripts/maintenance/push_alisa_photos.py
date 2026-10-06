import os
import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', port=22, username='pi', password='1', timeout=10)
sftp = ssh.open_sftp()

files_to_sync = [
    'README.md',
    'docs/ЛАБОРАТОРНЫЙ_ЖУРНАЛ_ИССЛЕДОВАНИЯ.md',
    'docs/images/alisa_hardware_assembly_quad.jpg',
    'docs/images/alisa_soldering_station_electronics.jpg',
    'docs/images/alisa_assembling_orangepi_case.jpg',
    'docs/images/alisa_calibrating_mini360_voltage.jpg',
    'docs/images/alisa_testing_circuits_multimeter.jpg'
]

base_local = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi'
base_remote = '/home/pi/plant-stress-ndvi'

for rel in files_to_sync:
    local_p = os.path.join(base_local, rel)
    remote_p = f'{base_remote}/{rel}'.replace('\\', '/')
    print(f'Uploading {rel}...')
    sftp.put(local_p, remote_p)

sftp.close()

commit_msg = (
    "docs(photos): add author hardware assembly photo documentation and quadtych\n\n"
    "- Add 4-photo collage alisa_hardware_assembly_quad.jpg documenting student hardware creation\n"
    "- Document soldering of lines with digital iron, Orange Pi heatsink case assembly, multimeter testing, and Mini-360 voltage calibration\n"
    "- Update README.md with Fig. 1 showcasing author physical build\n"
    "- Link photo proof in research lab journal (Oct 1-2 milestone)"
)

escaped_msg = commit_msg.replace('"', '\\"')

cmds = [
    'cd /home/pi/plant-stress-ndvi && git add README.md docs/ЛАБОРАТОРНЫЙ_ЖУРНАЛ_ИССЛЕДОВАНИЯ.md docs/images/alisa_*',
    f'cd /home/pi/plant-stress-ndvi && git commit -m "{escaped_msg}"',
    'cd /home/pi/plant-stress-ndvi && git push origin main',
    'cd /home/pi/plant-stress-ndvi && git log -n 2 --oneline'
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
