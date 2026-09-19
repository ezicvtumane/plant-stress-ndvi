"""
Active NDVI Computation, Calibration & False-Color Mapping Engine
Author: Alisa Kovaleva
Project: Plant Stress Active Dual-Wavelength Spectrophotometry Complex
"""

import logging
from typing import Dict, Tuple, Optional
import numpy as np
import cv2
from src import config

logger = logging.getLogger(__name__)

class NDVIProcessor:
    """
    Implements radiometric ambient subtraction, 18% gray card calibration,
    normalized difference vegetation index calculation, and thermal colormap generation.
    """
    def __init__(self, k_factor: float = config.DEFAULT_K_COEFFICIENT):
        self.k_factor = float(k_factor)

    def compute_k_factor_from_gray_card(
        self,
        ambient_frame: np.ndarray,
        nir_frame: np.ndarray,
        red_frame: np.ndarray,
        roi: Optional[Tuple[int, int, int, int]] = None
    ) -> float:
        """
        Calculates sensor calibration factor k = I_660 / I_850 on an 18% Gray Card
        after subtracting ambient illumination:
          I_net = max(0, I_flash - I_ambient)
        """
        # Radiometric ambient subtraction
        nir_net = np.maximum(0, nir_frame.astype(np.float32) - ambient_frame.astype(np.float32))
        red_net = np.maximum(0, red_frame.astype(np.float32) - ambient_frame.astype(np.float32))

        if roi is not None:
            x, y, w, h = roi
            nir_net = nir_net[y:y+h, x:x+w]
            red_net = red_net[y:y+h, x:x+w]

        mean_nir = float(np.mean(nir_net))
        mean_red = float(np.mean(red_net))

        if mean_nir <= 1e-3:
            logger.error("NIR channel intensity on calibration card is too low (< 1e-3).")
            return config.DEFAULT_K_COEFFICIENT

        self.k_factor = mean_red / mean_nir
        logger.info("Calibrated k-factor: %.4f (Mean Red: %.2f, Mean NIR: %.2f)",
                    self.k_factor, mean_red, mean_nir)
        return self.k_factor

    def compute_ndvi_map(
        self,
        ambient_frame: np.ndarray,
        nir_frame: np.ndarray,
        red_frame: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
        """
        Performs:
        1. Ambient background subtraction:
           I_nir_clean = max(0, I_nir - I_ambient)
           I_red_clean = max(0, I_red - I_ambient)
        2. Segmentation: NIR mask (I_nir_clean > threshold)
        3. Pixelwise NDVI:
           NDVI = (k * NIR - Red) / (k * NIR + Red + eps)
        4. Statistical aggregation of vegetation indices.
        
        Returns:
            ndvi_map (np.ndarray of float32, range [-1, 1])
            mask (np.ndarray of uint8, 255 for plant, 0 for background)
            metrics (dict of summary statistics)
        """
        # Convert to float32
        amb = ambient_frame.astype(np.float32)
        nir_raw = nir_frame.astype(np.float32)
        red_raw = red_frame.astype(np.float32)

        # Ambient subtraction
        nir_clean = np.maximum(0.0, nir_raw - amb)
        red_clean = np.maximum(0.0, red_raw - amb)

        # Vegetative mask: reflection in 850nm above threshold
        mask = (nir_clean > config.NIR_BACKGROUND_THRESHOLD).astype(np.uint8) * 255

        # Morphological clean-up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Scaled NIR
        nir_scaled = self.k_factor * nir_clean
        numerator = nir_scaled - red_clean
        denominator = nir_scaled + red_clean + 1e-6

        # Calculate NDVI
        ndvi_map = np.divide(numerator, denominator)
        ndvi_map = np.clip(ndvi_map, -1.0, 1.0)

        # Filter outside mask
        plant_pixels = ndvi_map[mask > 0]
        total_plant_pixels = len(plant_pixels)

        if total_plant_pixels == 0:
            metrics = {
                "plant_pixel_count": 0,
                "ndvi_mean": 0.0,
                "ndvi_std": 0.0,
                "ndvi_median": 0.0,
                "healthy_percent": 0.0,
                "latent_stress_percent": 0.0,
                "severe_stress_percent": 0.0,
                "k_factor": self.k_factor
            }
        else:
            ndvi_mean = float(np.mean(plant_pixels))
            ndvi_std = float(np.std(plant_pixels))
            ndvi_median = float(np.median(plant_pixels))

            healthy_cnt = np.count_nonzero(plant_pixels > config.NDVI_HEALTHY_MIN)
            stress_cnt = np.count_nonzero((plant_pixels > config.NDVI_STRESS_MIN) & (plant_pixels <= config.NDVI_HEALTHY_MIN))
            severe_cnt = np.count_nonzero(plant_pixels <= config.NDVI_STRESS_MIN)

            metrics = {
                "plant_pixel_count": int(total_plant_pixels),
                "ndvi_mean": round(ndvi_mean, 4),
                "ndvi_std": round(ndvi_std, 4),
                "ndvi_median": round(ndvi_median, 4),
                "healthy_percent": round((healthy_cnt / total_plant_pixels) * 100.0, 2),
                "latent_stress_percent": round((stress_cnt / total_plant_pixels) * 100.0, 2),
                "severe_stress_percent": round((severe_cnt / total_plant_pixels) * 100.0, 2),
                "k_factor": round(self.k_factor, 4)
            }

        return ndvi_map, mask, metrics

    def render_colormap_jet(self, ndvi_map: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Converts NDVI values [-0.2, 1.0] into false-color thermal map using COLORMAP_JET.
        Background (mask == 0) is rendered in pure black.
        """
        # Normalize NDVI range [-0.2, 1.0] into uint8 [0, 255]
        min_val = -0.2
        max_val = 1.0
        normalized = np.clip((ndvi_map - min_val) / (max_val - min_val), 0.0, 1.0)
        u8 = (normalized * 255.0).astype(np.uint8)

        # Apply JET colormap
        colored = cv2.applyColorMap(u8, cv2.COLORMAP_JET)

        # Black out background
        colored[mask == 0] = [0, 0, 0]

        return colored
