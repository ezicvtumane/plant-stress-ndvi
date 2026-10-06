import paramiko
import cv2
import numpy as np
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.23', username='pi', password='1', timeout=10)

# Stop station briefly to take full manual control of GPIO and Camera
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl stop plant-station')
stdout.channel.recv_exit_status()

remote_code = '''import time, cv2, gpiod
from gpiod.line import Direction, Value

settings = gpiod.LineSettings(direction=Direction.OUTPUT, active_low=True, output_value=Value.INACTIVE)
req = gpiod.request_lines('/dev/gpiochip1', consumer='nir_test', config={(4,): settings, (7,): settings})

# Ensure both OFF
req.set_value(4, Value.INACTIVE)
req.set_value(7, Value.INACTIVE)
time.sleep(0.5)

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1600)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1200)

for _ in range(5): cap.read()
_, frame_off = cap.read()
cv2.imwrite('/home/pi/plant-stress-ndvi/static/test_nir_off.jpg', frame_off)

# TURN ON NIR ONLY (Pin 10 / line 7) for 1.2 seconds
print('TURNING ON NIR LED (Pin 10 / line 7)...')
req.set_value(7, Value.ACTIVE)
time.sleep(0.8) # allow full camera adaptation

for _ in range(5): cap.read()
_, frame_on = cap.read()
cv2.imwrite('/home/pi/plant-stress-ndvi/static/test_nir_on.jpg', frame_on)

req.set_value(7, Value.INACTIVE)
print('TURNING OFF NIR LED...')
cap.release()
del req
'''

sftp = ssh.open_sftp()
with sftp.file('/home/pi/test_nir_isolated.py', 'w') as f:
    f.write(remote_code)

stdin, stdout, stderr = ssh.exec_command('python3 /home/pi/test_nir_isolated.py')
out = stdout.read().decode('utf-8')
err = stderr.read().decode('utf-8')
print("OUT:", out)
if err:
    print("ERR:", err)

# Restart station service
stdin, stdout, stderr = ssh.exec_command('echo 1 | sudo -S systemctl start plant-station')
stdout.channel.recv_exit_status()

local_dir = r'c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\test_captures\nir_live_test'
os.makedirs(local_dir, exist_ok=True)
sftp.get('/home/pi/plant-stress-ndvi/static/test_nir_off.jpg', os.path.join(local_dir, 'test_nir_off.jpg'))
sftp.get('/home/pi/plant-stress-ndvi/static/test_nir_on.jpg', os.path.join(local_dir, 'test_nir_on.jpg'))
sftp.close()
ssh.close()

def load_img(name):
    return cv2.imdecode(np.fromfile(os.path.join(local_dir, name), dtype=np.uint8), cv2.IMREAD_COLOR)

f_off = load_img('test_nir_off.jpg')
f_on = load_img('test_nir_on.jpg')

diff = f_on.astype(float) - f_off.astype(float)
abs_diff = cv2.absdiff(f_on, f_off)

print('=== NIR ISOLATED TEST RESULTS ===')
print(f'Off frame: Mean BGR = B={f_off[:,:,0].mean():.2f}, G={f_off[:,:,1].mean():.2f}, R={f_off[:,:,2].mean():.2f}')
print(f'On frame:  Mean BGR = B={f_on[:,:,0].mean():.2f}, G={f_on[:,:,1].mean():.2f}, R={f_on[:,:,2].mean():.2f}')
print(f'Delta (On - Off): B={diff[:,:,0].mean():.2f}, G={diff[:,:,1].mean():.2f}, R={diff[:,:,2].mean():.2f}')
print(f'Max absolute difference: BGR={abs_diff.max(axis=(0,1))}')

gray_diff = cv2.cvtColor(abs_diff, cv2.COLOR_BGR2GRAY)
_, max_val, _, max_loc = cv2.minMaxLoc(gray_diff)
print(f'Max diff location: {max_loc}, value: {max_val}')
x, y = max_loc
print(f'At ({x},{y}): Off={f_off[y,x]}, On={f_on[y,x]}')
