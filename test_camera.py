import cv2
import sys

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
if not cap.isOpened():
    print('ERROR: Could not open /dev/video0')
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

for _ in range(5):
    cap.grab()

ret, frame = cap.read()
if ret and frame is not None:
    path = '/home/pi/plant-stress-ndvi/test_camera_snap.jpg'
    cv2.imwrite(path, frame)
    h, w, c = frame.shape
    print(f'SUCCESS: Captured test frame {w}x{h} ({c} channels) -> {path}')
else:
    print('ERROR: Failed to capture frame')
cap.release()
