import os
import sys
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

src_folder = Path(r"C:\Users\Администратор\Documents\Проект_Большие_Вызовы_2026_NDVI\04_Фотоархив_и_Медиа\Агротехнологии фото\Фотосессия\Видео пайки и отладки")
repo_dir = Path(__file__).resolve().parent.parent
out_media_dir = repo_dir / "media" / "process"
out_media_dir.mkdir(parents=True, exist_ok=True)

final_video_path = out_media_dir / "alice_soldering_and_debugging.mp4"

# 1. Определение сегментов и титров
segments = [
    {
        "file": "document_5429457721550221344.mp4",
        "start": 1.0,
        "end": 4.2,
        "caption": "1. Подготовка и зачистка монтажной проводки"
    },
    {
        "file": "document_5429457721550221346.mp4",
        "start": 5.0,
        "end": 9.5,
        "caption": "2. Пайка узлов стробирования подсветки (Red / NIR)"
    },
    {
        "file": "document_5429457721550221356.mp4",
        "start": 1.5,
        "end": 5.0,
        "caption": "3. Коммутация силовой шины и релейного блока"
    },
    {
        "file": "document_5429457721550221355.mp4",
        "start": 3.5,
        "end": 7.5,
        "caption": "4. Электроконтроль цепей цифровым мультиметром"
    },
    {
        "file": "document_5429457721550221357.mp4",
        "start": 3.0,
        "end": 7.8,
        "caption": "5. Контроль времени включения реле и стабильности питания LED"
    }
]

# Шрифты для титров
font_path = "C:/Windows/Fonts/arialbd.ttf"
if not os.path.exists(font_path):
    font_path = "C:/Windows/Fonts/arial.ttf"
font = ImageFont.truetype(font_path, 26)

temp_dir = repo_dir / "temp_montage"
temp_dir.mkdir(parents=True, exist_ok=True)

processed_clips = []

print("[*] Обработка сегментов и наложение титров...")

for idx, seg in enumerate(segments):
    in_file = src_folder / seg["file"]
    clip_tmp = temp_dir / f"clip_{idx}.mp4"
    
    cap = cv2.VideoCapture(str(in_file))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    
    start_frame = int(seg["start"] * fps)
    end_frame = int(seg["end"] * fps)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(str(clip_tmp), fourcc, 30.0, (1280, 720))
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    current_frame = start_frame
    
    while current_frame <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Resize to exactly 1280x720 if needed
        if frame.shape[1] != 1280 or frame.shape[0] != 720:
            frame = cv2.resize(frame, (1280, 720))
            
        # Наложение полупрозрачной плашки внизу с титрами
        overlay = frame.copy()
        cv2.rectangle(overlay, (40, 640), (1240, 695), (15, 23, 42), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        cv2.rectangle(frame, (40, 640), (1240, 695), (0, 164, 153), 2)
        
        # Отрисовка текста через PIL для корректной кириллицы
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        draw.text((60, 650), seg["caption"], font=font, fill=(255, 255, 255))
        frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
        out_writer.write(frame)
        current_frame += 1
        
    cap.release()
    out_writer.release()
    processed_clips.append(clip_tmp)
    print(f"  [+] Сегмент {idx+1}/{len(segments)} сформирован: {seg['caption']}")

# Создание concat списка для ffmpeg
concat_txt = temp_dir / "concat_list.txt"
with open(concat_txt, "w", encoding="utf-8") as f:
    for cp in processed_clips:
        f.write(f"file '{cp.resolve().as_posix()}'\n")

print("[*] Финальная склейка и сжатие в H.264 через FFmpeg...")
cmd = [
    ffmpeg_exe,
    "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", str(concat_txt),
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "22",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    str(final_video_path)
]

res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    v_size = os.path.getsize(final_video_path) / (1024 * 1024)
    print(f"[+] Монтаж завершен успешно: {final_video_path} (Размер: {v_size:.2f} МБ)")
else:
    print(f"[-] Ошибка FFmpeg: {res.stderr.decode('utf-8', errors='ignore')}")

# Очистка временных клипов
import shutil
shutil.rmtree(temp_dir, ignore_errors=True)

# 2. Экспорт 4 ключевых эталонных фотографий
print("[*] Экспорт эталонных стоп-кадров...")

stills = [
    ("document_5429457721550221344.mp4", 2.0, "01_подготовка_проводки_стриппер.jpg"),
    ("document_5429457721550221346.mp4", 7.0, "02_пайка_через_лупу_микропаяльник.jpg"),
    ("document_5429457721550221355.mp4", 5.5, "03_прозвонка_цепей_мультиметр.jpg"),
    ("document_5429457721550221357.mp4", 4.5, "04_отладка_строба_осциллограф.jpg"),
]

for vid_name, sec, out_name in stills:
    cap = cv2.VideoCapture(str(src_folder / vid_name))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(sec * fps))
    ret, frame = cap.read()
    if ret:
        out_p = out_media_dir / out_name
        # cv2 imwrite with unicode path via imencode
        is_success, im_buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if is_success:
            im_buf.tofile(str(out_p))
            print(f"  [+] Фото сохранено: {out_name}")
    cap.release()

# Мастер-фото общего плана
master_photo_src = src_folder / "photo_5429457722010182170_y.jpg"
if master_photo_src.exists():
    shutil.copyfile(str(master_photo_src), str(out_media_dir / "05_рабочее_место_инженера_общий_план.jpg"))
    print("  [+] Мастер-фото скопировано: 05_рабочее_место_инженера_общий_план.jpg")

print("[+] Все материалы готовы к интеграции!")
