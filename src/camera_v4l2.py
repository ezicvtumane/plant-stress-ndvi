"""
V4L2 USB NoIR Camera Handler with Fixed Manual Exposure
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry Complex
"""

import logging
import cv2
import numpy as np
from src import config

logger = logging.getLogger(__name__)

class CameraV4L2:
    """
    Handles frame acquisition with strict photometric repeatability:
    - Manual fixed exposure (CAP_PROP_AUTO_EXPOSURE = 1)
    - Auto white-balance disabled
    - Frame buffer flush
    """
    def __init__(self, camera_idx: int = config.CAMERA_INDEX):
        self.camera_idx = camera_idx
        self.cap = None
        self.is_connected = False
        self._init_camera()

    def _init_camera(self):
        """Opens camera and configures V4L2 properties."""
        try:
            # Under Linux, use V4L2 backend
            backend = cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else cv2.CAP_ANY
            self.cap = cv2.VideoCapture(self.camera_idx, backend)
            
            if not self.cap.isOpened():
                logger.warning("Could not open camera at index %d. Simulation frames will be generated.", self.camera_idx)
                self.is_connected = False
                return

            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

            # Enforce manual exposure: in V4L2, 1 = manual, 3 = auto
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, config.CAMERA_MANUAL_EXPOSURE)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, config.CAMERA_EXPOSURE_VALUE)

            # Disable auto white balance
            self.cap.set(cv2.CAP_PROP_AUTO_WB, config.CAMERA_AUTO_WB)

            self.is_connected = True
            logger.info("Camera %d initialized with manual exposure=%d, auto_wb=%d",
                        self.camera_idx, config.CAMERA_EXPOSURE_VALUE, config.CAMERA_AUTO_WB)
        except Exception as e:
            logger.warning("Camera initialization exception: %s. Using simulation mode.", e)
            self.is_connected = False

    def capture_frame(self, flush_frames: int = 2) -> np.ndarray:
        """
        Captures a single grayscale frame, flushing older buffered frames
        to guarantee instant optical response.
        """
        if not self.is_connected or self.cap is None:
            # Return synthetic test frame (720x1280)
            return self._generate_mock_frame()

        # Flush buffer
        for _ in range(flush_frames):
            self.cap.grab()

        ret, frame = self.cap.read()
        if not ret or frame is None:
            logger.error("Failed to read frame from camera.")
            return self._generate_mock_frame()

        # Convert to single-channel 8-bit grayscale if BGR
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        return gray

    def _generate_mock_frame(self) -> np.ndarray:
        """Generates realistic synthetic leaf frame for dry-run testing."""
        h, w = config.CAMERA_HEIGHT, config.CAMERA_WIDTH
        mock = np.full((h, w), 10, dtype=np.uint8)
        # Draw mock leaf ellipse in center
        cv2.ellipse(mock, (w // 2, h // 2), (180, 260), 30, 0, 360, 140, -1)
        cv2.ellipse(mock, (w // 2 - 80, h // 2 + 50), (120, 180), -45, 0, 360, 160, -1)
        return mock

    def release(self):
        """Releases the camera device."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.is_connected = False
            logger.info("Camera device released.")
