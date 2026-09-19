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
    Calculates leaf-to-air temperature differential:
        Delta_T = T_leaf - T_air
    Under active transpiration, Delta_T is typically negative (-1.5 to -3.5 °C).
    Under stomatal closure (water/osmotic stress), Delta_T rises to 0 or positive.
    """
    def __init__(self, emissivity: float = config.LEAF_EMISSIVITY):
        self.emissivity = emissivity

    def parse_thermal_frame(
        self,
        thermal_image_path: str,
        leaf_roi: Optional[Tuple[int, int, int, int]] = None,
        air_roi: Optional[Tuple[int, int, int, int]] = None,
        manual_t_air: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Extracts thermal readings from an image file or simulated thermal matrix.
        """
        img = cv2.imread(thermal_image_path)
        if img is None:
            logger.warning("Could not load thermal image %s. Generating mock data.", thermal_image_path)
            t_leaf = 23.8
            t_air = 22.0
        else:
            # If color thermal image with ironbow/rainbow palette:
            # Here we provide standard ROI extraction or fallback
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
        is_transpiration_depressed = delta_t >= -0.5

        return {
            "t_leaf_celsius": round(t_leaf, 2),
            "t_air_celsius": round(t_air, 2),
            "delta_t_celsius": round(delta_t, 2),
            "transpiration_depressed": is_transpiration_depressed,
            "emissivity": self.emissivity
        }
