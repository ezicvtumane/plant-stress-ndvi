# -*- coding: utf-8 -*-
"""
Генератор чистого РАБОЧЕГО ДНЕВНИКА ЭКСПЕРИМЕНТАТОРА для Ковалевой Алисы.
Это пустой бланк-журнал для ручного (или цифрового) ввода реальных данных
без каких-либо симулированных или предзаполненных значений.
"""

import os
import subprocess
import shutil
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

BASE_DIR = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi"
DOCS_DIR = os.path.join(BASE_DIR, "docs")
USER_DOCS = r"C:\Users\Администратор\Documents"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def set_cell_background(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tc_pr.append(shd)

def set_table_borders(table, color="94a3b8", sz="4", val="single"):
    tbl_pr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tblBorders>'
    )
    tbl_pr.append(borders)

def build_alisa_journal_docx(output_path):
    doc = docx.Document()
    
    # Альбомная ориентация для максимального удобства внесения данных по колонкам
    section = doc.sections[0]
    section.orientation = docx.enum.section.WD_ORIENT.LANDSCAPE
    section.page_width = Inches(11.69)   # A4 альбомная
    section.page_height = Inches(8.27)
    section.top_margin = Inches(0.4)
    section.bottom_margin = Inches(0.4)
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.4)
    
    style_normal = doc.styles['Normal']
    font = style_normal.font
    font.name = 'Arial'
    font.size = Pt(9)
    font.color.rgb = RGBColor(0x0f, 0x17, 0x2a)
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(2)
    
    # Заголовок
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("РАБОЧИЙ ДНЕВНИК НАУЧНОГО ИССЛЕДОВАНИЯ\n")
    r.bold = True
    r.font.size = Pt(14)
    r.font.color.rgb = RGBColor(0x00, 0x82, 0x76)
    
    r2 = p.add_run("Первичный протокол измерений физиологических параметров стресса растений\n")
    r2.font.size = Pt(10)
    r2.font.italic = True
    r2.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
    
    # Карточка исследователя (компактная)
    t_meta = doc.add_table(rows=2, cols=4)
    t_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t_meta, color="cbd5e1")
    
    meta_info = [
        [("Исследователь:", " Ковалева Алиса Ивановна, 10 класс"), 
         ("Культура:", " Горох посевной (Pisum sativum), сорт «Альфа»"),
         ("Дата посева:", " 29 сентября 2026 г."),
         ("Старт стресс-опыта:", " 9 октября 2026 г. (через 10 дней)")],
        [("Научный руководитель:", " Ковалев Иван Викторович"),
         ("Выборка:", " n = 45 (5 когорт по 9 растений) + Стенд №0"),
         ("Субстрат:", " Торф верховой с перлитом (pH 6.0)"),
         ("Изоляция соли:", " Кассета №2 в отдельном лотке-поддоне!")]
    ]
    
    for r_idx, row in enumerate(meta_info):
        for c_idx, (k, v) in enumerate(row):
            cell = t_meta.rows[r_idx].cells[c_idx]
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            rk = p.add_run(k)
            rk.bold = True
            rk.font.size = Pt(8.5)
            rv = p.add_run(v)
            rv.font.size = Pt(8.5)
            if "отдельном" in v:
                rv.bold = True
                rv.font.color.rgb = RGBColor(0xb9, 0x1c, 0x1c)
                
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    
    # --------------------------------------------------------------------------
    # РАЗДЕЛ 1: ФАЗА 0 (ПРОРАЩИВАНИЕ И ВЕГЕТАЦИЯ, 29.09 — 08.10)
    # --------------------------------------------------------------------------
    h1 = doc.add_paragraph()
    r = h1.add_run("РАЗДЕЛ I. ФАЗА ПРОРАЩИВАНИЯ И ВЕГЕТАЦИИ (ДНИ 0–9: с 29 сентября по 8 октября 2026 г.)")
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = RGBColor(0x0f, 0x76, 0x6e)
    
    p_desc0 = doc.add_paragraph()
    p_desc0.paragraph_format.line_spacing = 1.05
    p_desc0.add_run(
        "Инструкция Алисе: В этот период все кассеты поливаются только чистой отстоянной водой. "
        "Кассета №2 уже стоит в своем отдельном лотке. Записывай время полива, объем, всхожесть и наблюдения. "
        "3–5 октября на стенде №0 настраиваем оптику."
    ).font.size = Pt(8.5)
    
    headers_phase0 = [
        "Дата / День", "Кассета (когорта)", "Время полива", "Объем полива (мл)", 
        "Чем полито", "Масса кассеты M (г)", "Всхожесть (из 9 шт)", 
        "Tвозд / RHвозд", "Фенологические наблюдения (петельки, семядоли, листья)", "Подпись"
    ]
    
    # Создаем чистую таблицу на 12 строк (по строке на день или для сводной записи)
    t_phase0 = doc.add_table(rows=11, cols=len(headers_phase0))
    t_phase0.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t_phase0, color="94a3b8")
    
    for j, h in enumerate(headers_phase0):
        cell = t_phase0.rows[0].cells[j]
        set_cell_background(cell, "e2e8f0")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.0)
        r.font.color.rgb = RGBColor(0x0f, 0x76, 0x6e)
        
    # Дни 0–9 (чистые строки для Алисы)
    days_labels = [
        ("29.09 (День 0, Вт)", "К1–К5 (все)", "Посев проростков с корешками 1–2 см. Кассета №2 в отдельный лоток!"),
        ("30.09 (День 1, Ср)", "К1–К5 (все)", ""),
        ("01.10 (День 2, Чт)", "К1–К5 (все)", ""),
        ("02.10 (День 3, Пт)", "К1–К5 (все)", ""),
        ("03.10 (День 4, Сб)", "К1–К5 + Ст№0", "Прибытие посылки с диодами и датчиками! Монтаж"),
        ("04.10 (День 5, Вс)", "К1–К5 + Ст№0", ""),
        ("05.10 (День 6, Пн)", "К1–К5 + Ст№0", "Юстировка оптики NoIR и OCR на Стенде №0"),
        ("06.10 (День 7, Вт)", "К1–К5 (все)", ""),
        ("07.10 (День 8, Ср)", "К1–К5 (все)", ""),
        ("08.10 (День 9, Чт)", "К1–К5 (все)", "Фоновый замер перед стартом засухи (NDVI_init, масса M0)")
    ]
    
    for r_idx, (day_lbl, cas_lbl, note_init) in enumerate(days_labels):
        row = t_phase0.rows[r_idx + 1]
        row.cells[0].paragraphs[0].add_run(day_lbl).font.size = Pt(8)
        row.cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        row.cells[1].paragraphs[0].add_run(cas_lbl).font.size = Pt(8)
        row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if note_init:
            row.cells[8].paragraphs[0].add_run(note_init).font.size = Pt(7.5)
            row.cells[8].paragraphs[0].runs[0].font.italic = True
            
        # Задаем высоту строк для удобного рукописного заполнения
        tr_pr = row._tr.get_or_add_trPr()
        tr_height = parse_xml(f'<w:trHeight {nsdecls("w")} w:val="320" w:hRule="atLeast"/>')
        tr_pr.append(tr_height)
        
    doc.add_page_break()
    
    # --------------------------------------------------------------------------
    # РАЗДЕЛ 2: ФАЗА 1 (АКТИВНЫЙ СТРЕСС-ОПЫТ, СТАРТ 09.10.2026)
    # --------------------------------------------------------------------------
    h2 = doc.add_paragraph()
    r = h2.add_run("РАЗДЕЛ II. БЛАНК ЕЖЕДНЕВНЫХ ЗАМЕРОВ СТРЕСС-ОПЫТА (СТАРТ 09.10.2026, 09:00)")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(0x0f, 0x76, 0x6e)
    
    p_inst = doc.add_paragraph()
    p_inst.paragraph_format.line_spacing = 1.05
    p_inst.add_run(
        "Инструкция Алисе: Замеры проводятся 2 раза в день: УТРОМ (09:00–10:00) и ВЕЧЕРОМ (18:00–19:00). "
        "В каждую строчку заноси показания весов, экрана тепловизора UTi120S, датчиков станции и веб-интерфейса. "
        "К1: полив водой по графику. К2: полив ТОЛЬКО раствором NaCl 150 мМ (8.76 г соли на 1 л воды). "
        "К3: реанимационный полив водой (25 мл) ПРИ ПЕРВОМ АЛЕРТЕ СТАНЦИИ (ΔT > +0.8°C). "
        "К4: полив водой (25 мл) ТОЛЬКО ПРИ ВИДИМОМ ПОНИКАНИИ ЛИСТЬЕВ. К5: без полива."
    ).font.size = Pt(8.0)
    
    headers_stress = [
        "Дата и Время", "Когорта (Кассета)", "Полив (мл)", "Чем полито (вода/соль/0)", 
        "Масса M (г)", "Wпочвы (%)", "Vпочвы (В)", "Tлиста (°C)", "Tвозд (°C)", "ΔT (°C)", 
        "RHвозд (%)", "NDVI ср.", "PLA (см²)", "Тургор / Внешнее состояние", "Подпись"
    ]
    
    # Создаем сводный бланк замеров на 4 страницы (по 2 дня на страницу, 4 замера в день = 20 строк на страницу)
    days_stress_schedule = [
        "ДЕНЬ 10 (09.10, Пт) — СТАРТ СТРЕСС-ОПЫТА",
        "ДЕНЬ 11 (10.10, Сб) — РАЗВИТИЕ СТРЕССА / ОЖИДАНИЕ АЛЕРТА К3",
        "ДЕНЬ 12 (11.10, Вс) — АЛЕРТ И ПРЕВЕНТИВНЫЙ ПОЛИВ К3",
        "ДЕНЬ 13 (12.10, Пн) — ПОТЕРЯ ТУРГОРА И ПОЛИВ К4 (ВИЗУАЛЬНЫЙ КОНТРОЛЬ)",
        "ДЕНЬ 14 (13.10, Вт) — РЕПАРАЦИЯ И СРАВНЕНИЕ БИОМАССЫ",
        "ДЕНЬ 15 (14.10, Ср) — РЕПАРАЦИЯ / ТЕРМИНАЛЬНЫЙ НЕКРОЗ К5",
        "ДЕНЬ 16 (15.10, Чт) — ФИНАЛЬНЫЙ СКРИНИНГ РЕПАРАЦИИ",
        "ДЕНЬ 17 (16.10, Пт) — ИТОГОВЫЙ ЗАМЕР И ВЗВЕШИВАНИЕ БИОМАССЫ"
    ]
    
    cohorts_list = [
        ("№1: 🌱 Контроль (Оптимум)", "water"),
        ("№2: 🧂 Засоление (150 мМ NaCl)", "salt"),
        ("№3: 🔬 Превентивная регидратация", "device"),
        ("№4: 👁️ Традиционный визуальный контроль", "eyes"),
        ("№5: ⚠️ Терминальная засуха", "drought")
    ]
    
    for day_idx, day_title in enumerate(days_stress_schedule):
        # Подзаголовок дня
        p_day = doc.add_paragraph()
        p_day.paragraph_format.space_before = Pt(4)
        p_day.paragraph_format.space_after = Pt(2)
        r_day = p_day.add_run(f"📅 {day_title}")
        r_day.bold = True
        r_day.font.size = Pt(9.5)
        r_day.font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)
        
        # Таблица дня: 10 строк (5 кассет УТРО + 5 кассет ВЕЧЕР) + 1 шапка
        t_day = doc.add_table(rows=11, cols=len(headers_stress))
        t_day.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t_day, color="94a3b8")
        
        # Шапка
        for j, h in enumerate(headers_stress):
            cell = t_day.rows[0].cells[j]
            set_cell_background(cell, "f1f5f9")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(7.5)
            r.font.color.rgb = RGBColor(0x0f, 0x76, 0x6e)
            
        # Заполняем метки кассет и времени
        # Строки 1..5: Утро (09:00)
        for c_i, (c_name, c_type) in enumerate(cohorts_list):
            row = t_day.rows[c_i + 1]
            tr_pr = row._tr.get_or_add_trPr()
            tr_height = parse_xml(f'<w:trHeight {nsdecls("w")} w:val="280" w:hRule="atLeast"/>')
            tr_pr.append(tr_height)
            
            # Дата/время
            p0 = row.cells[0].paragraphs[0]
            p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r0 = p0.add_run("Утро 09:00")
            r0.font.size = Pt(7.5)
            
            # Когорта
            p1 = row.cells[1].paragraphs[0]
            r1 = p1.add_run(c_name)
            r1.font.size = Pt(7.5)
            if c_type == "water":
                r1.font.color.rgb = RGBColor(0x04, 0x78, 0x57)
            elif c_type == "salt":
                r1.font.color.rgb = RGBColor(0xb4, 0x53, 0x09)
            elif c_type == "device":
                r1.font.color.rgb = RGBColor(0x02, 0x84, 0xc7)
            elif c_type == "eyes":
                r1.font.color.rgb = RGBColor(0x6d, 0x28, 0xd9)
            elif c_type == "drought":
                r1.font.color.rgb = RGBColor(0xb9, 0x1c, 0x1c)
                
        # Строки 6..10: Вечер (18:00)
        for c_i, (c_name, c_type) in enumerate(cohorts_list):
            row = t_day.rows[c_i + 6]
            tr_pr = row._tr.get_or_add_trPr()
            tr_height = parse_xml(f'<w:trHeight {nsdecls("w")} w:val="280" w:hRule="atLeast"/>')
            tr_pr.append(tr_height)
            
            p0 = row.cells[0].paragraphs[0]
            p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r0 = p0.add_run("Вечер 18:00")
            r0.font.size = Pt(7.5)
            
            p1 = row.cells[1].paragraphs[0]
            r1 = p1.add_run(c_name)
            r1.font.size = Pt(7.5)
            if c_type == "water":
                r1.font.color.rgb = RGBColor(0x04, 0x78, 0x57)
            elif c_type == "salt":
                r1.font.color.rgb = RGBColor(0xb4, 0x53, 0x09)
            elif c_type == "device":
                r1.font.color.rgb = RGBColor(0x02, 0x84, 0xc7)
            elif c_type == "eyes":
                r1.font.color.rgb = RGBColor(0x6d, 0x28, 0xd9)
            elif c_type == "drought":
                r1.font.color.rgb = RGBColor(0xb9, 0x1c, 0x1c)
                
        # Разделитель страниц каждые 2 дня
        if day_idx % 2 == 1 and day_idx < len(days_stress_schedule) - 1:
            doc.add_page_break()
            
    doc.save(output_path)
    print(f"[OK] Generated Clean DOCX: {output_path}")

def make_clean_html_journal():
    cohorts_list = [
        ("№1: 🌱 Контроль (Оптимум)", "color: #047857; font-weight: bold;"),
        ("№2: 🧂 Засоление (150 мМ NaCl)", "color: #b45309; font-weight: bold;"),
        ("№3: 🔬 Превентивная регидратация", "color: #0284c7; font-weight: bold;"),
        ("№4: 👁️ Традиционный визуальный контроль", "color: #6d28d9; font-weight: bold;"),
        ("№5: ⚠️ Терминальная засуха", "color: #b91c1c; font-weight: bold;")
    ]
    
    days_stress_schedule = [
        "ДЕНЬ 10 (09.10, Пт) — СТАРТ СТРЕСС-ОПЫТА",
        "ДЕНЬ 11 (10.10, Сб) — РАЗВИТИЕ СТРЕССА / ОЖИДАНИЕ АЛЕРТА К3",
        "ДЕНЬ 12 (11.10, Вс) — АЛЕРТ И ПРЕВЕНТИВНЫЙ ПОЛИВ К3",
        "ДЕНЬ 13 (12.10, Пн) — ПОТЕРЯ ТУРГОРА И ПОЛИВ К4 (ВИЗУАЛЬНЫЙ КОНТРОЛЬ)",
        "ДЕНЬ 14 (13.10, Вт) — РЕПАРАЦИЯ И СРАВНЕНИЕ БИОМАССЫ",
        "ДЕНЬ 15 (14.10, Ср) — РЕПАРАЦИЯ / ТЕРМИНАЛЬНЫЙ НЕКРОЗ К5",
        "ДЕНЬ 16 (15.10, Чт) — ФИНАЛЬНЫЙ СКРИНИНГ РЕПАРАЦИИ",
        "ДЕНЬ 17 (16.10, Пт) — ИТОГОВЫЙ ЗАМЕР И ВЗВЕШИВАНИЕ БИОМАССЫ"
    ]

    html_days_tables = []
    for day_idx, day_title in enumerate(days_stress_schedule):
        rows_html = []
        # Утро
        for c_name, c_style in cohorts_list:
            rows_html.append(f"""
            <tr>
                <td style="font-weight: bold;">Утро 09:00</td>
                <td style="{c_style} text-align: left; padding-left: 4px;">{c_name}</td>
                <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
                <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
                <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
            </tr>
            """)
        # Вечер
        for c_name, c_style in cohorts_list:
            rows_html.append(f"""
            <tr>
                <td style="font-weight: bold;">Вечер 18:00</td>
                <td style="{c_style} text-align: left; padding-left: 4px;">{c_name}</td>
                <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
                <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
                <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
            </tr>
            """)
            
        page_break_cls = "page-break" if (day_idx % 2 == 1 and day_idx < len(days_stress_schedule) - 1) else ""
        
        table_block = f"""
        <div class="{page_break_cls}">
            <h3 style="color: #1e3a8a; margin: 8px 0 3px 0; font-size: 9.5pt;">📅 {day_title}</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 7%;">Время</th>
                        <th style="width: 15%;">Когорта</th>
                        <th style="width: 6%;">Полив мл</th>
                        <th style="width: 7%;">Чем полито</th>
                        <th style="width: 6%;">M (г)</th>
                        <th style="width: 5%;">Wпочв</th>
                        <th style="width: 5%;">Vпочв</th>
                        <th style="width: 6%;">Tлист</th>
                        <th style="width: 6%;">Tвозд</th>
                        <th style="width: 5%;">ΔT</th>
                        <th style="width: 5%;">RH%</th>
                        <th style="width: 6%;">NDVI</th>
                        <th style="width: 6%;">PLA см²</th>
                        <th style="width: 11%;">Тургор / Симптомы</th>
                        <th style="width: 4%;">Подп.</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
        """
        html_days_tables.append(table_block)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Рабочий дневник исследователя — Ковалева Алиса</title>
<style>
    @page {{
        size: A4 landscape;
        margin: 10mm 10mm 10mm 10mm;
    }}
    body {{
        font-family: Arial, sans-serif;
        font-size: 8pt;
        color: #0f172a;
        line-height: 1.15;
        background: #fff;
        margin: 0;
        padding: 0;
    }}
    .header {{
        text-align: center;
        border-bottom: 2px solid #008276;
        padding-bottom: 4px;
        margin-bottom: 8px;
    }}
    h1 {{
        color: #008276;
        font-size: 13pt;
        margin: 0 0 2px 0;
        text-transform: uppercase;
    }}
    .subtitle {{
        font-size: 8.5pt;
        color: #475569;
        font-style: italic;
    }}
    .meta-box {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 8px;
        font-size: 8pt;
    }}
    .meta-box td {{
        padding: 3px 6px;
        border: 1px solid #cbd5e1;
    }}
    .meta-box td.label {{
        background: #f1f5f9;
        font-weight: bold;
        width: 16%;
        color: #0f766e;
    }}
    .alert-banner {{
        background: #fef2f2;
        border-left: 4px solid #ef4444;
        padding: 4px 8px;
        font-size: 8pt;
        color: #991b1b;
        margin-bottom: 8px;
        font-weight: bold;
    }}
    h2 {{
        font-size: 10pt;
        color: #0f766e;
        border-bottom: 1px solid #94a3b8;
        padding-bottom: 2px;
        margin: 8px 0 4px 0;
        text-transform: uppercase;
    }}
    table.data-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 7pt;
        margin-bottom: 6px;
    }}
    table.data-table th {{
        background: #e2e8f0;
        color: #0f766e;
        border: 1px solid #94a3b8;
        padding: 3px 1px;
        text-align: center;
        font-weight: bold;
    }}
    table.data-table td {{
        border: 1px solid #94a3b8;
        padding: 3px 1px;
        text-align: center;
        height: 14px;
    }}
    .page-break {{
        page-break-before: always;
    }}
</style>
</head>
<body>

<div class="header">
    <h1>📋 Рабочий дневник экспериментатора</h1>
    <div class="subtitle">Чистый бланк для ручного заполнения Алисой Ковалевой при проведении замеров</div>
</div>

<div class="alert-banner">
    ⚠️ ПРАВИЛО ИЗОЛЯЦИИ: Кассета №2 (Засоление 150 мМ NaCl) находится в ОТДЕЛЬНОМ ЛОТКЕ-ИЗОЛЯТОРЕ! Полив производить только раствором соли 150 мМ (8.76 г NaCl/л).
</div>

<table class="meta-box">
    <tr>
        <td class="label">Исследователь:</td>
        <td><b>Ковалева Алиса Ивановна</b>, 10 класс (Науч. рук.: Ковалев И. В.)</td>
        <td class="label">Культура:</td>
        <td>Горох посевной (<i>Pisum sativum</i>), сорт «Альфа»</td>
    </tr>
    <tr>
        <td class="label">Дата посева:</td>
        <td><b>29 сентября 2026 г.</b> (Стенд №0 высеян 22.09.2026)</td>
        <td class="label">Старт стресс-опыта:</td>
        <td><b>9 октября 2026 г.</b> (через 10 дней от момента посева)</td>
    </tr>
</table>

<h2>Раздел I. Фаза проращивания и вегетации (Дни 0–9: с 29.09 по 08.10.2026)</h2>
<p style="font-size: 7.5pt; margin: 0 0 4px 0;">
    <i>Инструкция Алисе:</i> Вносить реальные данные полива чистой водой (10–15 мл/кассету), всхожести и высоты растений. 3–5 октября на Стенде №0 настраиваем NoIR-камеру и тепловизор.
</p>

<table class="data-table">
    <thead>
        <tr>
            <th style="width: 10%;">Дата / День</th>
            <th style="width: 10%;">Кассета</th>
            <th style="width: 8%;">Время полива</th>
            <th style="width: 8%;">Полив (мл)</th>
            <th style="width: 9%;">Чем полито</th>
            <th style="width: 8%;">Масса М (г)</th>
            <th style="width: 9%;">Всхожесть (из 9)</th>
            <th style="width: 10%;">Tвозд / RHвозд</th>
            <th style="width: 22%;">Фенонаблюдения (петельки, листья, высота)</th>
            <th style="width: 6%;">Подпись</th>
        </tr>
    </thead>
    <tbody>
        <tr><td>29.09 (Д0)</td><td>К1–К5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td style="text-align:left; font-size:6.5pt;">Посев семян с корешками 1–2 см. Соль в отдельный лоток!</td><td>&nbsp;</td></tr>
        <tr><td>30.09 (Д1)</td><td>К1–К5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>01.10 (Д2)</td><td>К1–К5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>02.10 (Д3)</td><td>К1–К5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>03.10 (Д4)</td><td>К1–К5 + Ст0</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td style="text-align:left; font-size:6.5pt;">Посылка прибыла! Монтаж оптики. Тест стенда №0</td><td>&nbsp;</td></tr>
        <tr><td>04.10 (Д5)</td><td>К1–К5 + Ст0</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>05.10 (Д6)</td><td>К1–К5 + Ст0</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td style="text-align:left; font-size:6.5pt;">Юстировка NoIR и OCR на Стенде №0</td><td>&nbsp;</td></tr>
        <tr><td>06.10 (Д7)</td><td>К1–К5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>07.10 (Д8)</td><td>К1–К5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>08.10 (Д9)</td><td>К1–К5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td style="text-align:left; font-size:6.5pt;">Предстартовый замер фона (NDVI_init, масса M0)</td><td>&nbsp;</td></tr>
    </tbody>
</table>

<div class="page-break"></div>

<h2>Раздел II. Бланк ежедневных замеров стресс-опыта (Старт 09.10.2026, 09:00)</h2>
<p style="font-size: 7.5pt; margin: 0 0 4px 0;">
    <i>Регламент Алисы:</i> Замеры 2 раза в день: <b>УТРО (09:00)</b> и <b>ВЕЧЕР (18:00)</b>. 
    <b>Кассета №3:</b> восстановительный полив (25 мл) ПРИ ПЕРВОМ АЛЕРТЕ СТАНЦИИ (ΔT > +0.8°C). 
    <b>Кассета №4:</b> полив (25 мл) ТОЛЬКО ПРИ ВИДИМОМ ПОНИКАНИИ ЛИСТЬЕВ. 
    <b>Кассета №5:</b> без полива. <b>Кассета №2:</b> полив только раствором соли 150 мМ!
</p>

{''.join(html_days_tables)}

</body>
</html>
"""
    return html

def main():
    print("=== ГЕНЕРАЦИЯ ЧИСТОГО РАБОЧЕГО ДНЕВНИКА ДЛЯ АЛИСЫ ===")
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(USER_DOCS, exist_ok=True)
    
    # 1. Генерируем чистый Word DOCX
    docx_path = os.path.join(DOCS_DIR, "Рабочий_дневник_исследователя_Ковалева_Алиса.docx")
    user_docx_path = os.path.join(USER_DOCS, "Рабочий_дневник_исследователя_Ковалева_Алиса.docx")
    build_alisa_journal_docx(docx_path)
    shutil.copy2(docx_path, user_docx_path)
    print(f"[OK] Copied Clean DOCX to: {user_docx_path}")
    
    # 2. Генерируем чистый HTML
    html_path = os.path.join(DOCS_DIR, "Рабочий_дневник_исследователя_Ковалева_Алиса.html")
    html_content = make_clean_html_journal()
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] Saved Clean HTML: {html_path}")
    
    # 3. Генерируем чистый PDF для печати
    pdf_path = os.path.join(DOCS_DIR, "Рабочий_дневник_исследователя_Ковалева_Алиса.pdf")
    user_pdf_path = os.path.join(USER_DOCS, "Рабочий_дневник_исследователя_Ковалева_Алиса.pdf")
    if os.path.exists(CHROME_PATH):
        cmd = [
            CHROME_PATH,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode == 0 and os.path.exists(pdf_path):
            shutil.copy2(pdf_path, user_pdf_path)
            print(f"[OK] Saved Clean PDF: {pdf_path} ({os.path.getsize(pdf_path)/1024:.1f} KB)")
            print(f"[OK] Copied Clean PDF to: {user_pdf_path}")
            
    print("\n=======================================================")
    print("Чистый рабочий дневник для Алисы успешно создан!")
    print(f"Файлы размещены в:\n  1. {DOCS_DIR}\n  2. {USER_DOCS}")
    print("=======================================================")

if __name__ == "__main__":
    main()
