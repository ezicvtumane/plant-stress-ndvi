import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
import cv2

# Add repo to sys.path
repo_dir = Path(__file__).resolve().parent.parent
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
        card_bg = "#111C35"        # Card background
        card_border = "#2A3B60"
        text_color = "#F8FAFC"     # White slate
        subtext_color = "#94A3B8"  # Cool gray
        grid_color = "#1E293B"     # Subtle grid line
        
        red_line = "#FF3355"       # Vivid neon red
        red_point = "#FF5577"
        blue_line = "#00D2FF"      # Vivid electric cyan-blue
        blue_point = "#38BDF8"
        
        window_bg = "#F59E0B"      # Amber gold
        window_alpha = 0.15
        border_color = "#334155"
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

    fig.patch.set_facecolor(bg_color)
    
    # Custom axes rect to leave generous space for titles, bottom HUD, and large labels
    # [left, bottom, width, height]
    ax1 = fig.add_axes([0.08, 0.16, 0.83, 0.65])
    ax1.set_facecolor(bg_color)

    # 1. Highlight 48-Hour Anticipation Window (Day 4 to Day 7)
    window_start = 3.6
    window_end = 7.4
    ax1.axvspan(window_start, window_end, color=window_bg, alpha=window_alpha, zorder=1)
    
    # Grid
    ax1.grid(True, color=grid_color, linestyle="--", linewidth=1.2, alpha=0.7, zorder=0)

    # 2. CWSI Threshold line (CWSI = 0.5)
    ax1.axhline(0.5, color=red_line, linestyle=":", linewidth=2.2, alpha=0.7, zorder=2)
    ax1.text(0.7, 0.525, "Порог стресса: CWSI ≥ 0.5 (Устьичный коллапс)", 
             color=red_line, fontsize=12, fontweight="bold", alpha=0.95, zorder=5)

    # 3. Plot CWSI Curve (Left Axis)
    ax1.plot(days, cwsi, color=red_line, linewidth=4.5, marker="o", markersize=12, 
             markerfacecolor=red_point, markeredgecolor="#FFFFFF", markeredgewidth=2.2,
             zorder=6)
    ax1.fill_between(days, cwsi, color=red_line, alpha=0.10, zorder=2)

    ax1.set_xlabel("Сутки эксперимента (Pisum sativum, Когорта №3 «Терминальная засуха»)", 
                   fontsize=15, fontweight="bold", color=text_color, labelpad=10)
    ax1.set_ylabel("Индекс водного стресса CWSI (0.0 — 1.0)", 
                   fontsize=16, fontweight="bold", color=red_line, labelpad=12)
    ax1.set_ylim(-0.06, 1.28)
    ax1.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax1.set_yticklabels(["0.0\n(Норма)", "0.2", "0.4", "0.6\n(Стресс)", "0.8", "1.0\n(Увядание)"], 
                        fontsize=12.5, color=red_line, fontweight="bold")
    ax1.tick_params(axis='y', colors=red_line, labelsize=12.5)
    ax1.tick_params(axis='x', colors=text_color, labelsize=13)

    ax1.set_xlim(0.5, 11.5)
    ax1.set_xticks(range(1, 12))
    ax1.set_xticklabels([f"День {d}" for d in range(1, 12)], fontsize=13, fontweight="semibold")

    # 4. Right axis: NDVI (Blue)
    ax2 = ax1.twinx()
    ax2.set_facecolor("none")
    ax2.set_ylim(0.48, 0.98)
    ax2.set_yticks([0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90])
    ax2.tick_params(axis='y', colors=blue_line, labelsize=12.5)
    ax2.set_ylabel("Спектральный вегетационный индекс NDVI", 
                   fontsize=16, fontweight="bold", color=blue_line, labelpad=14)

    # NDVI Threshold line (NDVI = 0.70)
    ax2.axhline(0.70, color=blue_line, linestyle=":", linewidth=2.2, alpha=0.7, zorder=2)
    ax2.text(11.3, 0.675, "Оптический оптимум: NDVI ≥ 0.70", 
             color=blue_line, fontsize=12, fontweight="bold", alpha=0.95, zorder=5, ha="right")

    # Plot NDVI Curve
    ax2.plot(days, ndvi, color=blue_line, linewidth=4.5, marker="s", markersize=12,
             markerfacecolor=blue_point, markeredgecolor="#FFFFFF", markeredgewidth=2.2,
             zorder=7)

    # 5. Highlight Unified Banner inside 48-hour Window (Top Center)
    banner_x = 5.5
    banner_text = "⚡ ОКНО УПРЕЖДЕНИЯ: 48 ЧАСОВ (2 СУТОК)\nЛатентная фаза: устьица закрыты, лист греется, но хлорофилл еще интактен!"
    ax1.text(banner_x, 1.16, banner_text, 
             color="#F59E0B" if theme == "dark" else "#B45309",
             fontsize=13.5, fontweight="bold", ha="center", va="center", multialignment="center",
             bbox=dict(boxstyle="round,pad=0.6", facecolor=card_bg, edgecolor="#F59E0B", linewidth=2.2, alpha=0.98),
             zorder=10)

    # 6. Annotation 1: CWSI surge (Day 4 -> Day 6)
    # Position in clear space at (x=2.2, y=0.36) pointing to (5.85, 0.55)
    ax1.annotate("Резкий взлет CWSI (0.29 → 1.00)\nСмыкание устьиц, остановка транспирации",
                 xy=(5.85, 0.55), xytext=(2.2, 0.36),
                 arrowprops=dict(facecolor=red_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                 fontsize=12, fontweight="bold", color=red_line,
                 bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=red_line, linewidth=1.8),
                 zorder=12)

    # 7. Annotation 2: NDVI inertia (Days 4 - 7)
    # Position on right side at (x=8.2, y=0.88 on ax2) pointing to Day 7 NDVI (7.1, 0.79)
    ax2.annotate("NDVI стабилен (0.75 – 0.81)\nОптика «не видит» скрытый стресс",
                 xy=(7.1, 0.79), xytext=(8.1, 0.88),
                 arrowprops=dict(facecolor=blue_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                 fontsize=12, fontweight="bold", color=blue_line,
                 bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=blue_line, linewidth=1.8),
                 zorder=12)

    # 8. Annotation 3: Late NDVI drop (Day 8 - 9)
    # Position below Day 9 (x=8.6, y=0.525 on ax2) pointing to (9.0, 0.622)
    ax2.annotate("Запоздалый спад NDVI (до 0.62)\nНекроз и необратимое увядание",
                 xy=(9.0, 0.622), xytext=(8.6, 0.525),
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
    fig.text(0.5, 0.952, "ФИЗИОЛОГИЧЕСКАЯ АСИНХРОНИЯ: ТЕРМИЧЕСКИЙ vs СПЕКТРАЛЬНЫЙ СИГНАЛ", 
             fontsize=21, fontweight="heavy", color=text_color, ha="center")
    fig.text(0.5, 0.918, "Динамика ранней реакции устьичного аппарата (CWSI) относительно оптического индекса (NDVI)", 
             fontsize=14, color=subtext_color, ha="center", fontweight="medium")

    # Unified Bottom Status HUD
    hud_y = 0.045
    hud_text = (
        "  ●  КРАСНАЯ КРИВАЯ: CWSI (Тепловизор + SHT30) — Стресс на 4–5 сутки      │      "
        "■  СИНЯЯ КРИВАЯ: NDVI (NoIR 660/850 нм) — Реакция лишь на 8–9 сутки (Δt = 48 ч)  "
    )
    fig.text(0.5, hud_y, hud_text,
             fontsize=12, fontweight="bold", color=text_color,
             ha="center", va="center",
             bbox=dict(boxstyle="round,pad=0.55", facecolor=card_bg, edgecolor=card_border, linewidth=1.5, alpha=0.98))

    out_file = output_dir / f"video_cwsi_vs_ndvi_{theme}.png"
    plt.savefig(out_file, facecolor=fig.get_facecolor(), edgecolor='none', dpi=120)
    plt.close()
    print(f"Generated {out_file}")


def make_animation(theme="dark"):
    """
    Generates a 1920x1080 30fps animated MP4 video clip (~7 seconds)
    showing:
      Phase 1 (0-2s): Axes appear and curves draw smoothly from Day 1 to Day 11.
      Phase 2 (2-4s): Amber 48-hour window highlights and glows.
      Phase 3 (4-7s): Annotations and arrows pulse into view.
    """
    video_out = output_dir / "video_cwsi_vs_ndvi_animated.mp4"
    fps = 30
    total_frames = 180  # 6 seconds at 30 fps
    
    # Interpolated dense points for buttery smooth curve reveal
    dense_days = np.linspace(1, 11, 200)
    from scipy.interpolate import pchip_interpolate
    dense_cwsi = pchip_interpolate(days, cwsi, dense_days)
    dense_ndvi = pchip_interpolate(days, ndvi, dense_days)
    dense_cwsi = np.clip(dense_cwsi, 0.0, 1.0)
    
    # We'll render key frames to memory and write to cv2.VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(video_out), fourcc, fps, (1920, 1080))
    
    print("Rendering video animation frames...")
    
    # We will compute 60 distinct frames (each held for 3 frames = 30fps) for fast rendering
    steps = 60
    for s in range(steps + 1):
        progress = s / steps
        # Progress 0.0 to 0.5: Curve draws from day 1 to day 11
        curve_prog = min(1.0, progress / 0.5)
        # Progress 0.4 to 0.7: Window alpha fades in
        window_alpha_prog = max(0.0, min(1.0, (progress - 0.4) / 0.3))
        # Progress 0.6 to 1.0: Annotations fade in
        annot_prog = max(0.0, min(1.0, (progress - 0.6) / 0.4))
        
        fig = plt.figure(figsize=(16, 9), dpi=120)
        bg_color = "#0B1120"
        card_bg = "#111C35"
        card_border = "#2A3B60"
        text_color = "#F8FAFC"
        subtext_color = "#94A3B8"
        grid_color = "#1E293B"
        red_line = "#FF3355"
        red_point = "#FF5577"
        blue_line = "#00D2FF"
        blue_point = "#38BDF8"
        window_bg = "#F59E0B"
        border_color = "#334155"
        
        fig.patch.set_facecolor(bg_color)
        ax1 = fig.add_axes([0.08, 0.16, 0.83, 0.65])
        ax1.set_facecolor(bg_color)
        
        # Window highlight
        if window_alpha_prog > 0:
            ax1.axvspan(3.6, 7.4, color=window_bg, alpha=0.15 * window_alpha_prog, zorder=1)
            
        ax1.grid(True, color=grid_color, linestyle="--", linewidth=1.2, alpha=0.7, zorder=0)
        ax1.axhline(0.5, color=red_line, linestyle=":", linewidth=2.2, alpha=0.7, zorder=2)
        ax1.text(0.7, 0.525, "Порог стресса: CWSI ≥ 0.5 (Устьичный коллапс)", 
                 color=red_line, fontsize=12, fontweight="bold", alpha=0.95, zorder=5)
        
        ax1.set_xlabel("Сутки эксперимента (Pisum sativum, Когорта №3 «Терминальная засуха»)", 
                       fontsize=15, fontweight="bold", color=text_color, labelpad=10)
        ax1.set_ylabel("Индекс водного стресса CWSI (0.0 — 1.0)", 
                       fontsize=16, fontweight="bold", color=red_line, labelpad=12)
        ax1.set_ylim(-0.06, 1.28)
        ax1.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax1.set_yticklabels(["0.0\n(Норма)", "0.2", "0.4", "0.6\n(Стресс)", "0.8", "1.0\n(Увядание)"], 
                            fontsize=12.5, color=red_line, fontweight="bold")
        ax1.tick_params(axis='y', colors=red_line, labelsize=12.5)
        ax1.tick_params(axis='x', colors=text_color, labelsize=13)
        ax1.set_xlim(0.5, 11.5)
        ax1.set_xticks(range(1, 12))
        ax1.set_xticklabels([f"День {d}" for d in range(1, 12)], fontsize=13, fontweight="semibold")

        ax2 = ax1.twinx()
        ax2.set_facecolor("none")
        ax2.set_ylim(0.48, 0.98)
        ax2.set_yticks([0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90])
        ax2.tick_params(axis='y', colors=blue_line, labelsize=12.5)
        ax2.set_ylabel("Спектральный вегетационный индекс NDVI", 
                       fontsize=16, fontweight="bold", color=blue_line, labelpad=14)

        ax2.axhline(0.70, color=blue_line, linestyle=":", linewidth=2.2, alpha=0.7, zorder=2)
        ax2.text(11.3, 0.675, "Оптический оптимум: NDVI ≥ 0.70", 
                 color=blue_line, fontsize=12, fontweight="bold", alpha=0.95, zorder=5, ha="right")

        # Draw dense curves up to current progress
        curr_len = max(2, int(curve_prog * len(dense_days)))
        sub_d = dense_days[:curr_len]
        sub_cwsi = dense_cwsi[:curr_len]
        sub_ndvi = dense_ndvi[:curr_len]
        
        ax1.plot(sub_d, sub_cwsi, color=red_line, linewidth=4.5, zorder=6)
        ax1.fill_between(sub_d, sub_cwsi, color=red_line, alpha=0.10, zorder=2)
        ax2.plot(sub_d, sub_ndvi, color=blue_line, linewidth=4.5, zorder=7)
        
        # Real day markers
        passed_days = days[days <= sub_d[-1]]
        passed_cwsi = cwsi[days <= sub_d[-1]]
        passed_ndvi = ndvi[days <= sub_d[-1]]
        if len(passed_days) > 0:
            ax1.plot(passed_days, passed_cwsi, "o", color=red_point, markersize=12,
                     markeredgecolor="#FFFFFF", markeredgewidth=2.2, zorder=8)
            ax2.plot(passed_days, passed_ndvi, "s", color=blue_point, markersize=12,
                     markeredgecolor="#FFFFFF", markeredgewidth=2.2, zorder=9)
            
        # Top banner
        if window_alpha_prog > 0.2:
            banner_text = "⚡ ОКНО УПРЕЖДЕНИЯ: 48 ЧАСОВ (2 СУТОК)\nЛатентная фаза: устьица закрыты, лист греется, но хлорофилл еще интактен!"
            ax1.text(5.5, 1.16, banner_text, 
                     color="#F59E0B",
                     fontsize=13.5, fontweight="bold", ha="center", va="center", multialignment="center",
                     bbox=dict(boxstyle="round,pad=0.6", facecolor=card_bg, edgecolor="#F59E0B", linewidth=2.2, alpha=window_alpha_prog),
                     zorder=10)

        # Annotations when progress >= 0.7
        if annot_prog > 0.3:
            ax1.annotate("Резкий взлет CWSI (0.29 → 1.00)\nСмыкание устьиц, остановка транспирации",
                         xy=(5.85, 0.55), xytext=(2.2, 0.36),
                         arrowprops=dict(facecolor=red_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                         fontsize=12, fontweight="bold", color=red_line,
                         bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=red_line, linewidth=1.8),
                         zorder=12)

            ax2.annotate("NDVI стабилен (0.75 – 0.81)\nОптика «не видит» скрытый стресс",
                         xy=(7.1, 0.79), xytext=(8.1, 0.88),
                         arrowprops=dict(facecolor=blue_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                         fontsize=12, fontweight="bold", color=blue_line,
                         bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=blue_line, linewidth=1.8),
                         zorder=12)

            ax2.annotate("Запоздалый спад NDVI (до 0.62)\nНекроз и необратимое увядание",
                         xy=(9.0, 0.622), xytext=(8.6, 0.525),
                         arrowprops=dict(facecolor=blue_line, edgecolor="#FFFFFF", shrink=0.08, width=2.5, headwidth=9),
                         fontsize=12, fontweight="bold", color=blue_line,
                         bbox=dict(boxstyle="round,pad=0.45", facecolor=card_bg, edgecolor=blue_line, linewidth=1.8),
                         zorder=12)

        for spine in ax1.spines.values():
            spine.set_color(border_color)
            spine.set_linewidth(1.5)
        for spine in ax2.spines.values():
            spine.set_color(border_color)
            spine.set_linewidth(1.5)

        fig.text(0.5, 0.952, "ФИЗИОЛОГИЧЕСКАЯ АСИНХРОНИЯ: ТЕРМИЧЕСКИЙ vs СПЕКТРАЛЬНЫЙ СИГНАЛ", 
                 fontsize=21, fontweight="heavy", color=text_color, ha="center")
        fig.text(0.5, 0.918, "Динамика ранней реакции устьичного аппарата (CWSI) относительно оптического индекса (NDVI)", 
                 fontsize=14, color=subtext_color, ha="center", fontweight="medium")

        hud_text = (
            "  ●  КРАСНАЯ КРИВАЯ: CWSI (Тепловизор + SHT30) — Стресс на 4–5 сутки      │      "
            "■  СИНЯЯ КРИВАЯ: NDVI (NoIR 660/850 нм) — Реакция лишь на 8–9 сутки (Δt = 48 ч)  "
        )
        fig.text(0.5, 0.045, hud_text,
                 fontsize=12, fontweight="bold", color=text_color,
                 ha="center", va="center",
                 bbox=dict(boxstyle="round,pad=0.55", facecolor=card_bg, edgecolor=card_border, linewidth=1.5, alpha=0.98))

        # Convert figure to numpy RGB frame
        fig.canvas.draw()
        rgba_img = np.asarray(fig.canvas.buffer_rgba())
        bgr_frame = cv2.cvtColor(rgba_img, cv2.COLOR_RGBA2BGR)
        plt.close(fig)
        
        # Write 3 duplicate frames (each step = 0.1s at 30 fps)
        for _ in range(3):
            writer.write(bgr_frame)
            
    writer.release()
    print(f"Generated animation: {video_out}")


make_chart("dark")
make_chart("light")
make_animation("dark")
