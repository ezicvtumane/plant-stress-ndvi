# -*- coding: utf-8 -*-
"""
Генератор официального печатного бланка протокола лабораторных измерений (Формат А4 альбомный / книжный).
Разработан для Ковалевой Алисы (Всероссийский конкурс «Большие вызовы»).
"""

import os
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

HTML_OUT = os.path.join(DOCS_DIR, "Бланк_лабораторного_протокола_А4.html")
PDF_OUT = os.path.join(DOCS_DIR, "Бланк_лабораторного_протокола_А4.pdf")
MD_OUT = os.path.join(DOCS_DIR, "БЛАНК_ПРОТОКОЛА_ИЗМЕРЕНИЙ.md")

HTML_CONTENT = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Лабораторный журнал измерений — Бланк протокола А4</title>
<style>
    @page {
        size: A4 portrait;
        margin: 8mm 10mm 8mm 10mm;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 8pt;
        color: #0f172a;
        line-height: 1.2;
        background: #fff;
        margin: 0;
        padding: 0;
    }
    .header-box {
        text-align: center;
        border-bottom: 2px solid #008276;
        padding-bottom: 4px;
        margin-bottom: 6px;
    }
    .header-title {
        font-size: 13pt;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: #008276;
        text-transform: uppercase;
        margin: 0;
    }
    .header-sub {
        font-size: 8.5pt;
        color: #334155;
        font-weight: 600;
        margin: 2px 0 0 0;
    }
    .header-meta {
        font-size: 7.5pt;
        color: #64748b;
        margin-top: 1px;
    }
    .session-card {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 5px 7px;
        margin-bottom: 7px;
        background: #f8fafc;
    }
    .session-meta-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 7.8pt;
        font-weight: 600;
        margin-bottom: 4px;
        color: #1e293b;
        border-bottom: 1px dashed #cbd5e1;
        padding-bottom: 3px;
    }
    table.data-tbl {
        width: 100%;
        border-collapse: collapse;
        font-size: 7.2pt;
        background: #fff;
    }
    table.data-tbl th, table.data-tbl td {
        border: 1px solid #94a3b8;
        padding: 3px 2px;
        text-align: center;
    }
    table.data-tbl th {
        background: #f1f5f9;
        font-weight: 700;
        color: #1e293b;
        font-size: 7pt;
    }
    .col-cassette {
        text-align: left !important;
        font-weight: 700;
        padding-left: 4px !important;
        white-space: nowrap;
    }
    .tag-k1 { color: #047857; }
    .tag-k2 { color: #6d28d9; }
    .tag-k3 { color: #be123c; }
    .tag-k4 { color: #b45309; }
    .tag-k5 { color: #1d4ed8; }
    
    .status-guide {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 5px;
        padding: 4px 6px;
        font-size: 6.8pt;
        color: #334155;
        margin-bottom: 6px;
        line-height: 1.35;
    }
    .notes-box {
        border: 1px solid #cbd5e1;
        border-radius: 5px;
        padding: 4px 6px;
        font-size: 7.2pt;
        margin-bottom: 6px;
    }
    .notes-line {
        border-bottom: 1px dotted #94a3b8;
        height: 14px;
        margin-top: 2px;
    }
    .footer-row {
        display: flex;
        justify-content: space-between;
        font-size: 6.8pt;
        color: #64748b;
        border-top: 1px solid #e2e8f0;
        padding-top: 3px;
    }
</style>
</head>
<body>

<div class="header-box">
    <div class="header-title">📋 Лабораторный журнал измерений</div>
    <div class="header-sub">Оптико-электронный комплекс активной двухволновой спектрофотометрии и термографии</div>
    <div class="header-meta"><b>Ковалева Алиса Ивановна</b> | ГБОУ СОШ №282 Кировского района СПб | Всероссийский конкурс «Большие вызовы» 2026/2027</div>
</div>

<!-- СЕАНС 1 (УТРЕННИЙ ЗАМЕР) -->
<div class="session-card">
    <div class="session-meta-row">
        <span><b>Дата:</b> _______________</span>
        <span><b>Время:</b> _________</span>
        <span><b>Замер №:</b> ______</span>
        <span><b>Культура:</b> [ ] Горох  [ ] Огурец</span>
        <span><b>Этап:</b> 1 / 2</span>
        <span><b>День опыта:</b> Д____</span>
        <span><b>Подпись:</b> _________</span>
    </div>
    <table class="data-tbl">
        <thead>
            <tr>
                <th style="width:17%;">Кассета (когорта)</th>
                <th style="width:4.5%;">ArUco</th>
                <th style="width:7.5%;">Масса, г</th>
                <th style="width:6.5%;">Wпочв, %</th>
                <th style="width:6.5%;">Tбокс, °C</th>
                <th style="width:6.5%;">RHбокс, %</th>
                <th style="width:6.5%;">Tпод., °C</th>
                <th style="width:6.5%;">RHпод., %</th>
                <th style="width:6.5%;">Tлист, °C</th>
                <th style="width:6.5%;">ΔT, °C</th>
                <th style="width:8%;">NDVI</th>
                <th style="width:7.5%;">PLA, см²</th>
                <th style="width:7%;">Полив</th>
                <th style="width:7%;">Статус</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td class="col-cassette tag-k1">#1 Контроль (Оптимум)</td>
                <td><b>1</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k2">#2 Осмос (150 мМ NaCl)</td>
                <td><b>2</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k3">#3 Засуха (Водный дефицит)</td>
                <td><b>3</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k4">#4 Превенция (Полив по ΔT)</td>
                <td><b>4</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k5">#5 Реакция (Визуальн. увядание)</td>
                <td><b>5</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette" style="color:#64748b;">— Дополнительный замер</td>
                <td></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
        </tbody>
    </table>
</div>

<!-- СЕАНС 2 (ВЕЧЕРНИЙ ЗАМЕР) -->
<div class="session-card">
    <div class="session-meta-row">
        <span><b>Дата:</b> _______________</span>
        <span><b>Время:</b> _________</span>
        <span><b>Замер №:</b> ______</span>
        <span><b>Культура:</b> [ ] Горох  [ ] Огурец</span>
        <span><b>Этап:</b> 1 / 2</span>
        <span><b>День опыта:</b> Д____</span>
        <span><b>Подпись:</b> _________</span>
    </div>
    <table class="data-tbl">
        <thead>
            <tr>
                <th style="width:17%;">Кассета (когорта)</th>
                <th style="width:4.5%;">ArUco</th>
                <th style="width:7.5%;">Масса, г</th>
                <th style="width:6.5%;">Wпочв, %</th>
                <th style="width:6.5%;">Tбокс, °C</th>
                <th style="width:6.5%;">RHбокс, %</th>
                <th style="width:6.5%;">Tпод., °C</th>
                <th style="width:6.5%;">RHпод., %</th>
                <th style="width:6.5%;">Tлист, °C</th>
                <th style="width:6.5%;">ΔT, °C</th>
                <th style="width:8%;">NDVI</th>
                <th style="width:7.5%;">PLA, см²</th>
                <th style="width:7%;">Полив</th>
                <th style="width:7%;">Статус</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td class="col-cassette tag-k1">#1 Контроль (Оптимум)</td>
                <td><b>1</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k2">#2 Осмос (150 мМ NaCl)</td>
                <td><b>2</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k3">#3 Засуха (Водный дефицит)</td>
                <td><b>3</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k4">#4 Превенция (Полив по ΔT)</td>
                <td><b>4</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette tag-k5">#5 Реакция (Визуальн. увядание)</td>
                <td><b>5</b></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr>
                <td class="col-cassette" style="color:#64748b;">— Дополнительный замер</td>
                <td></td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
        </tbody>
    </table>
</div>

<!-- ДОПОЛНИТЕЛЬНЫЕ / ПОВТОРНЫЕ ЗАМЕРЫ -->
<div class="session-card" style="margin-bottom:5px;">
    <div style="font-size:7.5pt; font-weight:700; color:#334155; margin-bottom:3px;">
        🔬 Дополнительные / повторные / контрольные замеры:
    </div>
    <table class="data-tbl">
        <thead>
            <tr>
                <th style="width:17%;">Кассета / Примечание</th>
                <th style="width:4.5%;">ArUco</th>
                <th style="width:7.5%;">Масса, г</th>
                <th style="width:6.5%;">Wпочв, %</th>
                <th style="width:6.5%;">Tбокс, °C</th>
                <th style="width:6.5%;">RHбокс, %</th>
                <th style="width:6.5%;">Tпод., °C</th>
                <th style="width:6.5%;">RHпод., %</th>
                <th style="width:6.5%;">Tлист, °C</th>
                <th style="width:6.5%;">ΔT, °C</th>
                <th style="width:8%;">NDVI</th>
                <th style="width:7.5%;">PLA, см²</th>
                <th style="width:7%;">Полив</th>
                <th style="width:7%;">Статус</th>
            </tr>
        </thead>
        <tbody>
            <tr><td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
            <tr><td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
            <tr><td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
        </tbody>
    </table>
</div>

<!-- ПАМЯТКА КОДОВ И СТАТУСОВ -->
<div class="status-guide">
    <b>Коды визуального статуса:</b> 
    <b>Тургор:</b> <b>У</b> — упругий (норма) | <b>СВ</b> — слегка вялый | <b>П</b> — поникший | <b>СУ</b> — сильное увядание. &nbsp;|&nbsp; 
    <b>Цвет:</b> <b>З</b> — насыщенно-зелёный | <b>Ж</b> — желтизна | <b>Х</b> — хлороз | <b>Н</b> — краевой некроз → <i>пример записи: «У/З» или «П/Х»</i>.<br>
    <b>Полив:</b> объём (мл) + состав (<b>В</b> = отстоянная вода, <b>S</b> = 150 мМ NaCl, <b>0</b> = пропуск полива). &nbsp;|&nbsp; 
    <b>Градиент температуры:</b> <b>&Delta;T = T<sub>листа</sub> &minus; T<sub>под.</sub></b> (опорная температура берется с датчика на подоконнике, где растут растения). Масса — лабораторные весы (точность 0.1 г).
</div>

<!-- ПРИМЕЧАНИЯ -->
<div class="notes-box">
    <b>Примечания / агротехнические действия / калибровка:</b>
    <div class="notes-line"></div>
    <div class="notes-line"></div>
</div>

<div class="footer-row">
    <span>Заполнять ручкой. Каждая строка = замер одной кассеты. Обязательно дублировать в электронный журнал станции: <b>http://192.168.0.23:8000</b></span>
    <span>Лист ____ из ____ &nbsp;|&nbsp; Проект <b>plant-stress-ndvi</b> &bull; github.com/ezicvtumane/plant-stress-ndvi</span>
</div>

</body>
</html>
"""

with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)
print("[OK] Saved HTML:", HTML_OUT)

# Markdown summary
MD_CONTENT = """# 📋 ЛАБОРАТОРНЫЙ ЖУРНАЛ ИЗМЕРЕНИЙ
### Оптико-электронный комплекс активной двухволновой спектрофотометрии и термографии
**Ковалева Алиса Ивановна** | ГБОУ СОШ №282 Кировского района СПб | Большие вызовы 2026/2027

---

### Бланк протокола физиологических замеров (Сеанс 1 / Сеанс 2)

**Дата:** `__________________` &nbsp;&nbsp;&nbsp;&nbsp; **Время:** `_________` &nbsp;&nbsp;&nbsp;&nbsp; **Замер №:** `_________` &nbsp;&nbsp;&nbsp;&nbsp; **Подпись:** `___________`  
**Культура:** горох / огурец &nbsp;&nbsp;&nbsp;&nbsp; **Этап:** 1 (горох) / 2 (огурец) &nbsp;&nbsp;&nbsp;&nbsp; **День опыта:** `Д____`

| Кассета (когорта) | ArUco | Масса, г | $W_{\\text{почв}}$, % | $T_{\\text{бокс}}$, °C | $RH_{\\text{бокс}}$, % | $T_{\\text{под.}}$, °C | $RH_{\\text{под.}}$, % | $T_{\\text{лист}}$, °C | $\\Delta T$, °C | NDVI | PLA, см² | Полив | Статус |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1 Контроль (Оптимум)** | **1** | | | | | | | | | | | | |
| **#2 Осмос (150 мМ NaCl)** | **2** | | | | | | | | | | | | |
| **#3 Засуха (Водный дефицит)** | **3** | | | | | | | | | | | | |
| **#4 Превенция (Полив по $\\Delta T$)** | **4** | | | | | | | | | | | | |
| **#5 Реакция (Визуальн. увядание)** | **5** | | | | | | | | | | | | |
| *— Дополнительный замер* | | | | | | | | | | | | | |

---

### Памятка кодов и формул
* **Коды визуального статуса:**
  * **Тургор:** `У` — упругий (норма) | `СВ` — слегка вялый | `П` — поникший | `СУ` — сильное увядание.
  * **Цвет:** `З` — зелёный | `Ж` — желтизна | `Х` — хлороз | `Н` — краевой некроз → *пример: «У/З» или «П/Х»*.
* **Полив:** объем (мл) + состав (`В` = вода, `S` = 150 мМ NaCl, `0` = пропуск полива).
* **Градиент температуры:** $\\mathbf{\\Delta T = T_{\\text{листа}} - T_{\\text{под.}}}$ *(опорная температура берется с подоконника, где расположены растения, чтобы исключить паразитный нагрев от электроники бокса)*.
* **Масса кассеты:** лабораторные электронные весы (точность 0.1 г).

---
*Каждая строка = один замер одной кассеты. Дублировать в электронный веб-журнал станции: `http://192.168.0.23:8000`.*
"""

with open(MD_OUT, "w", encoding="utf-8") as f:
    f.write(MD_CONTENT)
print("[OK] Saved Markdown:", MD_OUT)

# Compile PDF via Chromium / Chrome if available
for ch_cmd in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "chromium", r"C:\Program Files\Google\Chrome\Application\chrome.exe"]:
    try:
        cmd = [
            ch_cmd,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--print-to-pdf={PDF_OUT}",
            HTML_OUT
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if os.path.exists(PDF_OUT) and os.path.getsize(PDF_OUT) > 1000:
            print(f"[OK] Generated PDF ({os.path.getsize(PDF_OUT)} bytes): {PDF_OUT}")
            break
    except Exception:
        continue

print("=== Protocol generator completed ===")
