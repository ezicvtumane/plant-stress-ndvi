import sys
import os
import time
import subprocess
import cv2
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, '/home/pi/plant-stress-ndvi')

from hardware.hal import get_relay_controller

def check_target():
    print("[*] Starting FUM tape target diagnostic...")
    
    def set_v4l2_exposure(exp_val, gain_val):
        try:
            subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '-c', 
                            f'auto_exposure=1,exposure_time_absolute={exp_val},gain={gain_val},white_balance_automatic=0'], 
                           check=False)
        except Exception as e:
            print(f"[!] v4l2-ctl error: {e}")

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("[ERROR] Cannot open camera /dev/video0")
        return

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)

    relay = get_relay_controller()

    try:
        # --- 1. NIR 850 nm capture ---
        print("  -> Capturing NIR 850 nm...")
        set_v4l2_exposure(2500, 200)
        time.sleep(0.25)
        relay.set_nir(True)
        time.sleep(0.45)
        for _ in range(10): cap.grab()
        ret_n, frame_nir = cap.read()
        relay.set_nir(False)

        # Ambient NIR
        time.sleep(0.20)
        for _ in range(8): cap.grab()
        ret_an, frame_amb_nir = cap.read()

        # --- 2. RED 660 nm capture ---
        print("  -> Capturing RED 660 nm...")
        set_v4l2_exposure(120, 40)
        time.sleep(0.25)
        for _ in range(8): cap.grab()
        relay.set_red(True)
        time.sleep(0.45)
        for _ in range(10): cap.grab()
        ret_r, frame_red = cap.read()
        relay.set_red(False)

        # Ambient RED
        time.sleep(0.20)
        for _ in range(8): cap.grab()
        ret_ar, frame_amb_red = cap.read()

    finally:
        relay.set_nir(False)
        relay.set_red(False)
        cap.release()
        try:
            subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '-c', 'auto_exposure=3'], check=False)
        except Exception:
            pass

    if not (ret_n and ret_r and ret_an and ret_ar):
        print("[ERROR] Failed to capture all frames!")
        return

    print("[*] Frames captured successfully. Analyzing reflectance...")

    # Signal extraction:
    # RED: Channel 2 (Red)
    red_raw = frame_red[:, :, 2].astype(np.float32)
    amb_red = frame_amb_red[:, :, 2].astype(np.float32)
    red_clean = np.maximum(0.0, red_raw - amb_red)

    # NIR: Mono intensity (mean over channels for NoIR sensor under 850nm)
    nir_raw = frame_nir.astype(np.float32).mean(axis=2)
    amb_nir = frame_amb_nir.astype(np.float32).mean(axis=2)
    nir_clean = np.maximum(0.0, nir_raw - amb_nir)

    # Find candidate bright targets (the FUM tape target)
    # Target should be bright in both RED and NIR, or look at the brightest 10% area
    combined_signal = red_clean + nir_clean
    blur = cv2.GaussianBlur(combined_signal, (15, 15), 0)

    # Let's inspect:
    # 1. Standard corner ROI (top-left 4%-16%)
    h, w = red_clean.shape
    c_y1, c_y2 = int(h * 0.04), int(h * 0.16)
    c_x1, c_x2 = int(w * 0.04), int(w * 0.16)
    corner_red = float(np.mean(red_clean[c_y1:c_y2, c_x1:c_x2]))
    corner_nir = float(np.mean(nir_clean[c_y1:c_y2, c_x1:c_x2]))

    # 2. Maximum intensity ROI (where the user actually placed the tape, e.g. a 80x80 box around peak)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blur)
    peak_x, peak_y = max_loc
    half_box = 40
    bx1 = max(0, peak_x - half_box)
    bx2 = min(w, peak_x + half_box)
    by1 = max(0, peak_y - half_box)
    by2 = min(h, peak_y + half_box)

    target_red_raw = float(np.mean(red_raw[by1:by2, bx1:bx2]))
    target_nir_raw = float(np.mean(nir_raw[by1:by2, bx1:bx2]))
    target_red_clean = float(np.mean(red_clean[by1:by2, bx1:bx2]))
    target_nir_clean = float(np.mean(nir_clean[by1:by2, bx1:bx2]))
    
    # Saturation check: max pixel value inside peak box
    red_max_pixel = float(np.max(frame_red[by1:by2, bx1:bx2, 2]))
    nir_max_pixel = float(np.max(frame_nir[by1:by2, bx1:bx2]))
    
    # Calculate balance ratio k_bal
    k_bal = (target_red_clean / target_nir_clean) if target_nir_clean > 0.1 else 0.0

    print("--- РЕЗУЛЬТАТЫ АНАЛИЗА ---")
    print(f"Положение самого яркого объекта (мишени): X={peak_x}, Y={peak_y} (box: {bx1}:{bx2}, {by1}:{by2})")
    print(f"Красный канал (RED 660 нм): чистый сигнал = {target_red_clean:.1f} DN (raw={target_red_raw:.1f}, пик={red_max_pixel:.0f}/255)")
    print(f"ИК канал (NIR 850 нм): чистый сигнал = {target_nir_clean:.1f} DN (raw={target_nir_raw:.1f}, пик={nir_max_pixel:.0f}/255)")
    print(f"Расчетный баланс эмиттеров k_bal = {k_bal:.3f}")
    print(f"Фоновые показатели в верхнем левом углу: RED={corner_red:.1f}, NIR={corner_nir:.1f}")

    # Build diagnostic visual image
    vis = np.zeros((h, w * 2, 3), dtype=np.uint8)
    
    # Left half: RED frame with peak box and corner box
    vis_red = cv2.cvtColor(np.clip(red_clean * (255.0 / (np.max(red_clean) + 1e-5)), 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    cv2.rectangle(vis_red, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
    cv2.putText(vis_red, f"Target ROI (Peak: {peak_x},{peak_y})", (bx1, max(20, by1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.rectangle(vis_red, (c_x1, c_y1), (c_x2, c_y2), (0, 0, 255), 1)
    cv2.putText(vis_red, "Default Corner ROI", (c_x1, max(15, c_y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    cv2.putText(vis_red, f"RED 660nm (Signal: {target_red_clean:.1f})", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # Right half: NIR frame with peak box
    vis_nir = cv2.cvtColor(np.clip(nir_clean * (255.0 / (np.max(nir_clean) + 1e-5)), 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    cv2.rectangle(vis_nir, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
    cv2.putText(vis_nir, f"NIR 850nm (Signal: {target_nir_clean:.1f})", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(vis_nir, f"k_bal = {k_bal:.3f}", (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if 0.5 <= k_bal <= 2.5 else (0, 0, 255), 2)

    vis[:, :w] = vis_red
    vis[:, w:] = vis_nir

    # Save outputs
    out_dir = '/home/pi/plant-stress-ndvi/static'
    cv2.imwrite(os.path.join(out_dir, 'fum_check_diag.jpg'), vis)
    cv2.imwrite(os.path.join(out_dir, 'fum_check_raw_red.jpg'), frame_red)
    cv2.imwrite(os.path.join(out_dir, 'fum_check_raw_nir.jpg'), frame_nir)
    print(f"[*] Diagnostic image saved to {os.path.join(out_dir, 'fum_check_diag.jpg')}")

if __name__ == '__main__':
    check_target()
