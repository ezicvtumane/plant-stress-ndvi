import cv2
import time
import subprocess
import numpy as np
from hardware.hal import get_relay_controller

def set_v4l2_exposure(exp: int, gain: int):
    try:
        subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '-c', 
                        f'auto_exposure=1,exposure_time_absolute={exp},gain={gain},white_balance_automatic=0'], 
                        check=False, capture_output=True)
    except Exception:
        pass

def get_center_mean(frame):
    if frame is None:
        return 0
    h, w = frame.shape[:2]
    # Grab 200x200 center
    roi = frame[h//2-100:h//2+100, w//2-100:w//2+100]
    # We only care about intensity (grayscale equivalent) or just the specific channel.
    # Since it's BGR, Red is index 2, NIR is all channels but let's just use grayscale
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)

def main():
    relay = get_relay_controller()
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)

    def test_params(channel_name, relay_on_func, exp, gain):
        set_v4l2_exposure(exp, gain)
        time.sleep(0.3)
        relay_on_func(True)
        time.sleep(0.5)
        # flush buffer
        for _ in range(8):
            cap.read()
        ret, frame = cap.read()
        relay_on_func(False)
        mean_val = get_center_mean(frame)
        print(f'[{channel_name}] Exp: {exp:4d}, Gain: {gain:3d} => Mean Brightness: {mean_val:.1f}')
        return mean_val

    print('\n--- Starting RED (660nm) Calibration ---')
    red_exposures = [120, 250, 500, 800, 1000, 1500, 2000, 2500]
    red_results = []
    for exp in red_exposures:
        val = test_params('RED', relay.set_red, exp, 100)
        red_results.append((exp, val))
        if val > 240:
            print('-> Reached clipping, stopping RED sweep.')
            break

    print('\n--- Starting NIR (850nm) Calibration ---')
    nir_exposures = [500, 1000, 1500, 2000, 2500, 3000, 4000]
    nir_results = []
    for exp in nir_exposures:
        val = test_params('NIR', relay.set_nir, exp, 200)
        nir_results.append((exp, val))
        if val > 240:
            print('-> Reached clipping, stopping NIR sweep.')
            break

    cap.release()
    relay.cleanup()
    
    print('\n--- CALIBRATION SUMMARY ---')
    print('RED tests (Gain=100):', red_results)
    print('NIR tests (Gain=200):', nir_results)

if __name__ == '__main__':
    main()
