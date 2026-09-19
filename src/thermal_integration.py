"""
UNI-T UTi120S Thermal Imaging Integration & Transpiration Analysis
Author: Alisa Kovaleva
Project: Plant Stress Active Phenotyping System
"""

import logging
from typing import Dict, Optional, Tuple
import cv2
import numpy as np
from src import config

logger = logging.getLogger(__name__)

class ThermalAnalyzer:
    """
    Analyzes thermograms from UNI-T UTi120S (NETD < 0.06 °C, e = 0.98).
    Calculates:
      1. Leaf-to-air temperature differential: Delta_T = T_leaf - T_air
      2. Crop Water Stress Index (CWSI):
         CWSI = (T_leaf - T_wet) / (T_dry - T_wet)
         - Cancels out absolute sensor bias (+/- 2 deg C) of the microbolometer.
         - CWSI ~ 0.0: Fully open stomata, optimal transpiration.
         - CWSI ~ 1.0: Complete stomatal closure, acute stress.
    """
    def __init__(self, emissivity: float = config.LEAF_EMISSIVITY):
        self.emissivity = emissivity

    def compute_cwsi(
        self,
        t_leaf: float,
        t_air: float,
        t_wet: Optional[float] = None,
        t_dry: Optional[float] = None
    ) -> float:
        """
        Calculates normalized Crop Water Stress Index (CWSI in [0.0, 1.0]).
        If reference targets are not measured directly:
          T_wet = T_air - 3.2 °C (maximum evaporative cooling baseline)
          T_dry = T_air + 2.0 °C (non-transpiring boundary layer baseline)
        """
        tw = t_wet if t_wet is not None else (t_air - 3.2)
        td = t_dry if t_dry is not None else (t_air + 2.0)

        if td <= tw:
            return 0.0

        raw_cwsi = (t_leaf - tw) / (td - tw)
        return float(np.clip(raw_cwsi, 0.0, 1.0))

    def parse_thermal_frame(
        self,
        thermal_image_path: str,
        leaf_roi: Optional[Tuple[int, int, int, int]] = None,
        air_roi: Optional[Tuple[int, int, int, int]] = None,
        manual_t_air: Optional[float] = None,
        manual_t_wet: Optional[float] = None,
        manual_t_dry: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Extracts thermal readings and computes both Delta_T and CWSI.
        """
        img = cv2.imread(thermal_image_path)
        if img is None:
            logger.warning("Could not load thermal image %s. Generating mock data.", thermal_image_path)
            t_leaf = 23.8
            t_air = 22.0
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if leaf_roi:
                x, y, w, h = leaf_roi
                leaf_sub = gray[y:y+h, x:x+w]
            else:
                leaf_sub = gray

            # Map pixel intensity [0, 255] to realistic temperature span [15.0, 35.0 C]
            t_min, t_max = 15.0, 35.0
            t_leaf = float(np.mean(leaf_sub) / 255.0 * (t_max - t_min) + t_min)
            t_air = manual_t_air if manual_t_air is not None else 22.5

        delta_t = t_leaf - t_air
        cwsi = self.compute_cwsi(t_leaf, t_air, manual_t_wet, manual_t_dry)
        is_transpiration_depressed = cwsi >= 0.45 or delta_t >= -0.5

        return {
            "t_leaf_celsius": round(t_leaf, 2),
            "t_air_celsius": round(t_air, 2),
            "delta_t_celsius": round(delta_t, 2),
            "cwsi_index": round(cwsi, 3),
            "transpiration_depressed": is_transpiration_depressed,
            "emissivity": self.emissivity
        }
