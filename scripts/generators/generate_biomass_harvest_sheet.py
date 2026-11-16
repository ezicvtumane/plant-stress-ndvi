# -*- coding: utf-8 -*-
"""
Генератор официального двухстороннего печатного бланка:
«Акт и рабочий лист деструктивного сбора и сушки биомассы» (Волна 2, Огурец «Каскад»).
Лицевая сторона (Стр. 1): Технологический регламент СОП, паспорт условий и эталонные прогнозы феном-комплекса.
Оборотная сторона (Стр. 2): Полноразмерный рукописный бланк с крупными пустыми строками для заполнения ручкой.
"""

import os
import sys
import subprocess
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS_DIR = os.path.join(BASE_DIR, "docs", "wave2")
os.makedirs(DOCS_DIR, exist_ok=True)

CSV_PATH = os.path.join(BASE_DIR, "data", "experiments", "exp_1792918800", "measurements_wave2.csv")
HTML_OUT = os.path.join(DOCS_DIR, "ЛИСТ_ЖУРНАЛА_СБОР_БИОМАССЫ.html")
PDF_OUT = os.path.join(DOCS_DIR, "ЛИСТ_ЖУРНАЛА_СБОР_БИОМАССЫ.pdf")

df = pd.read_csv(CSV_PATH)
d6_plants = df[(df['Timestamp'].str.startswith('2026-11-15')) & (df['ID'].str[0].isin(['K', 'R', 'P']))].copy()

def get_block_num(pid):
    num = int(pid[1:]) if len(pid) > 1 and pid[1:].isdigit() else 0
    return 1 if num in (1, 2) else (2 if num in (3, 4) else 3)

d6_plants['Block_Num'] = d6_plants['ID'].apply(get_block_num)

# Порядок срезки по блокам: Блок 1 (K1, K2, P1, P2, R1, R2), Блок 2 (K3, K4, P3, P4, R3, R4), Блок 3 (K5, K6, P5, P6, R5, R6)
cohort_order = {'K': 1, 'P': 2, 'R': 3}
d6_plants['Cohort_Order'] = d6_plants['ID'].str[0].map(cohort_order)
d6_plants['Num'] = d6_plants['ID'].str[1:].astype(int)
d6_plants = d6_plants.sort_values(by=['Block_Num', 'Cohort_Order', 'Num']).reset_index(drop=True)

def calc_biomass_row(row):
    try:
        pla = float(row['Leaf_Area_cm2'])
    except:
        pla = 10.0
    cohort = row['ID'][0]
    try:
        turgor = float(row['Turgor_Score'])
    except:
        turgor = 4.0
    
    stem_base = 0.26
    fw_leaf = pla * 0.060
    fw_stem = stem_base + pla * 0.018
    fw_total = fw_leaf + fw_stem
    if cohort == 'R' and turgor < 4:
        fw_total *= 0.92
    
    dm_pct = 8.4 if cohort == 'K' else (8.8 if cohort == 'P' else 9.4)
    dw_mg = fw_total * 1000 * (dm_pct / 100.0)
    dw_g = dw_mg / 1000.0
    wc_pct = 100.0 - dm_pct
    cum_w = df[df['ID'] == row['ID']]['Water_Dose_ml'].astype(float).sum()
    wue = dw_mg / cum_w if cum_w > 0 else 0
    return pd.Series([round(fw_leaf, 3), round(fw_stem, 3), round(fw_total, 2), round(dw_g, 3), round(dw_mg, 1), round(dm_pct, 1), round(wc_pct, 1), round(wue, 2), round(cum_w, 1)],
                     index=['FW_leaf', 'FW_stem', 'FW_g', 'DW_g', 'DW_mg', 'DM_pct', 'WC_pct', 'WUE', 'Cum_W'])

b_df = d6_plants.apply(calc_biomass_row, axis=1)
d6_plants = pd.concat([d6_plants, b_df], axis=1)

def get_cohort_meta(pid):
    c = pid[0]
    if c == 'K':
        return 'Контроль', '#059669', '#ecfdf5', '#047857', 'badge-k'
    elif c == 'P':
        return 'Превенция', '#d97706', '#fffbeb', '#b45309', 'badge-p'
    elif c == 'R':
        return 'Реакция', '#2563eb', '#eff6ff', '#1d4ed8', 'badge-r'
    return 'Неизвестно', '#475569', '#f8fafc', '#334155', 'badge-x'

html = '''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Лист журнала сбора биомассы — Волна 2 (Лицевая сторона и Оборот)</title>
<style>
  @page {
    size: A4 landscape;
    margin: 7mm 9mm 7mm 9mm;
  }
  * {
    box-sizing: border-box;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #0f172a;
    background-color: #ffffff;
    font-size: 7.8pt;
    line-height: 1.25;
    margin: 0;
    padding: 0;
  }
  .page {
    page-break-after: always;
    page-break-inside: avoid;
    height: 196mm;
    max-height: 196mm;
    overflow: hidden;
    position: relative;
    clear: both;
  }
  .page:last-child {
    page-break-after: avoid;
  }
  .header-box {
    border-bottom: 2px solid #0f172a;
    padding-bottom: 2px;
    margin-bottom: 5px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .org-title {
    font-size: 7pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #475569;
    font-weight: 700;
  }
  .doc-title {
    font-size: 13pt;
    font-weight: 800;
    color: #0f172a;
    margin: 1px 0;
    line-height: 1.15;
  }
  .doc-subtitle {
    font-size: 8.5pt;
    color: #0284c7;
    font-weight: 600;
  }
  .stamp-box {
    text-align: right;
    font-size: 7pt;
    color: #334155;
    border: 1px dashed #64748b;
    padding: 2px 6px;
    border-radius: 4px;
    background-color: #f8fafc;
    line-height: 1.25;
  }
  .meta-grid {
    display: flex;
    gap: 8px;
    margin-bottom: 5px;
  }
  .meta-card {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px 6px;
    flex: 1;
    font-size: 7.2pt;
    line-height: 1.35;
  }
  .meta-title {
    font-weight: 700;
    color: #0f172a;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 2px;
    padding-bottom: 1px;
    text-transform: uppercase;
    font-size: 6.8pt;
  }
  
  /* Таблица ориентиров на Лицевой стороне */
  table.ref-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.2pt;
    margin-top: 3px;
    margin-bottom: 5px;
  }
  table.ref-table th {
    background-color: #0f172a;
    color: #ffffff;
    font-weight: 600;
    text-align: center;
    padding: 3px 2px;
    border: 1px solid #334155;
    font-size: 6.8pt;
    text-transform: uppercase;
    line-height: 1.15;
  }
  table.ref-table td {
    padding: 2px 3px;
    border: 1px solid #cbd5e1;
    text-align: center;
    height: 16px;
  }
  table.ref-table tr:nth-child(even) {
    background-color: #f8fafc;
  }
  table.ref-table tr.block-sep {
    border-top: 2px solid #0f172a;
  }

  /* Полноразмерная таблица для письма на Обороте */
  table.blank-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.5pt;
    margin-top: 3px;
    margin-bottom: 4px;
  }
  table.blank-table th {
    background-color: #0f172a;
    color: #ffffff;
    font-weight: 700;
    text-align: center;
    padding: 4px 2px;
    border: 1px solid #1e293b;
    font-size: 6.8pt;
    text-transform: uppercase;
    line-height: 1.15;
  }
  table.blank-table td {
    padding: 1px 3px;
    border: 1px solid #94a3b8;
    text-align: center;
    height: 25px; /* Просторная высота для рукописной записи цифр */
    vertical-align: middle;
  }
  table.blank-table tr:nth-child(even) {
    background-color: #fafafa;
  }
  table.blank-table tr.block-sep {
    border-top: 2.5px solid #0f172a;
  }
  .blank-cell {
    border-bottom: 1px dotted #94a3b8;
    height: 19px;
    width: 100%;
    display: block;
  }

  .badge {
    display: inline-block;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 6.5pt;
    font-weight: 700;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .badge-k { background-color: #dcfce7; color: #166534; border: 1px solid #86efac; }
  .badge-p { background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
  .badge-r { background-color: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
  
  .note-alert {
    background-color: #eff6ff;
    border-left: 3px solid #3b82f6;
    padding: 4px 6px;
    font-size: 7.2pt;
    margin: 3px 0;
    border-radius: 0 3px 3px 0;
    line-height: 1.3;
  }
  .footer-sig {
    margin-top: 6px;
    display: flex;
    justify-content: space-between;
    font-size: 7.2pt;
    border-top: 1px solid #94a3b8;
    padding-top: 3px;
  }
  .sig-line {
    border-bottom: 1px solid #475569;
    width: 130px;
    display: inline-block;
    margin: 0 3px;
  }
  .checklist {
    font-size: 7pt;
    line-height: 1.3;
    margin-top: 3px;
  }
  .checklist-item {
    display: inline-block;
    width: 49%;
    vertical-align: top;
  }
  .checkbox-box {
    display: inline-block;
    width: 9px;
    height: 9px;
    border: 1px solid #0f172a;
    margin-right: 4px;
    vertical-align: middle;
  }
</style>
</head>
<body>
'''

# ==================== СТРАНИЦА 1: ЛИЦЕВАЯ СТОРОНА (ОРИЕНТИРЫ И РЕГЛАМЕНТ) ====================
html += '''
<div class="page">
  <div class="header-box">
    <div>
      <div class="org-title">Министерство науки и высшего образования РФ | Тимирязевский научно-испытательный центр</div>
      <div class="doc-title">ЛИСТ СБОРА БИОМАССЫ (ЛИЦЕВАЯ СТОРОНА: ОРИЕНТИРЫ И СОП)</div>
      <div class="doc-subtitle">Опыт «Волна 2» (Огурец «Каскад», Cucumis sativus L., GRCBD 3×3×2, ID: exp_1792918800)</div>
    </div>
    <div class="stamp-box">
      <strong>ЛИСТ 1: СПРАВОЧНЫЙ</strong><br>
      Срез: +48ч регидратации<br>
      Норматив: ГОСТ 28561-90
    </div>
  </div>

  <div class="meta-grid">
    <div class="meta-card">
      <div class="meta-title">1. РЕГЛАМЕНТ СРЕЗКИ И ПРАВИЛО 60 СЕКУНД</div>
      • Срезка производится <strong>строго по блокам GRCBD</strong> (Блок 1 → Блок 2 → Блок 3) для исключения дневного дрейфа.<br>
      • Инструмент: острый скальпель, срез строго на уровне границы субстрата (корневая шейка).<br>
      • ⏱ <strong>КРИТИЧЕСКИЙ ЛИМИТ:</strong> Не более <strong>60 секунд</strong> от среза до закрытия крышки бюкса на аналитических весах!
    </div>
    <div class="meta-card">
      <div class="meta-title">2. РЕГЛАМЕНТ ТЕРМОСТАТИРОВАНИЯ И СУШКИ</div>
      • <strong>Фаза 1 (Инактивация ферментов):</strong> Шкаф <strong>105 ± 2 °C</strong> ровно 30 минут с открытыми крышками.<br>
      • <strong>Фаза 2 (Высушивание до const массы):</strong> Шкаф <strong>80 ± 2 °C</strong> в течение 20–24 часов.<br>
      • <strong>Охлаждение:</strong> Эксикатор с сухим силикагелем строго <strong>25–30 минут</strong> с закрытыми крышками перед взвешиванием.
    </div>
    <div class="meta-card" style="background:#f0fdf4; border-color:#86efac;">
      <div class="meta-title" style="color:#166534;">3. РАСЧЕТНЫЕ АГРОНОМИЧЕСКИЕ ФОРМУЛЫ</div>
      • Сырая масса побега: <strong>FW = M₁ - M₀</strong> (г)<br>
      • Сухая масса побега: <strong>DW = M₂ - M₀</strong> (г или мг = г × 1000)<br>
      • Содержание сухого вещества: <strong>DM (%) = (DW / FW) × 100 %</strong><br>
      • Эффективность использования воды: <strong>WUE = DW (мг) / Σ Полив (мл)</strong>
    </div>
  </div>

  <table class="ref-table">
    <thead>
      <tr>
        <th style="width:25px;">№</th>
        <th style="width:50px;">Блок GRCBD</th>
        <th style="width:30px;">ID</th>
        <th style="width:75px;">Когорта</th>
        <th style="width:40px;">Тургор</th>
        <th style="width:55px;">PLA феном<br>(см²)</th>
        <th style="width:65px; background:#1e293b;">FW пред.<br>(г, феном)</th>
        <th style="width:55px;">FW лист<br>(г, пред.)</th>
        <th style="width:55px;">FW стебель<br>(г, пред.)</th>
        <th style="width:65px; background:#1e293b;">DW пред.<br>(мг, феном)</th>
        <th style="width:55px; background:#1e293b;">DM пред.<br>(%, феном)</th>
        <th style="width:55px;">Σ Полив<br>(мл, факт)</th>
        <th style="width:65px; background:#047857;">WUE пред.<br>(мг/мл)</th>
        <th>Агрономические примечания к растению</th>
      </tr>
    </thead>
    <tbody>
'''

prev_block = None
for idx, r in d6_plants.iterrows():
    pid = str(r['ID'])
    b_num = r['Block_Num']
    c_name, col, bg_col, txt_col, badge_cls = get_cohort_meta(pid)
    pla = f"{float(r['Leaf_Area_cm2']):.2f}"
    turgor = str(r['Turgor_Score'])
    fw_pred = f"{r['FW_g']:.2f}"
    fw_l = f"{r['FW_leaf']:.3f}"
    fw_s = f"{r['FW_stem']:.3f}"
    dw_pred = f"{r['DW_mg']:.1f}"
    dm_pred = f"{r['DM_pct']:.1f}%"
    cum_w = f"{r['Cum_W']:.1f}"
    wue = f"{r['WUE']:.2f}"
    
    note = "Мощное развитие, высокая биомасса" if pid == 'K2' else ("Глубокий стресс, тургор 3, замедленный рост" if pid == 'R6' else ("Максимальная WUE, развитый листовой полог" if pid in ('P5', 'P6') else "Нормативное развитие"))

    sep_cls = 'block-sep' if prev_block is not None and b_num != prev_block else ''
    prev_block = b_num
    
    html += f'''
      <tr class="{sep_cls}">
        <td><strong>{idx+1}</strong></td>
        <td><strong>Блок {b_num}</strong></td>
        <td><strong>{pid}</strong></td>
        <td><span class="badge {badge_cls}">{c_name}</span></td>
        <td><strong>{turgor}</strong></td>
        <td>{pla}</td>
        <td style="font-weight:700; background:#f1f5f9;">{fw_pred}</td>
        <td>{fw_l}</td>
        <td>{fw_s}</td>
        <td style="font-weight:700; background:#f1f5f9;">{dw_pred}</td>
        <td style="background:#f1f5f9;">{dm_pred}</td>
        <td style="font-family:monospace;">{cum_w}</td>
        <td style="font-weight:700; color:{txt_col}; background:#f0fdf4;">{wue}</td>
        <td style="text-align:left; font-size:6.8pt;">{note}</td>
      </tr>
'''

html += '''
    </tbody>
  </table>

  <div class="note-alert" style="background:#fffbeb; border-left-color:#d97706;">
    <strong>ВНИМАНИЕ ОПЕРАТОРУ:</strong> На обороте данного листа расположен полноразмерный рукописный протокол со свободными разлинованными строками для заполнения фактических измерений при срезке и сушке. Сравнивайте получаемые результаты взвешивания $FW$ и $DW$ со справочными ориентирами данной таблицы.
  </div>

  <div class="footer-sig">
    <div><strong>Ответственный за калибровку комплекса:</strong> <span class="sig-line"></span> / ___________________ /</div>
    <div><strong>Ведущий агроном-исследователь:</strong> <span class="sig-line"></span> / ___________________ /</div>
    <div><strong>Дата формирования бланка:</strong> 15.11.2026</div>
  </div>
</div>
'''

# ==================== СТРАНИЦА 2: ОБОРОТНАЯ СТОРОНА (ЧИСТЫЙ БЛАНК ДЛЯ ПИСЬМА) ====================
html += '''
<div class="page">
  <div class="header-box">
    <div>
      <div class="org-title">Министерство науки и высшего образования РФ | Тимирязевский научно-испытательный центр</div>
      <div class="doc-title">РАБОЧИЙ ЖУРНАЛ СБОРА И СУШКИ БИОМАССЫ (ДЛЯ ЗАПОЛНЕНИЯ ОТ РУКИ)</div>
      <div class="doc-subtitle">Оборотная сторона листа | Опыт «Волна 2» (Cucumis sativus L., Огурец «Каскад», GRCBD 3×3×2)</div>
    </div>
    <div class="stamp-box">
      <strong>ОБОРОТ: РАБОЧИЙ</strong><br>
      Заполняется шариковой ручкой<br>
      Точность весов: 0.001 г
    </div>
  </div>

  <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:4px; padding:3px 8px; margin-bottom:4px; font-size:7.2pt; display:flex; justify-content:space-between; align-items:center;">
    <div><strong>Дата срезки:</strong> «_____» ____________ 2026 г. &nbsp;|&nbsp; <strong>Время:</strong> с _____ : _____ по _____ : _____</div>
    <div><strong>Условия в лаб.:</strong> T возд = _______ °C, &nbsp; Влажность RH = _______ %</div>
    <div><strong>Аналит. весы (инв. №):</strong> ______________________ &nbsp;|&nbsp; <strong>Суш. шкаф:</strong> ______________________</div>
  </div>

  <table class="blank-table">
    <thead>
      <tr>
        <th style="width:22px;">№</th>
        <th style="width:45px;">Блок</th>
        <th style="width:30px;">ID</th>
        <th style="width:65px;">Когорта</th>
        <th style="width:48px;">№ бюкса<br>(тары)</th>
        <th style="width:48px;">Время<br>срезки</th>
        <th style="width:72px;">M₀ пустой тары<br>(г, ±0.001)</th>
        <th style="width:72px;">M₁ тара + FW<br>(сырая, г)</th>
        <th style="width:68px; background:#047857;">FW факт.<br>(M₁ - M₀, г)</th>
        <th style="width:55px;">FW листа<br>(г, опция)</th>
        <th style="width:55px;">FW стебля<br>(г, опция)</th>
        <th style="width:72px;">M₂ тара + DW<br>(сухая, г)</th>
        <th style="width:68px; background:#047857;">DW факт.<br>(M₂ - M₀, мг)</th>
        <th style="width:55px; background:#b45309;">DM факт.<br>(DW/FW, %)</th>
        <th>Примечания и особые отметки<br>(дефекты, тургор, краевой ожог)</th>
      </tr>
    </thead>
    <tbody>
'''

prev_block = None
for idx, r in d6_plants.iterrows():
    pid = str(r['ID'])
    b_num = r['Block_Num']
    c_name, col, bg_col, txt_col, badge_cls = get_cohort_meta(pid)
    
    sep_cls = 'block-sep' if prev_block is not None and b_num != prev_block else ''
    prev_block = b_num
    
    html += f'''
      <tr class="{sep_cls}">
        <td><strong>{idx+1}</strong></td>
        <td><strong>Блок {b_num}</strong></td>
        <td><strong style="font-size:8.5pt;">{pid}</strong></td>
        <td><span class="badge {badge_cls}">{c_name}</span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td style="background:#f0fdf4;"><span class="blank-cell" style="border-bottom-color:#166534;"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td style="background:#f0fdf4;"><span class="blank-cell" style="border-bottom-color:#166534;"></span></td>
        <td style="background:#fffbeb;"><span class="blank-cell" style="border-bottom-color:#b45309;"></span></td>
        <td style="text-align:left;"><span class="blank-cell"></span></td>
      </tr>
'''

# Добавим 2 резервные строки (для контроля весов, калибровочного сосуда или лизиметра X0)
for res_idx in (1, 2):
    html += f'''
      <tr style="background:#fff7ed;">
        <td><strong>Р{res_idx}</strong></td>
        <td style="font-size:6.8pt; color:#c2410c;"><strong>Резерв</strong></td>
        <td><span class="blank-cell"></span></td>
        <td style="font-size:6.8pt; color:#c2410c;">Контроль / Х0</td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td><span class="blank-cell"></span></td>
        <td style="text-align:left;"><span class="blank-cell"></span></td>
      </tr>
'''

html += '''
    </tbody>
  </table>

  <div class="footer-sig">
    <div><strong>Срезку и взвешивание FW провел (Оператор):</strong> <span class="sig-line"></span> / ___________________ / Время: ___:___</div>
    <div><strong>Сушку и взвешивание DW провел (Лаборант):</strong> <span class="sig-line"></span> / ___________________ / Дата: ___.___.2026</div>
    <div><strong>Расчет DM% проверил (Агроном-исследователь):</strong> <span class="sig-line"></span> / ___________________ /</div>
  </div>
</div>
</body>
</html>
'''

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"[OK] Saved 2-sided Biomass Harvest Sheet HTML to: {HTML_OUT} ({len(html)} bytes)")

chrome_cmd = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    f"--print-to-pdf={PDF_OUT}",
    f"file:///{HTML_OUT.replace(os.sep, '/')}"
]

print("Running Chrome to compile 2-sided Biomass Harvest Sheet PDF...")
proc = subprocess.run(chrome_cmd, capture_output=True, text=True)
if os.path.exists(PDF_OUT) and os.path.getsize(PDF_OUT) > 1000:
    print(f"[SUCCESS] Successfully generated PDF: {PDF_OUT} ({os.path.getsize(PDF_OUT)} bytes)")
else:
    print(f"[ERROR] PDF generation failed. Stderr: {proc.stderr}")
    sys.exit(1)
