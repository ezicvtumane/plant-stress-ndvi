"""
Comparative Triptych Generator: RGB - NDVI Heatmap - Thermal UTi120S
Author: Alisa Kovaleva
Project: Plant Stress Active Phenotyping System
"""

import logging
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
import matplotlib.pyplot as plt
from src import config

logger = logging.getLogger(__name__)

def generate_triptych(
    rgb_path: Optional[str] = None,
    ndvi_heatmap_path: Optional[str] = None,
    thermal_path: Optional[str] = None,
    output_filename: str = "triptych_day04_drought.png",
    day: int = 4,
    sample_id: str = "Drought_03",
    metrics_text: str = "NDVI: 0.48 (-36%) | Delta_T: +0.4 °C | Soil: 18.2%"
) -> Path:
    """
    Creates a publication-ready side-by-side triptych comparing:
    1. RGB photograph (showing apparently normal plant without visible wilting)
    2. Active NDVI Heatmap (revealing pronounced degradation of photosynthetic absorption)
    3. UTi120S Thermogram (showing stoppage of evaporative cooling / stomatal closure)
    """
    out_dir = config.TRIPTYCH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_filename

    # Load panels from files
    def load_panel(path, label):
        if path and Path(path).exists():
            img = cv2.imread(str(path))
            if img is not None:
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        canvas = np.full((480, 640, 3), 35, dtype=np.uint8)
        cv2.putText(canvas, f"File not found: {label}", (40, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1, cv2.LINE_AA)
        return canvas

    img_rgb = load_panel(rgb_path, "RGB")
    img_ndvi = load_panel(ndvi_heatmap_path, "NDVI Heatmap")
    img_therm = load_panel(thermal_path, "Thermal UTi120S")

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))

    # Panel 1: RGB
    axes[0].imshow(img_rgb)
    axes[0].set_title("1. Визуальный контроль (RGB)\nСимптомы увядания отсутствуют", fontsize=11, fontweight="bold")
    axes[0].axis("off")

    # Panel 2: NDVI
    axes[1].imshow(img_ndvi)
    axes[1].set_title("2. Активная спектрофотометрия (NDVI)\nСкрытый стресс: падение хлорофилла", fontsize=11, fontweight="bold", color="darkred")
    axes[1].axis("off")

    # Panel 3: Thermal
    axes[2].imshow(img_therm)
    axes[2].set_title("3. Термограмма (UNI-T UTi120S)\nЗакрытие устьиц: лист теплее воздуха", fontsize=11, fontweight="bold", color="darkred")
    axes[2].axis("off")

    # Header and footer annotations
    plt.suptitle(f"Мультимодальная триада раненнего стресса: Образец {sample_id} (День {day})\n{metrics_text}",
                 fontsize=13, fontweight="bold", y=0.98)

    plt.tight_layout()
    plt.savefig(str(out_path), dpi=300, bbox_inches="tight")
    plt.close()

    logger.info("Publication triptych generated at: %s", out_path)
    return out_path

if __name__ == "__main__":
    generate_triptych()
