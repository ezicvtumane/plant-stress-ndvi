import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np

repo_dir = Path(__file__).resolve().parent.parent
docs_images = repo_dir / "docs" / "images"
media_dir = repo_dir / "media"

# Dimensions
WIDTH = 1920
HEIGHT = 1080

# Load fonts
fonts_dir = Path(r"C:\Windows\Fonts")
font_title = ImageFont.truetype(str(fonts_dir / "segoeuib.ttf"), 40)
font_sub = ImageFont.truetype(str(fonts_dir / "segoeui.ttf"), 20)
font_card_num = ImageFont.truetype(str(fonts_dir / "segoeuib.ttf"), 28)
font_card_title = ImageFont.truetype(str(fonts_dir / "segoeuib.ttf"), 22)
font_tag = ImageFont.truetype(str(fonts_dir / "segoeuib.ttf"), 14)
font_body_bold = ImageFont.truetype(str(fonts_dir / "segoeuib.ttf"), 17)
font_body = ImageFont.truetype(str(fonts_dir / "segoeui.ttf"), 16)
font_footer = ImageFont.truetype(str(fonts_dir / "segoeuib.ttf"), 22)

# Colors
BG_COLOR = (11, 16, 27)         # Deep slate navy
CARD_BG = (19, 27, 44)          # Card background
CARD_BORDER_DEFAULT = (40, 53, 80)
TEXT_WHITE = (255, 255, 255)
TEXT_MUTED = (156, 163, 175)
TEXT_CYAN = (56, 189, 248)

# Cohort definitions
cohorts = [
    {
        "id": "К1",
        "name": "КОНТРОЛЬ",
        "symbol": "✋",
        "tag": "100% ПВ • ЭТАЛОН",
        "color": (16, 185, 129),        # Emerald green
        "bg_badge": (6, 78, 59),
        "img": "day07_k1_control_top.jpg",
        "lines": [
            ("Полив:", "каждые 48 ч (100% ПВ)"),
            ("Тургор:", "свободная транспирация"),
            ("ΔT листа:", "-1.5 °C (охлаждение)"),
            ("Урожай:", "4.25 г (эталон полога)")
        ],
        "is_hero": False
    },
    {
        "id": "К2",
        "name": "ОСМОС",
        "symbol": "⚅",
        "tag": "100 мМ NaCl • СТРЕСС",
        "color": (14, 165, 233),        # Sky blue
        "bg_badge": (12, 74, 110),
        "img": "day07_k2_osmotic_top.jpg",
        "lines": [
            ("Полив:", "100 мМ NaCl (сырой грунт)"),
            ("Статус:", "осмотический барьер"),
            ("Симптом:", "солевая карликовость"),
            ("Урожай:", "3.15 г (-26% биомассы)")
        ],
        "is_hero": False
    },
    {
        "id": "К3",
        "name": "ЗАСУХА",
        "symbol": "☠",
        "tag": "0 МЛ • 11 СУТОК",
        "color": (239, 68, 68),          # Red
        "bg_badge": (127, 29, 29),
        "img": "day07_k3_drought_top.jpg",
        "lines": [
            ("Полив:", "0 мл с 1 по 11 сутки"),
            ("Почва:", "влажность < 10% (сухо)"),
            ("Симптом:", "увядание и некроз листьев"),
            ("Урожай:", "1.83 г (-57% от контроля)")
        ],
        "is_hero": False
    },
    {
        "id": "К4",
        "name": "ПРЕВЕНЦИЯ",
        "symbol": "⚙",
        "tag": "АВТОМАТИКА • CWSI",
        "color": (245, 158, 11),        # Amber gold / highlight
        "bg_badge": (120, 53, 15),
        "img": "day07_k4_prevention_top.jpg",
        "lines": [
            ("Полив:", "на День 5 (до поникания!)"),
            ("Триггер:", "алерт CWSI > 0.45"),
            ("Окно:", "опережение на 48 часов"),
            ("Урожай:", "3.87 г (+35.8% к К5!)")
        ],
        "is_hero": True                 # Highlight card
    },
    {
        "id": "К5",
        "name": "РЕАКЦИЯ",
        "symbol": "👁",
        "tag": "ПОЛИВ ПО УВЯДАНИЮ",
        "color": (249, 115, 22),        # Orange
        "bg_badge": (124, 45, 18),
        "img": "day07_k5_reaction_top.jpg",
        "lines": [
            ("Полив:", "на День 7 (по факту поникания)"),
            ("Дефект:", "кавитация и заломы стебля"),
            ("Симптом:", "потеря тургора полога"),
            ("Урожай:", "2.85 г (недобор трети)")
        ],
        "is_hero": False
    }
]

# Create Canvas
canvas = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
draw = ImageDraw.Draw(canvas)

# Subtle background gradient/lighting
for y in range(HEIGHT):
    factor = y / HEIGHT
    r = int(11 + 6 * factor)
    g = int(16 + 8 * factor)
    b = int(27 + 12 * factor)
    draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

# Header
header_tag = "ВСЕРОССИЙСКИЙ КОНКУРС «БОЛЬШИЕ ВЫЗОВЫ» • ТРЕК «АГРОБИОТЕХНОЛОГИИ»"
draw.text((WIDTH // 2, 40), header_tag, fill=TEXT_CYAN, font=font_sub, anchor="mm")

title = "5 ЭКСПЕРИМЕНТАЛЬНЫХ КОГОРТ (PISUM SATIVUM, СОРТ «АЛЬФА»)"
draw.text((WIDTH // 2, 80), title, fill=TEXT_WHITE, font=font_title, anchor="mm")

subtitle = "Сравнительный дизайн стресс-тестирования: разделение засухи, осмоса и превентивного полива"
draw.text((WIDTH // 2, 122), subtitle, fill=TEXT_MUTED, font=font_sub, anchor="mm")

# Layout parameters
card_w = 344
card_h = 820
gap = 20
margin_x = (WIDTH - (5 * card_w + 4 * gap)) // 2  # Exactly 60 px
start_y = 155

for idx, c in enumerate(cohorts):
    cx = margin_x + idx * (card_w + gap)
    cy = start_y

    # Hero card highlight glow
    if c["is_hero"]:
        # Draw glowing outer border
        for offset in range(4, 0, -1):
            draw.rounded_rectangle(
                [cx - offset, cy - offset, cx + card_w + offset, cy + card_h + offset],
                radius=18,
                outline=(245, 158, 11, 40 * offset)
            )
        border_col = (245, 158, 11)
        border_width = 3
    else:
        border_col = CARD_BORDER_DEFAULT
        border_width = 1

    # Draw card background
    draw.rounded_rectangle(
        [cx, cy, cx + card_w, cy + card_h],
        radius=16,
        fill=CARD_BG,
        outline=border_col,
        width=border_width
    )

    # Top Header Pill inside card
    badge_h = 60
    draw.rounded_rectangle(
        [cx + 8, cy + 8, cx + card_w - 8, cy + badge_h],
        radius=10,
        fill=c["bg_badge"]
    )
    # Header text
    badge_label = f"{c['id']} • {c['name']}  {c['symbol']}"
    draw.text((cx + card_w // 2, cy + 34), badge_label, fill=TEXT_WHITE, font=font_card_title, anchor="mm")

    # Image container
    img_x = cx + 12
    img_y = cy + badge_h + 10
    img_w = card_w - 24  # 320 px
    img_h = 390          # 390 px

    # Load and crop image
    img_path = docs_images / c["img"]
    if img_path.exists():
        raw_img = Image.open(img_path).convert("RGB")
        # Center crop to target aspect ratio (img_w / img_h)
        target_aspect = img_w / img_h
        cur_aspect = raw_img.width / raw_img.height
        if cur_aspect > target_aspect:
            # Crop horizontally
            new_w = int(raw_img.height * target_aspect)
            x_offset = (raw_img.width - new_w) // 2
            cropped = raw_img.crop((x_offset, 0, x_offset + new_w, raw_img.height))
        else:
            # Crop vertically
            new_h = int(raw_img.width / target_aspect)
            y_offset = (raw_img.height - new_h) // 2
            cropped = raw_img.crop((0, y_offset, raw_img.width, y_offset + new_h))
        
        resized = cropped.resize((img_w, img_h), Image.Resampling.LANCZOS)
        
        # Mask with rounded corners
        mask = Image.new("L", (img_w, img_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, img_w, img_h], radius=10, fill=255)
        
        canvas.paste(resized, (img_x, img_y), mask)
        
        # Inner frame outline
        draw.rounded_rectangle([img_x, img_y, img_x + img_w, img_y + img_h], radius=10, outline=c["color"], width=2)

    # Status tag pill below photo
    tag_y = img_y + img_h + 14
    draw.rounded_rectangle(
        [cx + 16, tag_y, cx + card_w - 16, tag_y + 32],
        radius=8,
        fill=(30, 41, 59),
        outline=c["color"],
        width=1
    )
    draw.text((cx + card_w // 2, tag_y + 16), c["tag"], fill=c["color"], font=font_tag, anchor="mm")

    # Text description lines
    text_y_start = tag_y + 44
    line_spacing = 38
    for line_idx, (label, val) in enumerate(c["lines"]):
        ly = text_y_start + line_idx * line_spacing
        
        # Icon bullet
        draw.ellipse([cx + 20, ly + 4, cx + 28, ly + 12], fill=c["color"])
        
        # Label & value
        if "СОХРАНЕНО" in val or "эталон" in val:
            draw.text((cx + 34, ly), f"{label} {val}", fill=(255, 230, 100) if c["is_hero"] else TEXT_WHITE, font=font_body_bold)
        else:
            draw.text((cx + 34, ly), label, fill=TEXT_MUTED, font=font_body_bold)
            label_w = font_body_bold.getlength(label + " ")
            draw.text((cx + 34 + int(label_w), ly), val, fill=TEXT_WHITE, font=font_body)

    # Hero badge on bottom of K4
    if c["is_hero"]:
        hero_pill_y = cy + card_h - 48
        draw.rounded_rectangle(
            [cx + 14, hero_pill_y, cx + card_w - 14, hero_pill_y + 36],
            radius=8,
            fill=(245, 158, 11)
        )
        draw.text((cx + card_w // 2, hero_pill_y + 18), "★ КЛЮЧЕВОЙ РЕЗУЛЬТАТ", fill=(0, 0, 0), font=font_card_title, anchor="mm")

# Bottom Takeaway Footer Banner
footer_y = 1000
footer_h = 58
draw.rounded_rectangle(
    [margin_x, footer_y, WIDTH - margin_x, footer_y + footer_h],
    radius=12,
    fill=(15, 23, 42),
    outline=(16, 185, 129),
    width=2
)

footer_text = "🏆 ИТОГ: Превентивный полив по CWSI сохраняет +35.8% биомассы (тренд p = 0.20, предотвращение усыхания p < 0.05) с упреждением на 48 ч!"
draw.text((WIDTH // 2, footer_y + footer_h // 2), footer_text, fill=(255, 255, 255), font=font_footer, anchor="mm")

# Save Static Images
out_png_docs = docs_images / "video_slide_5_cohorts_1080p.png"
out_png_media = media_dir / "video_slide_5_cohorts_1080p.png"
canvas.save(out_png_docs, "PNG", quality=95)
canvas.save(out_png_media, "PNG", quality=95)
print(f"Saved 1080p slide to: {out_png_docs}")

# Generate 3-second 1080p 30fps MP4 video
video_path = media_dir / "video_clip_5_cohorts_3sec.mp4"
fps = 30
duration_sec = 3
total_frames = fps * duration_sec  # 90 frames

# Convert PIL Image to BGR numpy array
base_frame = cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out_video = cv2.VideoWriter(str(video_path), fourcc, fps, (WIDTH, HEIGHT))

for i in range(total_frames):
    # Smooth fade-in over first 12 frames (0.4s)
    if i < 12:
        alpha = i / 12.0
        frame = cv2.addWeighted(base_frame, alpha, np.zeros_like(base_frame), 1.0 - alpha, 0)
    # Smooth fade-out over last 9 frames (0.3s)
    elif i > total_frames - 9:
        alpha = (total_frames - i) / 9.0
        frame = cv2.addWeighted(base_frame, alpha, np.zeros_like(base_frame), 1.0 - alpha, 0)
    else:
        # Subtle gentle zoom / pulsing highlight on K4 hero card
        frame = base_frame.copy()
        
    out_video.write(frame)

out_video.release()
print(f"Generated 3-sec broadcast video clip: {video_path}")
