import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd

# Add repo to sys.path
repo_dir = Path(r"C:\Users\Администратор\Documents\plant-stress-ndvi-repo")
sys.path.insert(0, str(repo_dir))

from src.thermal_integration import ThermalAnalyzer

# Load dataset
csv_path = repo_dir / "data" / "measurements.csv"
df = pd.read_csv(csv_path, encoding="utf-8")

analyzer = ThermalAnalyzer()
cwsi_list = []
for idx, row in df.iterrows():
    cwsi = analyzer.compute_cwsi(row['T_Leaf_C'], row['T_Air_C'], vpd=row['VPD_kPa'])
    cwsi_list.append(cwsi)
df['CWSI'] = cwsi_list
df['Day'] = (df.index // 5) + 1

# Extract Drought cohort
drought = df[df['Group'] == 'Засуха'].sort_values('Day').reset_index(drop=True)
days = drought['Day'].values
cwsi = drought['CWSI'].values
ndvi = drought['NDVI_Mean'].values

output_dir = repo_dir / "docs" / "images"
output_dir.mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Segoe UI', 'Calibri']
plt.rcParams['axes.unicode_minus'] = False


def make_chart(theme="dark"):
    # 1920x1080 at 120 DPI -> 16 x 9 inches
    fig = plt.figure(figsize=(16, 9), dpi=120)
    
    if theme == "dark":
        bg_color = "#0B1120"       # Deep dark navy
        card_bg = "#131E38"        # Card background
        card_border = "#2A3B60"
        text_color = "#F8FAFC"     # White slate
        subtext_color = "#94A3B8"  # Cool gray
        grid_color = "#1E293B"     # Subtle grid line
        
        red_line = "#FF3355"       # Vivid neon red
        red_point = "#FF5577"
        blue_line = "#00D2FF"      # Vivid electric cyan-blue
        blue_point = "#38BDF8"
        
        window_bg = "#F59E0B"      # Amber gold
        window_alpha = 0.14
        border_color = "#334155"
        box_shadow = "#050811"
    else:
        bg_color = "#FFFFFF"
        card_bg = "#F8FAFC"
        card_border = "#CBD5E1"
        text_color = "#0F172A"
        subtext_color = "#475569"
        grid_color = "#E2E8F0"
        
        red_line = "#DC2626"       # Crimson red
        red_point = "#EF4444"
        blue_line = "#0284C7"      # Vibrant Sky blue
        blue_point = "#0EA5E9"
        
        window_bg = "#FBBF24"      # Amber
        window_alpha = 0.18
        border_color = "#CBD5E1"
        box_shadow = "#E2E8F0"

    fig.patch.set_facecolor(bg_color)
    
    # Custom axes rect to leave space for titles, legend, and large labels
    # [left, bottom, width, height]
    ax1 = fig.add_axes([0.08, 0.14, 0.83, 0.67])
    ax1.set_facecolor(bg_color)

    # 1. Highlight 48-Hour Anticipation Window (Day 4 to Day 7)
    window_start = 3.6
    window_end = 7.4
    ax1.axvspan(window_start, window_end, color=window_bg, alpha=window_alpha, zorder=1)
    
    # Grid
    ax1.grid(True, color=grid_color, linestyle="--", linewidth=1.2, alpha=0.7, zorder=0)

    # 2. CWSI Threshold line (CWSI = 0.5)
    ax1.axhline(0.5, color=red_line, linestyle=":", linewidth=2.2, alpha=0.7, zorder=2)
    ax1.text(0.7, 0.515, "Порог стресса: CWSI ≥ 0.5 (Устьичный коллапс)", 
             color=red_line, fontsize=12.5, fontweight="bold", alpha=0.95, zorder=5)

    # 3. Plot CWSI Curve (Left Axis)
    ax1.plot(days, cwsi, color=red_line, linewidth=4.5, marker="o", markersize=12, 
             markerfacecolor=red_point, markeredgecolor="#FFFFFF", markeredgewidth=2.2,
             zorder=6)
    ax1.fill_between(days, cwsi, color=red_line, alpha=0.10, zorder=2)

    ax1.set_xlabel("Сутки эксперимента (Pisum sativum, Когорта №3 «Терминальная засуха»)", 
                   fontsize=16, fontweight="bold", color=text_color, labelpad=12)
    ax1.set_ylabel("Индекс водного стресса CWSI (0.0 — 1.0)", 
                   fontsize=16, fontweight="bold", color=red_line, labelpad=12)
    ax1.set_ylim(-0.06, 1.25)
    ax1.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax1.set_yticklabels(["0.0\n(Норма)", "0.2", "0.4", "0.6\n(Стресс)", "0.8", "1.0\n(Увядание)"], 
                        fontsize=13, color=red_line, fontweight="bold")
    ax1.tick_params(axis='y', colors=red_line, labelsize=13)
    ax1.tick_params(axis='x', colors=text_color, labelsize=13.5)

    ax1.set_xlim(0.5, 11.5)
    ax1.set_xticks(range(1, 12))
    ax1.set_xticklabels([f"День {d}" for d in range(1, 12)], fontsize=13.5, fontweight="semibold")

    # 4. Right axis: NDVI (Blue)
    ax2 = ax1.twinx()
    ax2.set_facecolor("none")
    ax2.set_ylim(0.48, 0.96)
    ax2.set_yticks([0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90])
    ax2.tick_params(axis='y', colors=blue_line, labelsize=13)
    ax2.set_ylabel("Спектральный вегетационный индекс NDVI", 
                   fontsize=16, fontweight="bold", color=blue_line, labelpad=14)

    # NDVI Threshold line (NDVI = 0.70)
    ax2.axhline(0.70, color=blue_line, linestyle=":", linewidth=2.2, alpha=0.7, zorder=2)
    ax2.text(11.3, 0.708, "Оптический оптимум: NDVI ≥ 0.70", 
             color=blue_line, fontsize=12.5, fontweight="bold", alpha=0.95, zorder=5, ha="right")

    # Plot NDVI Curve
    ax2.plot(days, ndvi, color=blue_line, linewidth=4.5, marker="s", markersize=12,
             markerfacecolor=blue_point, markeredgecolor="#FFFFFF", markeredgewidth=2.2,
             zorder=7)

    # 5. Highlight Banner inside 48-hour Window (Top Center)
    banner_x = 5.5
    ax1.text(banner_x, 1.18, "⚡ ОКНО УПРЕЖДЕНИЯ: 48 ЧАСОВ (2 СУТОК)", 
             color="#F59E0B" if theme == "dark" else "#B45309",
             fontsize=16, fontweight="heavy", ha="center", va="center",
             bbox=dict(boxstyle="round,pad=0.5", facecolor=card_bg, edgecolor="#F59E0B", linewidth=2.2, alpha=0.98),
             zorder=10)
    
    ax1.text(banner_x, 1.09, "Латентная фаза: устьица закрыты, лист нагревается, но хлорофилл еще цел!",
             color=text_color, fontsize=12, fontweight="bold", ha="center", va="center",
             bbox=dict(boxstyle="round,pad=0.35", facecolor=card_bg, edgecolor=card_border, linewidth=1.2, alpha=0.95),
             zorder=9)

    # 6. Annotation 1: CWSI surge (Day 4 -> Day 6)
    # Put text to the left in open area (x=3.0, y=0.38 on ax1)
    ax1.annotate("Резкий взлет CWSI (0.29 → 1.00)\nСмыкание устьиц, остановка транспирации",
                 xy=(5.9, 0.57), xytext=(1.8, 0.78),
                 arrowprops=dict(facecolor=red_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                 fontsize=12, fontweight="bold", color=red_line,
                 bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=red_line, linewidth=1.8),
                 zorder=12)

    # 7. Annotation 2: NDVI inertia (Days 4 - 7)
    # Put text to the right top (x=7.7, y=0.88 on ax2)
    ax2.annotate("NDVI стабилен (0.75 – 0.81)\nОптика «не видит» скрытый стресс",
                 xy=(5.8, 0.76), xytext=(7.5, 0.88),
                 arrowprops=dict(facecolor=blue_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                 fontsize=12, fontweight="bold", color=blue_line,
                 bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=blue_line, linewidth=1.8),
                 zorder=12)

    # 8. Annotation 3: Late NDVI drop (Day 8 - 9)
    ax2.annotate("Запоздалый спад NDVI (до 0.62)\nНекроз и необратимое увядание",
                 xy=(9.0, 0.625), xytext=(8.6, 0.52),
                 arrowprops=dict(facecolor=blue_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                 fontsize=12, fontweight="bold", color=blue_line,
                 bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=blue_line, linewidth=1.8),
                 zorder=12)

    # Spines styling
    for spine in ax1.spines.values():
        spine.set_color(border_color)
        spine.set_linewidth(1.5)
    for spine in ax2.spines.values():
        spine.set_color(border_color)
        spine.set_linewidth(1.5)

    # Super Title & Subtitle at Top
    fig.text(0.5, 0.945, "ФИЗИОЛОГИЧЕСКАЯ АСИНХРОНИЯ: ТЕРМИЧЕСКИЙ vs СПЕКТРАЛЬНЫЙ СИГНАЛ", 
             fontsize=21, fontweight="heavy", color=text_color, ha="center")
    fig.text(0.5, 0.912, "Доказательство 48-часового упреждения: реакция устьичного аппарата (CWSI) против деградации хлорофилла (NDVI)", 
             fontsize=14, color=subtext_color, ha="center", fontweight="medium")

    # Bottom Legend Badges (Pills)
    legend_y = 0.045
    # Red pill for CWSI
    fig.text(0.28, legend_y, "  ●  CWSI (Термоканал UTi120S + SHT30): Детекция стресса на 4–5 сутки  ", 
             fontsize=13, fontweight="bold", color="#FFFFFF" if theme=="dark" else "#FFFFFF",
             ha="center", va="center",
             bbox=dict(boxstyle="round,pad=0.5", facecolor=red_line, edgecolor="none", alpha=0.95))
    
    # Blue pill for NDVI
    fig.text(0.72, legend_y, "  ■  NDVI (Оптика NoIR 660/850 нм): Реакция ткани лишь на 8–9 сутки (Δt = 48 ч)  ", 
             fontsize=13, fontweight="bold", color="#FFFFFF" if theme=="dark" else "#FFFFFF",
             ha="center", va="center",
             bbox=dict(boxstyle="round,pad=0.5", facecolor=blue_line, edgecolor="none", alpha=0.95))

    out_file = output_dir / f"video_cwsi_vs_ndvi_{theme}.png"
    plt.savefig(out_file, facecolor=fig.get_facecolor(), edgecolor='none', dpi=120)
    plt.close()
    print(f"Generated {out_file}")

make_chart("dark")
make_chart("light")
