#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматическая проверка целостности ссылок на изображения в журнале Волны 2
(`data/experiments/exp_1792918800/measurements_wave2.csv`).

Классифицирует каждую ссылку `Opt_File` и `Thermal_File`:
- ok (найдено): файл существует, не пустой, валидный заголовок (JPEG/PNG/BMP),
  полностью декодируется Pillow (width > 0, height > 0), формат совпадает с расширением, префикс совпадает с ID.
- missing (отсутствует/повреждён): файл не найден, пустой (0 байт), содержит заглушку
  или не прошёл полное декодирование (битый/усечённый JPEG/PNG/BMP, нулевые размеры).
- ambiguous (неоднозначно): префикс имени не соответствует ID, несовпадение реального формата с расширением,
  либо один файл указан для разных ID.
- unlinked ('--'): явный прочерк в CSV (снимок ещё не привязан).
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional
from PIL import Image, ImageFile

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV = os.path.join(PROJECT_ROOT, "data", "experiments", "exp_1792918800", "measurements_wave2.csv")
DEFAULT_IMAGES_DIR = os.path.join(PROJECT_ROOT, "data", "experiments", "exp_1792918800", "images")

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".dib")
_CYR_TO_LAT = str.maketrans({"К": "K", "П": "P", "Р": "R"})


def _inspect_image_header(fpath: str) -> Dict[str, Any]:
    """Проверяет размер, сигнатуру, соответствие формата расширению и выполняет полное декодирование Pillow."""
    size = os.path.getsize(fpath)
    with open(fpath, "rb") as f:
        head = f.read(64)
    ext = os.path.splitext(fpath)[1].lower()
    if b"FAKE_JPEG_DATA_STREAM" in head or size == 0:
        return {"valid": False, "format": "corrupt_or_dummy", "size_bytes": size}
    if head.startswith(b"\xff\xd8\xff"):
        sig_fmt = "jpeg"
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        sig_fmt = "png"
    elif head.startswith(b"BM"):
        sig_fmt = "bmp"
    else:
        return {"valid": False, "format": "unknown", "size_bytes": size}

    # Полное декодирование через Pillow без модификации исходного файла
    prev_trunc = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        with Image.open(fpath) as im_verify:
            im_verify.verify()
        with Image.open(fpath) as im:
            pil_raw_fmt = (im.format or "").upper()
            im.load()
            width, height = im.size
    except Exception as exc:
        return {
            "valid": False,
            "format": f"decode_error:{sig_fmt}",
            "size_bytes": size,
            "decode_error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = prev_trunc

    if width <= 0 or height <= 0:
        return {
            "valid": False,
            "format": f"invalid_dimensions:{width}x{height}",
            "size_bytes": size,
            "width": width,
            "height": height,
        }

    pil_fmt = {"JPEG": "jpeg", "PNG": "png", "BMP": "bmp", "DIB": "bmp"}.get(pil_raw_fmt, pil_raw_fmt.lower())
    ext_map = {"jpeg": (".jpg", ".jpeg"), "png": (".png",), "bmp": (".bmp", ".dib")}
    ext_ok = (sig_fmt == pil_fmt) and (ext in ext_map.get(pil_fmt, ()))
    return {
        "valid": True,
        "format": pil_fmt,
        "signature_format": sig_fmt,
        "ext_ok": ext_ok,
        "size_bytes": size,
        "width": width,
        "height": height,
    }


def verify_image_links(
    csv_path: str = DEFAULT_CSV,
    images_dir: str = DEFAULT_IMAGES_DIR,
    date_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Проверяет все ссылки Opt_File и Thermal_File в CSV и формирует структурированный отчёт."""
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if date_filter:
        rows = [r for r in rows if (r.get("Timestamp") or "").strip().startswith(date_filter)]

    # Отслеживаем дублирующиеся ссылки между разными ID
    file_to_ids: Dict[str, set] = defaultdict(set)
    for row in rows:
        pid = (row.get("ID") or "").strip().upper().translate(_CYR_TO_LAT)
        for col in ("Opt_File", "Thermal_File"):
            fname = (row.get(col) or "").strip()
            if fname and fname != "--":
                file_to_ids[fname].add(pid)

    entries: List[Dict[str, Any]] = []
    counts = {"ok": 0, "missing": 0, "ambiguous": 0, "unlinked": 0}
    referenced_files = set()

    for row_idx, row in enumerate(rows, start=1):
        ts = (row.get("Timestamp") or "").strip()
        pid = (row.get("ID") or "").strip().upper().translate(_CYR_TO_LAT)
        for col in ("Opt_File", "Thermal_File"):
            fname = (row.get(col) or "").strip()
            if not fname or fname == "--":
                counts["unlinked"] += 1
                entries.append({
                    "row": row_idx, "timestamp": ts, "pot_id": pid, "column": col,
                    "filename": fname or "--", "status": "unlinked", "reason": "Прочерк в CSV",
                })
                continue

            referenced_files.add(fname)
            fpath = os.path.join(images_dir, fname)
            if not os.path.isfile(fpath):
                counts["missing"] += 1
                entries.append({
                    "row": row_idx, "timestamp": ts, "pot_id": pid, "column": col,
                    "filename": fname, "status": "missing", "reason": "Файл не найден на диске",
                })
                continue

            hdr = _inspect_image_header(fpath)
            if not hdr["valid"]:
                counts["missing"] += 1
                entries.append({
                    "row": row_idx, "timestamp": ts, "pot_id": pid, "column": col,
                    "filename": fname, "status": "missing",
                    "reason": f"Невалидный или пустой файл ({hdr['format']}, {hdr['size_bytes']} Б)",
                    **hdr,
                })
                continue

            issues = []
            if pid and not fname.upper().startswith(f"{pid}_"):
                issues.append(f"префикс имени не соответствует ID '{pid}'")
            if not hdr["ext_ok"]:
                issues.append(f"расширение не соответствует сигнатуре '{hdr['format']}'")
            if len(file_to_ids[fname]) > 1:
                issues.append(f"файл привязан сразу к нескольким ID: {sorted(file_to_ids[fname])}")

            if issues:
                counts["ambiguous"] += 1
                entries.append({
                    "row": row_idx, "timestamp": ts, "pot_id": pid, "column": col,
                    "filename": fname, "status": "ambiguous",
                    "reason": "; ".join(issues), **hdr,
                })
            else:
                counts["ok"] += 1
                entries.append({
                    "row": row_idx, "timestamp": ts, "pot_id": pid, "column": col,
                    "filename": fname, "status": "ok", "reason": "OK", **hdr,
                })

    disk_files = sorted(
        fn for fn in os.listdir(images_dir)
        if os.path.isfile(os.path.join(images_dir, fn)) and fn.lower().endswith(_IMAGE_EXTENSIONS)
    ) if os.path.isdir(images_dir) else []
    unreferenced = sorted(fn for fn in disk_files if fn not in referenced_files)

    healthy = counts["missing"] == 0 and counts["ambiguous"] == 0
    return {
        "healthy": healthy,
        "csv_path": csv_path,
        "images_dir": images_dir,
        "date_filter": date_filter,
        "rows_checked": len(rows),
        "counts": counts,
        "unreferenced_on_disk": unreferenced,
        "entries": entries,
    }


def _format_text_report(report: Dict[str, Any]) -> str:
    c = report["counts"]
    lines = [
        "=== АУДИТ ССЫЛОК НА ИЗОБРАЖЕНИЯ ВОЛНЫ 2 ===",
        f"CSV:       {report['csv_path']}",
        f"Каталог:   {report['images_dir']}",
        f"Фильтр:    {report['date_filter'] or 'все даты'}",
        f"Строк CSV: {report['rows_checked']}",
        f"Найдено (валидно):           {c['ok']}",
        f"Отсутствует / повреждено:    {c['missing']}",
        f"Неоднозначно / конфликт ID:  {c['ambiguous']}",
        f"Прочерк ('--'):              {c['unlinked']}",
        f"Файлов на диске вне CSV:     {len(report['unreferenced_on_disk'])}",
    ]
    for status_label, key in (("ОТСУТСТВУЕТ", "missing"), ("НЕОДНОЗНАЧНО", "ambiguous")):
        bad = [e for e in report["entries"] if e["status"] == key]
        if bad:
            lines.append(f"\n[{status_label}]")
            for item in bad:
                lines.append(f"  - строка {item['row']} ({item['timestamp']}, {item['pot_id']} {item['column']}): {item['filename']} -> {item['reason']}")
    lines.append("\nИТОГ: " + ("OK (битых и спорных ссылок нет)" if report["healthy"] else "ОБНАРУЖЕНЫ ПРОБЛЕМЫ ССЫЛОК"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка целостности ссылок на фото в measurements_wave2.csv")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Путь к measurements_wave2.csv")
    parser.add_argument("--images-dir", default=DEFAULT_IMAGES_DIR, help="Каталог images/")
    parser.add_argument("--date", default=None, help="Необязательный фильтр даты (например 2026-11-09)")
    parser.add_argument("--json", action="store_true", help="Вывести отчёт в JSON")
    args = parser.parse_args()

    report = verify_image_links(csv_path=args.csv, images_dir=args.images_dir, date_filter=args.date)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_format_text_report(report))
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
