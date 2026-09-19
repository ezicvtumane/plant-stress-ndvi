"""
Hardware and Calibration Configuration
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry Complex
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
TRIPTYCH_DIR = DATA_DIR / "triptychs"

# Ensure directories exist
for d in [RAW_DATA_DIR, PROCESSED_DATA_DIR, TRIPTYCH_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Camera / Optical Sensor Configuration
CAMERA_INDEX = 0  # /dev/video0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_MANUAL_EXPOSURE = 1  # 1 = Manual mode in V4L2
CAMERA_EXPOSURE_VALUE = 120  # Fixed shutter value
CAMERA_AUTO_WB = 0  # 0 = Manual White Balance (AWB disabled)

# Photometric Calibration Parameters (18% Gray Card)
# k = I_660_ref / I_850_ref (sensor sensitivity ratio)
DEFAULT_K_COEFFICIENT = 1.054

# Plant Segmentation & Masking
NIR_BACKGROUND_THRESHOLD = 15  # Minimum pixel intensity under 850nm to classify as plant
MIN_CONTOUR_AREA = 500  # Minimum pixel area for valid leaves

# Physiological Stress Thresholds (NDVI)
NDVI_HEALTHY_MIN = 0.60  # Normal active photosynthetic tissue (healthy chloroplasts)
NDVI_STRESS_MIN = 0.35   # Latent stress range: 0.35 < NDVI <= 0.60
NDVI_NECROTIC_MAX = 0.35 # Severe stress / senescence / cellular damage

# Soil Moisture Sensor Calibration (ADS1115 v1.2 Capacitive Sensor)
# Two-point calibration voltages
V_DRY = 2.75   # Voltage in open air (0% moisture)
V_WET = 1.30   # Voltage submerged in water (100% moisture)
ADS1115_I2C_ADDRESS = 0x48
ADS1115_I2C_BUS = 1

# Relay GPIO Control Pins (Orange Pi / Linux GPIO)
# Active LOW or HIGH depending on relay board (default: active LOW)
RELAY_PIN_850NM = 12  # PA12
RELAY_PIN_660NM = 11  # PA11
RELAY_ACTIVE_LOW = True
FLASH_SETTLING_TIME_SEC = 0.15  # Stabilization delay after switching relay before frame capture

# Thermal Imaging Configuration (UNI-T UTi120S)
LEAF_EMISSIVITY = 0.98  # Standard emissivity for plant leaves
