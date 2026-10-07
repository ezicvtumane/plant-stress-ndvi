# -*- coding: utf-8 -*-
"""
Официальный сборщик презентации проекта на конкурс «Большие вызовы» 2025/2026.
Автор: Ковалева Алиса Ивановна, 10 класс
Научный руководитель: Ковалев Иван Викторович
Направление: «Агропромышленные и биотехнологии»

Строго соблюдает требования Положения:
1. Формат: PDF (16:9, ландшафт)
2. Объем: ровно 14 слайдов (норматив: не более 15 слайдов)
3. Размер файла: менее 7 Мб
4. Полная автономность: все изображения и графики встроены в base64
"""

import os
import base64
import subprocess
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS_DIR = os.path.join(BASE_DIR, 'docs')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
IMAGES_DIR = os.path.join(DOCS_DIR, 'images')

HTML_PATH = os.path.join(DOCS_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.html')
PDF_PATH = os.path.join(DOCS_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pdf')
PPTX_PATH = os.path.join(DOCS_DIR, 'Презентация_Большие_Вызовы_2026_Ковалева_Алиса.pptx')

def get_base64_img(rel_path):
    abs_path = os.path.join(BASE_DIR, rel_path.replace('/', os.sep))
    if not os.path.exists(abs_path):
        return ""
    ext = os.path.splitext(abs_path)[1].lower().replace('.', '')
    mime = 'image/jpeg' if ext in ['jpg', 'jpeg'] else 'image/png'
    with open(abs_path, 'rb') as f:
        encoded = base64.b64encode(f.read()).decode('utf-8')
    return f"data:{mime};base64,{encoded}"

# Предзагрузка медиа-ассетов
img_alisa_layout = get_base64_img('docs/images/alisa_5_cassettes_layout.jpg')
img_alisa_seeds = get_base64_img('docs/images/alisa_planting_seeds.jpg')
img_alisa_soil = get_base64_img('docs/images/alisa_soil_preparation.jpg')
img_triptych = get_base64_img('data/triptychs/triptych_day04_drought.png')
img_stat_plot = get_base64_img('data/processed/statistical_validation_plot.png')
img_qr_repo = get_base64_img('docs/images/qr_github_repo.png')
img_bv_logo = get_base64_img('docs/images/big_challenges_logo.png')
img_sirius_logo = get_base64_img('docs/images/sirius_center_logo.png')
img_agrotech_logo = get_base64_img('docs/images/agrobiotech_track_logo.png')

HTML_TEMPLATE = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Презентация — Большие вызовы 2026 — Ковалева Алиса</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

@page {{
    size: 1920px 1080px;
    margin: 0;
}}

* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #090d16;
    color: #f8fafc;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    overflow-x: hidden;
}}

.slide {{
    width: 1920px;
    height: 1080px;
    page-break-after: always;
    break-after: page;
    position: relative;
    padding: 50px 80px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
    background: radial-gradient(circle at 85% 15%, #1e293b 0%, #090d16 100%);
}}

.slide:last-child {{
    page-break-after: avoid;
    break-after: avoid;
}}

/* Верхний колонтитул */
.header-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid rgba(148, 163, 184, 0.15);
    padding-bottom: 16px;
}}

.header-left {{
    display: flex;
    align-items: center;
    gap: 15px;
}}

.header-tag {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
    padding: 6px 16px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}}

.header-title-box {{
    text-align: right;
}}

.header-contest {{
    font-size: 13px;
    color: #94a3b8;
    font-weight: 500;
}}

.header-section {{
    font-size: 14px;
    color: #38bdf8;
    font-weight: 700;
}}

/* Заголовок слайда */
.slide-heading {{
    margin-top: 14px;
    margin-bottom: 20px;
}}

.slide-heading h2 {{
    font-size: 34px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.02em;
    line-height: 1.2;
}}

.slide-heading p {{
    font-size: 17px;
    color: #94a3b8;
    margin-top: 5px;
}}

/* Контентная зона */
.content-area {{
    flex: 1;
    display: flex;
    gap: 30px;
    align-items: stretch;
}}

/* Нижний колонтитул */
.footer-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
    padding-top: 15px;
    font-size: 13px;
    color: #64748b;
}}

.footer-author {{
    color: #94a3b8;
    font-weight: 600;
}}

.slide-num {{
    background: rgba(255, 255, 255, 0.08);
    padding: 4px 14px;
    border-radius: 6px;
    font-weight: 700;
    color: #38bdf8;
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
}}

/* Стили карточек */
.card {{
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(12px);
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
}}

.card-title {{
    font-size: 19px;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
}}

/* Сетки */
.grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 25px;
    width: 100%;
}}

.grid-3 {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 22px;
    width: 100%;
}}

.grid-5 {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 16px;
    width: 100%;
}}

/* Бейджи когорт */
.badge-k1 {{ background: rgba(5, 150, 105, 0.2); border: 1px solid #059669; color: #34d399; }}
.badge-k2 {{ background: rgba(124, 58, 237, 0.2); border: 1px solid #7c3aed; color: #c084fc; }}
.badge-k3 {{ background: rgba(234, 179, 8, 0.2); border: 1px solid #eab308; color: #fde047; }}
.badge-k4 {{ background: rgba(37, 99, 235, 0.2); border: 1px solid #2563eb; color: #60a5fa; }}
.badge-k5 {{ background: rgba(220, 38, 38, 0.2); border: 1px solid #dc2626; color: #f87171; }}

.cohort-chip {{
    padding: 5px 12px;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}

/* Таблицы */
table.custom-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-radius: 12px;
    overflow: hidden;
    background: rgba(15, 23, 42, 0.7);
}}

table.custom-table th {{
    background: #1e293b;
    color: #94a3b8;
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 2px solid rgba(148, 163, 184, 0.25);
    text-align: left;
}}

table.custom-table td {{
    padding: 14px 16px;
    font-size: 14px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    color: #e2e8f0;
}}

table.custom-table tr:last-child td {{
    border-bottom: none;
}}

/* Выделители и акценты */
.highlight-val {{
    font-size: 36px;
    font-weight: 900;
    color: #10b981;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.1;
}}

.highlight-label {{
    font-size: 13px;
    color: #94a3b8;
    margin-top: 4px;
    font-weight: 500;
}}

.math-formula {{
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid rgba(56, 189, 248, 0.35);
    border-left: 5px solid #38bdf8;
    padding: 14px 20px;
    border-radius: 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 17px;
    color: #e0f2fe;
    margin: 10px 0;
}}

ul.bullet-list {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 12px;
}}

ul.bullet-list li {{
    position: relative;
    padding-left: 24px;
    font-size: 15px;
    line-height: 1.5;
    color: #cbd5e1;
}}

ul.bullet-list li::before {{
    content: "▹";
    position: absolute;
    left: 0;
    color: #38bdf8;
    font-size: 18px;
    top: -2px;
}}

.img-frame {{
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.25);
    box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.6);
}}

.img-frame img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}}
</style>
</head>
<body>

<!-- ==================== СЛАЙД 1: ТИТУЛЬНЫЙ ==================== -->
<div class="slide" style="background: radial-gradient(circle at 80% 20%, #1e3a5f 0%, #090d16 100%);">
    <div class="header-bar">
        <div class="header-left">
            <span class="header-tag">Международный конкурс научно-технологических проектов «Большие вызовы»</span>
        </div>
        <div class="header-title-box">
            <div class="header-contest">Образовательный центр «Сириус» • 2025/2026 уч. год</div>
            <div class="header-section">Направление: «Агропромышленные и биотехнологии»</div>
        </div>
    </div>

    <div style="display: flex; gap: 40px; align-items: center; margin: 30px 0;">
        <div style="flex: 1.4;">
            <div style="display:inline-block; background:rgba(56, 189, 248, 0.15); border:1px solid #38bdf8; color:#38bdf8; padding:5px 16px; border-radius:30px; font-size:13px; font-weight:700; margin-bottom:18px;">
                НАУЧНО-ИССЛЕДОВАТЕЛЬСКИЙ ПРОЕКТ С ДЕЙСТВУЮЩИМ ПРОТОТИПОМ
            </div>
            <h1 style="font-size: 44px; font-weight: 900; line-height: 1.18; color: #ffffff; letter-spacing: -0.02em;">
                Оптико-электронный комплекс активной двухволновой спектрофотометрии и термографии для ранней индикации водного и осмотического стресса растений
            </h1>
            <p style="font-size: 19px; color: #94a3b8; margin-top: 18px; line-height: 1.5;">
                Выявление скрытого гидротермического и солевого дефицита по сопряженным спектральным (NDVI) и термометрическим (&Delta;T) маркерам за <b>36–54 часа</b> до появления макросимптомов увядания
            </p>
        </div>
        
        <div style="flex: 0.8; height: 380px;" class="img-frame">
            <img src="{img_alisa_layout}" alt="Лабораторный комплекс на 5 кассет">
        </div>
    </div>

    <div style="display: flex; justify-content: space-between; align-items: flex-end; border-top: 2px solid rgba(148, 163, 184, 0.2); padding-top: 20px;">
        <div style="display: flex; gap: 50px;">
            <div>
                <div style="font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Автор проекта:</div>
                <div style="font-size: 21px; font-weight: 800; color: #f8fafc; margin-top: 2px;">Ковалева Алиса Ивановна</div>
                <div style="font-size: 14px; color: #38bdf8;">Учащаяся 10 класса ГБОУ СОШ №282 Кировского района Санкт-Петербурга</div>
            </div>
            <div>
                <div style="font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Научно-технический руководитель:</div>
                <div style="font-size: 21px; font-weight: 800; color: #f8fafc; margin-top: 2px;">Ковалев Иван Викторович</div>
                <div style="font-size: 14px; color: #94a3b8;">Наставник проекта, инженер-исследователь</div>
            </div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 16px; font-weight: 700; color: #e2e8f0;">Санкт-Петербург, 2026</div>
            <div style="font-size: 13px; color: #64748b; font-family:'JetBrains Mono', monospace;">github.com/ezicvtumane/plant-stress-ndvi</div>
        </div>
    </div>
</div>

<!-- ==================== СЛАЙД 2: ПРОБЛЕМА И АКТУАЛЬНОСТЬ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">01 • Актуальность и проблематика</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Агробиотехнологии • Защищенный грунт</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Парадокс мониторинга стресса: потеря урожая до появления внешних симптомов</h2>
        <p>Критические ограничения существующих методов диагностики засухи и засоления</p>
    </div>

    <div class="content-area">
        <div class="grid-3" style="align-items: stretch;">
            <div class="card" style="border-top: 4px solid #ef4444; display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div class="card-title" style="color: #f87171;">⚠️ Поздняя визуальная детекция</div>
                    <p style="font-size: 14px; color: #94a3b8; margin-bottom: 16px;">Человеческий глаз и стандартные RGB-камеры фиксируют увядание лишь при необратимой потере тургора:</p>
                    <div class="highlight-val" style="color: #f87171;">72–96 ч</div>
                    <div class="highlight-label">Время до появления видимого увядания листьев</div>
                </div>
                <div style="padding: 12px; background: rgba(239, 68, 68, 0.12); border-radius: 8px; font-size: 13px; color: #fca5a5;">
                    <b>Критический ущерб:</b> к моменту пожелтения или поникания ботвы растение теряет до <b>25–35%</b> потенциальной биомассы.
                </div>
            </div>

            <div class="card" style="border-top: 4px solid #f59e0b; display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div class="card-title" style="color: #fbbf24;">🔍 «Слепота» датчиков почвы к соли</div>
                    <p style="font-size: 14px; color: #94a3b8; margin-bottom: 16px;">Емкостные и кондуктометрические зонды влажности грунта:</p>
                    <div class="highlight-val" style="color: #fbbf24;">> 70% ПВ</div>
                    <div class="highlight-label">Почва сырая, но вода корням недоступна</div>
                </div>
                <div style="padding: 12px; background: rgba(245, 158, 11, 0.12); border-radius: 8px; font-size: 13px; color: #fde68a;">
                    <b>Осмотический шок:</b> при засолении почвенный раствор имеет сверхвысокое осмотическое давление. Корни не могут всасывать влагу при формально «мокрой» почве.
                </div>
            </div>

            <div class="card" style="border-top: 4px solid #38bdf8; display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div class="card-title" style="color: #38bdf8;">💰 Недоступность лабораторий</div>
                    <p style="font-size: 14px; color: #94a3b8; margin-bottom: 16px;">Существующие научные спектрометры и флуориметры хлорофилла (PAM-2500):</p>
                    <div class="highlight-val" style="color: #38bdf8;">1.8–3.5 млн ₽</div>
                    <div class="highlight-label">Стоимость лабораторных приборов (Walz, CID)</div>
                </div>
                <div style="padding: 12px; background: rgba(56, 189, 248, 0.12); border-radius: 8px; font-size: 13px; color: #bae6fd;">
                    <b>Ограничение масштабирования:</b> требуют контактного крепления клипсы на 1 лист и 30 мин темновой адаптации. Неприменимы для поточного кассетного контроля.
                </div>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">02 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 3: ЦЕЛЬ И ЗАДАЧИ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">02 • Научный аппарат исследования</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Методология и гипотеза</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Цель, научная гипотеза и ключевые задачи проекта</h2>
        <p>Переход от визуальной констатации гибели к превентивному спектро-термометрическому контролю</p>
    </div>

    <div class="content-area">
        <div class="grid-2">
            <div style="display:flex; flex-direction:column; gap:18px;">
                <div class="card" style="border-left: 5px solid #10b981;">
                    <div class="card-title" style="color: #34d399;">🎯 Цель исследования</div>
                    <p style="font-size: 16px; line-height: 1.6; color: #f1f5f9;">
                        Разработка, аппаратно-программная реализация и экспериментальная валидация <b>автономного оптико-электронного комплекса</b> активной двухволновой спектрофотометрии и термографии для <b>ранней неинвазивной экспресс-индикации</b> абиотических стрессов растений в защищенном грунте.
                    </p>
                </div>

                <div class="card" style="border-left: 5px solid #38bdf8;">
                    <div class="card-title" style="color: #38bdf8;">💡 Рабочая научная гипотеза</div>
                    <p style="font-size: 15px; line-height: 1.6; color: #e2e8f0;">
                        Сопряженный анализ динамики <b>транспирационного перегрева листа (&Delta;T)</b> и узкополосных спектральных индексов поглощения хлорофилла <i>a</i> (660 нм) и рассеяния мезофилла (850 нм) позволяет обнаружить развитие физиологического стресса за <b>36–54 часа</b> до появления внешних симптомов при статистической достоверности <b><i>p</i> &lt; 0.001</b>.
                    </p>
                </div>
            </div>

            <div class="card" style="display:flex; flex-direction:column; justify-content:space-between;">
                <div class="card-title">📋 Задачи исследования</div>
                <ul class="bullet-list">
                    <li><b>Оптико-электронный тракт:</b> Спроектировать стробоскопический модуль подсветки 660/850 нм с физическим демультиплексированием матрицы NoIR и 3-кадровым вычитанием темнового фона.</li>
                    <li><b>Термографический канал:</b> Интегрировать микроболометр UNI-T UTi120S с многопороговым алгоритмом OCR Tesseract для фиксации истинной температуры листа.</li>
                    <li><b>Автономное ядро и ArUco:</b> Создать сервер управления на Orange Pi 4 Pro с конвейерным распознаванием фидуциальных ArUco-маркеров кассет и локальной Wi-Fi веб-станцией.</li>
                    <li><b>Светозащитный бокс:</b> Изготовить лазерным раскроем кубический корпус с лабиринтными светоловушками для исключения паразитной фоновой засветки.</li>
                    <li><b>Биологический эксперимент:</b> Провести сравнительное исследование на 5 синхронных когортах (<i>Pisum sativum L.</i>, <i>n</i>=45) и доказать эффективность превентивной регидратации.</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">03 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 4: ФИЗИКО-БИОЛОГИЧЕСКИЙ МЕХАНИЗМ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">03 • Теоретические основы</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Биофизика и физиология стресса</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Двухканальный биофизический механизм детекции стресса</h2>
        <p>Сочетание ультрабыстрого устьичного термоответа и структурно-спектральной деградации</p>
    </div>

    <div class="content-area">
        <div class="grid-2">
            <div class="card" style="border-top: 4px solid #f59e0b;">
                <div class="card-title" style="color: #fbbf24;">🌡️ Канал 1: Термометрия листа (&Delta;T) — Первичный маркер</div>
                <div class="math-formula">&Delta;T = T_leaf - T_air &nbsp;&nbsp;|&nbsp;&nbsp; CWSI = (&Delta;T - &Delta;T_wet) / (&Delta;T_dry - &Delta;T_wet)</div>
                <ul class="bullet-list" style="margin-top: 14px;">
                    <li><b>Физиология:</b> Дефицит воды стимулирует синтез абсцизовой кислоты (АБК) в корнях &rarr; перемещение в листья &rarr; закрытие устьичных щелей.</li>
                    <li><b>Биофизика:</b> Закрытие устьиц блокирует транспирацию &rarr; исчезает расход тепла на испарение (2.26 МДж/кг) &rarr; лист перегревается.</li>
                    <li><b>Время отклика:</b> <b>2–4 часа</b> от начала стресса. Разность температур поднимается от <b>-1.5&deg;C</b> (норма) до <b>+2.0&deg;C</b> (стресс).</li>
                    <li><b>Нормировка по VPD:</b> Расчет дефицита упругости водяного пара по Sensirion SHT30 для исключения влияния влажности воздуха.</li>
                </ul>
            </div>

            <div class="card" style="border-top: 4px solid #10b981;">
                <div class="card-title" style="color: #34d399;">🌱 Канал 2: Мультиспектральный NDVI — Вторичный маркер</div>
                <div class="math-formula">NDVI = (I_850 - I_660) / (I_850 + I_660)</div>
                <ul class="bullet-list" style="margin-top: 14px;">
                    <li><b>Полоса 660 нм (Deep Red):</b> Резонансный пик поглощения хлорофилла <i>a</i>. В здоровом листе поглощается до 90–95% фотонов.</li>
                    <li><b>Полоса 850 нм (NIR):</b> Зона полного отсутствия поглощения пигментами. Отражение на 50–60% определяется архитектоникой мезофилла.</li>
                    <li><b>Время отклика:</b> <b>48–72 часа</b>. NDVI начинает падать только при деградации хлоропластов и фотодеструкции мембран.</li>
                    <li><b>Комплементарность:</b> &Delta;T дает мгновенный алерт, а NDVI подтверждает жизнеспособность и площадь листовой пластинки (PLA).</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">04 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 5: АРХИТЕКТУРА СТАНЦИИ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">04 • Инженерно-техническая реализация</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Аппаратно-программный комплекс</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Аппаратная архитектура оптико-электронного комплекса</h2>
        <p>Портативная станция на базе Orange Pi 4 Pro, NoIR камеры и микроболометра UTi120S</p>
    </div>

    <div class="content-area">
        <div class="grid-3" style="align-items: stretch;">
            <div class="card">
                <div class="card-title">📷 Оптический тракт</div>
                <ul class="bullet-list">
                    <li><b>Сенсор:</b> 5 Мп матрица OmniVision NoIR (с аппаратно удаленным ИК-фильтром 650 нм).</li>
                    <li><b>Канал 1:</b> Узкополосные светодиоды <b>660 нм</b> (Deep Red, FWHM 20 нм).</li>
                    <li><b>Канал 2:</b> Твердотельные излучатели <b>850 нм</b> (NIR, FWHM 30 нм).</li>
                    <li><b>Освещенность:</b> Коллимированная кольцевая схема для устранения теней на листьях.</li>
                </ul>
            </div>

            <div class="card">
                <div class="card-title">🔥 Термометрия и климат</div>
                <ul class="bullet-list">
                    <li><b>Тепловизор:</b> Микроболометр <b>UNI-T UTi120S</b> (120&times;90 пикс, &lambda;=8–14 мкм, NETD &lt; 60 мК).</li>
                    <li><b>OCR Ядро:</b> Tesseract OCR с бинаризацией по Оцу для считывания температуры центра листа.</li>
                    <li><b>Метеомодуль:</b> Sensirion SHT30 (&plusmn;0.2&deg;C, &plusmn;1.5% RH) по UDP-протоколу.</li>
                    <li><b>Влажность почвы:</b> 16-битный АЦП ADS1115 (I2C) с емкостными зондами.</li>
                </ul>
            </div>

            <div class="card">
                <div class="card-title">💻 Вычислительное ядро</div>
                <ul class="bullet-list">
                    <li><b>SoC:</b> Orange Pi 4 Pro (6-ядерный Rockchip RK3399, 4GB LPDDR4, NVMe SSD).</li>
                    <li><b>Автономность:</b> Локальная Wi-Fi AP (<code>PlantStation</code>), не требует интернета.</li>
                    <li><b>ПО:</b> Python 3.10, FastAPI, OpenCV 4.x, gpiod силовое стробирование через реле.</li>
                    <li><b>Себестоимость:</b> <b>11 850 руб.</b> (в 150–200 раз доступнее зарубежных аналогов).</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">05 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 6: АЛГОРИТМ И ARUCO ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">05 • Программные алгоритмы</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Компьютерное зрение и ArUco</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Стробоскопическое 3-кадровое дифференциальное сканирование</h2>
        <p>Полное аппаратное подавление фоновой засветки и автоматическая ArUco-паспортизация кассет</p>
    </div>

    <div class="content-area">
        <div class="grid-2">
            <div class="card">
                <div class="card-title">⚡ Дифференциальный оптический алгоритм</div>
                <p style="font-size: 14px; color: #94a3b8; margin-bottom: 10px;">Для исключения влияния паразитного внешнего света реализован 3-тактный цикл:</p>
                
                <div class="math-formula">I_red = I_raw(660 нм) - I_ambient(Dark)<br>I_nir = I_raw(850 нм) - I_ambient(Dark)</div>

                <ul class="bullet-list" style="margin-top: 12px;">
                    <li><b>Такт 1 (Темновой кадр):</b> Оценка фоновой освещенности при выключенных светодиодах.</li>
                    <li><b>Такт 2 (Вспышка 660 нм):</b> Активация твердотельного реле за 80 мс, съемка канала хлорофилла.</li>
                    <li><b>Такт 3 (Вспышка 850 нм):</b> Съемка инфракрасного рассеяния мезофилла.</li>
                    <li><b>Сегментация биомассы:</b> Вегетационный индекс ExG (2G-R-B) и адаптивный порог Оцу отсекают фон почвы и стенок лотка.</li>
                </ul>
            </div>

            <div class="card">
                <div class="card-title">🏷️ Фидуциальная ArUco-идентификация (5-в-1)</div>
                <p style="font-size: 14px; color: #94a3b8; margin-bottom: 10px;">Исключение человеческого фактора при массовом селекционном скрининге:</p>
                <ul class="bullet-list">
                    <li><b>Словарь ArUco 4&times;4_50:</b> Каждая кассета снабжена индивидуальным маркером ID 1–5 с уникальной цветовой каймой по периметру.</li>
                    <li><b>Многопороговый детектор:</b> Алгоритм с бинаризацией по Оцу устойчив к узкоспектральному освещению 660 нм и цветным меткам.</li>
                    <li><b>Автоматическая привязка:</b> Станция сама определяет номер когорты, тип стресса, извлекает метаданные и заносит в журнал за 1.8 с.</li>
                    <li><b>Матричный анализ:</b> Разбиение поля кассеты на сетку 3&times;3 квадранта с вычислением дисперсии NDVI (&sigma; &le; 0.015).</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">06 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 7: ДИЗАЙН ЭКСПЕРИМЕНТА ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">06 • Биологический эксперимент</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Синхронный дизайн 5 когорт</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Методика и синхронный дизайн эксперимента (n = 45)</h2>
        <p>Модельный объект — горох посевной <i>Pisum sativum L.</i>, сорт «Альфа». 5 кассет в идентичном микроклимате</p>
    </div>

    <div class="content-area" style="flex-direction: column; gap: 20px;">
        <div class="grid-5" style="align-items: stretch; width: 100%;">
            <div class="card" style="border-top: 4px solid #059669; padding: 18px;">
                <div class="cohort-chip badge-k1">🟢 К1: Контроль</div>
                <div style="margin-top: 12px; font-size: 13px; color: #cbd5e1; line-height: 1.45;">
                    <b>Режим:</b> Оптимальный полив дистиллированной водой (100% ПВ, 65–70% влажности почвы).<br><br>
                    <b>Цель:</b> Базовый эталон здорового фотосинтеза и транспирации.
                </div>
            </div>

            <div class="card" style="border-top: 4px solid #7c3aed; padding: 18px;">
                <div class="cohort-chip badge-k2">🟣 К2: Засоление</div>
                <div style="margin-top: 12px; font-size: 13px; color: #cbd5e1; line-height: 1.45;">
                    <b>Режим:</b> Полив раствором NaCl 150 мМ в герметичном отдельном лотке.<br><br>
                    <b>Цель:</b> Моделирование осмотического блока при высокой влажности субстрата.
                </div>
            </div>

            <div class="card" style="border-top: 4px solid #eab308; padding: 18px;">
                <div class="cohort-chip badge-k3">🟡 К3: Превент. регидратация</div>
                <div style="margin-top: 12px; font-size: 13px; color: #cbd5e1; line-height: 1.45;">
                    <b>Режим:</b> Прекращение полива до раннего алерта станции (&Delta;T &ge; +0.8&deg;C), затем полив.<br><br>
                    <b>Цель:</b> Купирование стресса в «Окне превентивной регидратации».
                </div>
            </div>

            <div class="card" style="border-top: 4px solid #2563eb; padding: 18px;">
                <div class="cohort-chip badge-k4">🔵 К4: Традиц. контроль</div>
                <div style="margin-top: 12px; font-size: 13px; color: #cbd5e1; line-height: 1.45;">
                    <b>Режим:</b> Без полива до явного визуального увядания листьев (потеря тургора).<br><br>
                    <b>Цель:</b> Оценка скрытых потерь урожая традиционного агроконтроля.
                </div>
            </div>

            <div class="card" style="border-top: 4px solid #dc2626; padding: 18px;">
                <div class="cohort-chip badge-k5">🔴 К5: Терм. засуха</div>
                <div style="margin-top: 12px; font-size: 13px; color: #cbd5e1; line-height: 1.45;">
                    <b>Режим:</b> Полное отсутствие полива до необратимого некроза биомассы (96+ ч).<br><br>
                    <b>Цель:</b> Определение критической точки невозврата растительной ткани.
                </div>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; height: 180px;">
            <div class="img-frame" style="display:flex; align-items:center; background:#1e293b;">
                <img src="{img_alisa_seeds}" alt="Посев семян в кассеты">
            </div>
            <div class="img-frame" style="display:flex; align-items:center; background:#1e293b;">
                <img src="{img_alisa_soil}" alt="Подготовка субстрата">
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">07 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 8: ДИНАМИКА ТЕРМОМЕТРИИ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">07 • Результаты исследований</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Динамика &Delta;T листовой пластинки</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Температурный маркер (&Delta;T): сверхранняя фиксация стресса</h2>
        <p>Нагрев листа на +1.5...+2.0&deg;C начинается уже через 24–36 часов после прекращения водопотребления</p>
    </div>

    <div class="content-area">
        <div class="grid-2">
            <div class="card">
                <div class="card-title">📈 Временной ряд &Delta;T = T_leaf - T_air (&deg;C)</div>
                <table class="custom-table" style="margin-top: 8px;">
                    <thead>
                        <tr>
                            <th>Когорта</th>
                            <th>0 ч</th>
                            <th>24 ч</th>
                            <th>48 ч (Окно)</th>
                            <th>72 ч</th>
                            <th>96 ч (Финал)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><span class="badge-k1 cohort-chip">🟢 К1 Контроль</span></td>
                            <td>-1.4&deg;C</td>
                            <td>-1.5&deg;C</td>
                            <td>-1.4&deg;C</td>
                            <td>-1.3&deg;C</td>
                            <td>-1.5&deg;C</td>
                        </tr>
                        <tr>
                            <td><span class="badge-k2 cohort-chip">🟣 К2 Засоление</span></td>
                            <td>-1.4&deg;C</td>
                            <td>-0.2&deg;C</td>
                            <td><b>+1.1&deg;C</b></td>
                            <td>+1.8&deg;C</td>
                            <td>+2.1&deg;C</td>
                        </tr>
                        <tr>
                            <td><span class="badge-k3 cohort-chip">🟡 К3 Превент. регидратация</span></td>
                            <td>-1.4&deg;C</td>
                            <td>+0.1&deg;C</td>
                            <td><b>+1.2&deg;C</b> (Полив)</td>
                            <td>-0.9&deg;C</td>
                            <td><b>-1.3&deg;C</b></td>
                        </tr>
                        <tr>
                            <td><span class="badge-k4 cohort-chip">🔵 К4 Традиц. контроль</span></td>
                            <td>-1.4&deg;C</td>
                            <td>0.0&deg;C</td>
                            <td>+1.4&deg;C</td>
                            <td><b>+2.4&deg;C</b> (Полив)</td>
                            <td>-0.4&deg;C</td>
                        </tr>
                        <tr>
                            <td><span class="badge-k5 cohort-chip">🔴 К5 Засуха</span></td>
                            <td>-1.4&deg;C</td>
                            <td>+0.2&deg;C</td>
                            <td>+1.6&deg;C</td>
                            <td>+2.6&deg;C</td>
                            <td><b>+3.2&deg;C</b></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card" style="display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div class="card-title">🔬 Физиологический анализ динамики</div>
                    <ul class="bullet-list">
                        <li><b>Контроль (К1):</b> Устьица открыты, активная транспирация охлаждает лист на <b>1.3–1.5&deg;C</b> ниже температуры воздуха.</li>
                        <li><b>Засоление (К2):</b> При влажности почвы 64% лист перегревается до <b>+1.1&deg;C</b> уже на 48 ч! Доказана неспособность контактных датчиков обнаружить солевой стресс.</li>
                        <li><b>К3 vs К4:</b> Полив кассеты К3 на 48-м часу возвращает охлаждение к норме (-1.3&deg;C) уже через 6 часов. В К4 к моменту полива устьичный аппарат поврежден (-0.4&deg;C).</li>
                    </ul>
                </div>
                <div style="background:rgba(16, 185, 129, 0.15); border:1px solid #10b981; padding:14px; border-radius:10px; font-size:14px; color:#a7f3d0;">
                    <b>Статистическая значимость:</b> Различия между К1 и К5/К2 на 48 ч достоверны при <b><i>t</i> = 8.42, <i>p</i> &lt; 0.001</b> (двусторонний t-критерий Стьюдента).
                </div>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">08 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 9: ДИНАМИКА NDVI И БИОМАССА ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">08 • Результаты исследований</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Спектральный индекс NDVI и площадь листьев</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Динамика NDVI и сохранение площади листовой поверхности (PLA)</h2>
        <p>Индекс NDVI подтверждает: хлорофилл стабилен в первые 48 ч, спасая растение до цитологических повреждений</p>
    </div>

    <div class="content-area">
        <div class="grid-2">
            <div class="card">
                <div class="card-title">📊 Динамика вегетационного индекса NDVI</div>
                <table class="custom-table" style="margin-top: 8px;">
                    <thead>
                        <tr>
                            <th>Когорта</th>
                            <th>0 ч</th>
                            <th>48 ч (Окно)</th>
                            <th>72 ч (Увядание)</th>
                            <th>96 ч (Финал)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><span class="badge-k1 cohort-chip">🟢 К1 Контроль</span></td>
                            <td>0.742 &plusmn; 0.01</td>
                            <td>0.745 &plusmn; 0.01</td>
                            <td>0.748 &plusmn; 0.01</td>
                            <td><b>0.752 &plusmn; 0.01</b></td>
                        </tr>
                        <tr>
                            <td><span class="badge-k2 cohort-chip">🟣 К2 Засоление</span></td>
                            <td>0.739 &plusmn; 0.01</td>
                            <td>0.722 &plusmn; 0.01</td>
                            <td>0.614 &plusmn; 0.02</td>
                            <td><b>0.514 &plusmn; 0.02</b></td>
                        </tr>
                        <tr>
                            <td><span class="badge-k3 cohort-chip">🟡 К3 Превент. регидратация</span></td>
                            <td>0.741 &plusmn; 0.01</td>
                            <td>0.730 &plusmn; 0.01</td>
                            <td>0.725 &plusmn; 0.01</td>
                            <td><b>0.744 &plusmn; 0.01</b></td>
                        </tr>
                        <tr>
                            <td><span class="badge-k4 cohort-chip">🔵 К4 Традиц. контроль</span></td>
                            <td>0.740 &plusmn; 0.01</td>
                            <td>0.718 &plusmn; 0.02</td>
                            <td>0.582 &plusmn; 0.03</td>
                            <td><b>0.618 &plusmn; 0.02</b></td>
                        </tr>
                        <tr>
                            <td><span class="badge-k5 cohort-chip">🔴 К5 Засуха</span></td>
                            <td>0.744 &plusmn; 0.01</td>
                            <td>0.708 &plusmn; 0.02</td>
                            <td>0.540 &plusmn; 0.03</td>
                            <td><b>0.455 &plusmn; 0.02</b></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card" style="display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div class="card-title">🌿 Продуктивность биомассы (PLA, см&sup2;)</div>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:14px; margin: 12px 0;">
                        <div style="background:rgba(5, 150, 105, 0.2); border:1px solid #059669; padding:14px; border-radius:10px;">
                            <div style="font-size:12px; color:#a7f3d0; font-weight:700;">К3: ПРЕВЕНТИВНАЯ СТРАТЕГИЯ</div>
                            <div style="font-size:30px; font-weight:900; color:#34d399; margin-top:2px;">92.4%</div>
                            <div style="font-size:12px; color:#cbd5e1;">сохранности площади листьев относительно контроля</div>
                        </div>
                        <div style="background:rgba(37, 99, 235, 0.2); border:1px solid #2563eb; padding:14px; border-radius:10px;">
                            <div style="font-size:12px; color:#bfdbfe; font-weight:700;">К4: РЕАКТИВНАЯ СТРАТЕГИЯ</div>
                            <div style="font-size:30px; font-weight:900; color:#60a5fa; margin-top:2px;">68.7%</div>
                            <div style="font-size:12px; color:#cbd5e1;">сохранности биомассы (потеря 31.3% из-за увядания)</div>
                        </div>
                    </div>
                    <ul class="bullet-list">
                        <li><b>Запаздывание NDVI:</b> На 48 ч NDVI кассеты К5 упал всего на 4.8%, в то время как &Delta;T вырос на 300%. Это доказывает необходимость <b>сопряженного</b> анализа!</li>
                    </ul>
                </div>
                <div style="background:rgba(234, 179, 8, 0.15); border:1px solid #eab308; padding:12px; border-radius:8px; font-size:13px; color:#fef08a;">
                    <b>Сравнительная оценка стратегий:</b> Превентивная регидратация по алерту станции сохраняет <b>+23.7%</b> товарной массы побегов по сравнению с визуальным осмотром.
                </div>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">09 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 10: ОКНО ПРЕВЕНТИВНОГО СПАСЕНИЯ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">09 • Главное научное открытие</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Феноменология физиологического стресса</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Обнаружение и обоснование «Окна превентивной регидратации»</h2>
        <p>Временной интервал между закрытием устьиц и распадом хлорофилла составляет от 24 до 54 часов</p>
    </div>

    <div class="content-area" style="flex-direction: column; gap: 20px;">
        <div class="grid-3" style="align-items: stretch; flex: 1;">
            <div class="card" style="border-top: 4px solid #10b981; padding: 18px;">
                <div class="card-title" style="color: #34d399; font-size:17px;">ФАЗА I (0–24 ч)<br>Компенсация</div>
                <div style="margin: 10px 0;">
                    <span style="background:rgba(16, 185, 129, 0.2); color:#34d399; padding:3px 8px; border-radius:5px; font-weight:700; font-size:12px;">НОРМА</span>
                </div>
                <ul class="bullet-list" style="font-size: 13px;">
                    <li><b>&Delta;T:</b> от -1.5&deg;C до -0.5&deg;C.</li>
                    <li><b>NDVI:</b> &gt; 0.73 (норма).</li>
                    <li><b>Внешний вид:</b> Идеальный тургор.</li>
                    <li><b>Физиология:</b> Запасы влаги в норме, активная транспирация.</li>
                </ul>
            </div>

            <div class="card" style="border-top: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.1); border: 2px solid #f59e0b; padding: 18px;">
                <div class="card-title" style="color: #fbbf24; font-size:17px;">ФАЗА II (24–54 ч)<br>⭐ «ПРЕВЕНТИВНОЕ ОКНО»</div>
                <div style="margin: 10px 0;">
                    <span style="background:rgba(245, 158, 11, 0.3); color:#fef08a; padding:3px 8px; border-radius:5px; font-weight:700; font-size:12px;">АЛЕРТ СТАНЦИИ</span>
                </div>
                <ul class="bullet-list" style="font-size: 13px;">
                    <li><b>&Delta;T:</b> <b>&ge; +0.8&deg;C &dots; +1.6&deg;C</b> (Устьица закрыты!).</li>
                    <li><b>NDVI:</b> 0.71–0.73 (Хлорофилл сохранен!).</li>
                    <li><b>Внешний вид:</b> Растения внешне неотличимы от контроля!</li>
                    <li><b>РЕЗУЛЬТАТ ПОЛИВА:</b> <b>100% обратимость</b> стресса, сохранение урожая.</li>
                </ul>
            </div>

            <div class="card" style="border-top: 4px solid #ef4444; padding: 18px;">
                <div class="card-title" style="color: #f87171; font-size:17px;">ФАЗА III (54–96 ч)<br>Точка невозврата</div>
                <div style="margin: 10px 0;">
                    <span style="background:rgba(239, 68, 68, 0.2); color:#fca5a5; padding:3px 8px; border-radius:5px; font-weight:700; font-size:12px;">НЕКРОЗ И ГИБЕЛЬ</span>
                </div>
                <ul class="bullet-list" style="font-size: 13px;">
                    <li><b>&Delta;T:</b> &gt; +2.5&deg;C.</li>
                    <li><b>NDVI:</b> Стремительное падение &lt; 0.55.</li>
                    <li><b>Внешний вид:</b> Скручивание, поникание ботвы.</li>
                    <li><b>РЕЗУЛЬТАТ:</b> Необратимая гибель проводящих пучков и мезофилла.</li>
                </ul>
            </div>
        </div>

        <div style="height: 180px; width: 100%;" class="img-frame">
            <img src="{img_triptych}" alt="Мультиспектрально-термографический триптих">
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">10 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 11: ТАБЛИЦА АНАЛОГОВ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">10 • Конкурентный анализ аналогов</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Критерий 2: Анализ решений на рынке</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Сравнительный анализ с отечественными и мировыми аналогами</h2>
        <p>Разработанный комплекс превосходит лабораторные приборы по скорости скрининга и доступности</p>
    </div>

    <div class="content-area">
        <table class="custom-table">
            <thead>
                <tr>
                    <th style="width:22%;">Решение / Прибор</th>
                    <th style="width:18%;">Измеряемые параметры</th>
                    <th style="width:20%;">Тип и время замера</th>
                    <th style="width:22%;">Недостатки в теплицах</th>
                    <th style="width:18%;">Ориентир. стоимость</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><b>Walz PAM-2500</b><br><span style="font-size:12px; color:#94a3b8;">Германия (Импульсный флуориметр)</span></td>
                    <td>Fv/Fm, квантовый выход ФС-II</td>
                    <td>Контактный (клипса на 1 лист), <b>20–30 мин</b></td>
                    <td>Требует темновой адаптации, точечный замер, разрушает восковой налет</td>
                    <td><b style="color:#f87171;">~3 200 000 ₽</b></td>
                </tr>
                <tr>
                    <td><b>CID CI-710 Miniature</b><br><span style="font-size:12px; color:#94a3b8;">США (Полевой спектрометр)</span></td>
                    <td>Спектр 400–950 нм, NDVI</td>
                    <td>Контактный световод, <b>2–3 мин</b></td>
                    <td>Нет термометрического канала (&Delta;T), «слеп» к раннему водному шоку</td>
                    <td><b style="color:#f87171;">~1 850 000 ₽</b></td>
                </tr>
                <tr>
                    <td><b>MicaSense RedEdge (БПЛА)</b><br><span style="font-size:12px; color:#94a3b8;">США (Мультиспектр для дронов)</span></td>
                    <td>5 спектральных каналов</td>
                    <td>Дистанционный облет полей</td>
                    <td>Неприменим в закрытых сити-фермах, стеллажах, теплицах; нет термометрии</td>
                    <td><b style="color:#f87171;">~1 200 000 ₽</b></td>
                </tr>
                <tr style="background: rgba(16, 185, 129, 0.15); border-left: 4px solid #10b981;">
                    <td><b style="color:#34d399;">Разработанная станция</b><br><span style="font-size:12px; color:#a7f3d0;">Санкт-Петербург (Авторская разработка)</span></td>
                    <td><b style="color:#38bdf8;">NDVI + &Delta;T + SHT30 + ArUco</b></td>
                    <td>Бесконтактный строб кассеты, <b>1.8 секунды</b></td>
                    <td><b style="color:#34d399;">Преимущества:</b> автономность, ранняя детекция в закрытом грунте, ArUco-паспортизация</td>
                    <td><b style="color:#34d399;">11 850 ₽</b><br><span style="font-size:11px; color:#94a3b8;">(в 150+ раз доступнее)</span></td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">11 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 12: ПРАКТИЧЕСКАЯ ЗНАЧИМОСТЬ ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">11 • Практическая значимость и внедрение</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Экономика и масштабирование</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Сферы применения, внедрение и экономический эффект</h2>
        <p>Готовое решение для сити-фермерства, промышленного защищенного грунта и селекционных фитотронов</p>
    </div>

    <div class="content-area">
        <div class="grid-3" style="align-items: stretch;">
            <div class="card">
                <div class="card-title">🏢 Вертикальные сити-фермы</div>
                <ul class="bullet-list">
                    <li>Поточный скрининг салатных и ягодных культур на многоярусных стеллажах.</li>
                    <li>Предотвращение солевых ожогов и физиологической засухи при автоматическом поливе питательными растворами.</li>
                    <li><b>Экономия ресурсов:</b> снижение расхода воды и минеральных удобрений на <b>15–20%</b>.</li>
                </ul>
            </div>

            <div class="card">
                <div class="card-title">🌾 Селекция и фитотроны</div>
                <ul class="bullet-list">
                    <li>Быстрый скрининг сотен генотипов растений на засухоустойчивость и солеустойчивость.</li>
                    <li>ArUco-маркировка исключает ошибки оператора при регистрации десятков опытных делянок.</li>
                    <li>Объективная валидация устойчивости сортов по термометрическому индексу устьичного ответа.</li>
                </ul>
            </div>

            <div class="card" style="border-top: 4px solid #10b981;">
                <div class="card-title" style="color: #34d399;">💰 Экономический расчет</div>
                <div style="margin: 12px 0;">
                    <div class="highlight-val" style="font-size:30px;">&lt; 2 месяцев</div>
                    <div class="highlight-label">Срок окупаемости на 100 м&sup2; закрытого грунта</div>
                </div>
                <p style="font-size: 13px; color: #cbd5e1; line-height: 1.5;">
                    Предотвращение гибели всего <b>1 кассетной партии</b> ценных микрозеленных или салатных культур полностью окупает себестоимость станции (11 850 руб).
                </p>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">12 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 13: ВЫВОДЫ И НАУЧНАЯ НОВИЗНА ==================== -->
<div class="slide">
    <div class="header-bar">
        <div class="header-tag">12 • Итоги и личный вклад</div>
        <div class="header-title-box">
            <div class="header-contest">Конкурс «Большие вызовы» 2026</div>
            <div class="header-section">Выводы по работе</div>
        </div>
    </div>

    <div class="slide-heading">
        <h2>Научная новизна и основные выводы исследования</h2>
        <p>Ключевые результаты, полученные лично автором в ходе выполнения проекта</p>
    </div>

    <div class="content-area">
        <div class="grid-2">
            <div class="card" style="border-left: 5px solid #38bdf8;">
                <div class="card-title" style="color: #38bdf8;">✨ Научная новизна</div>
                <ul class="bullet-list">
                    <li>Впервые предложена и аппаратно реализована <b>сопряженная модель</b> одновременного спектрального (NDVI) и термометрического (&Delta;T) скрининга с дифференциальным стробированием 660/850 нм в закрытом боксе.</li>
                    <li>Экспериментально доказано существование <b>«Окна превентивного спасения»</b> длительностью 24–54 ч, в котором устьичный перегрев (&Delta;T &ge; +0.8&deg;C) опережает падение NDVI и визуальное увядание.</li>
                    <li>Обоснована неэффективность классических почвенных датчиков при выявлении осмотического засоления (NaCl 150 мМ) и доказано преимущество дистанционной термографии.</li>
                </ul>
            </div>

            <div class="card" style="border-left: 5px solid #10b981;">
                <div class="card-title" style="color: #34d399;">📌 Основные выводы</div>
                <ul class="bullet-list">
                    <li>Спроектирован и собран действующий оптико-электронный комплекс с себестоимостью <b>11 850 руб</b>, управляемый Linux-сервером Orange Pi 4 Pro.</li>
                    <li>Разработан алгоритм распознавания ArUco-маркеров и дифференциального 3-кадрового вычитания темнового фона для независимости от внешнего света.</li>
                    <li>Проведен модельный опыт на <i>Pisum sativum L.</i> (<i>n</i>=45): стратегия превентивной регидратации по алерту станции сохраняет <b>92.4%</b> продуктивной биомассы против 68.7% при традиционном визуальном контроле (+23.7% выигрыша).</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="footer-bar">
        <span class="footer-author">Ковалева Алиса • Исследовательский проект</span>
        <span class="slide-num">13 / 14</span>
    </div>
</div>

<!-- ==================== СЛАЙД 14: ЗАКЛЮЧИТЕЛЬНЫЙ СЛАЙД ==================== -->
<div class="slide" style="background: radial-gradient(circle at 50% 50%, #1e293b 0%, #090d16 100%); text-align: center; justify-content: center; align-items: center;">
    <div style="max-width: 1200px; display: flex; flex-direction: column; align-items: center; gap: 25px;">
        <div style="display:inline-block; background:rgba(16, 185, 129, 0.15); border:1px solid #10b981; color:#34d399; padding:6px 20px; border-radius:30px; font-size:15px; font-weight:700;">
            ОТКРЫТЫЙ ИСХОДНЫЙ КОД И ДОКУМЕНТАЦИЯ
        </div>

        <h1 style="font-size: 50px; font-weight: 900; color: #ffffff; letter-spacing: -0.02em;">
            Спасибо за внимание!
        </h1>
        <p style="font-size: 20px; color: #94a3b8; max-width: 900px; line-height: 1.5;">
            Готова ответить на вопросы экспертной комиссии конкурса
        </p>

        <div style="display: flex; gap: 35px; margin-top: 15px; align-items: center;">
            <div style="width: 140px; height: 140px; background: white; padding: 8px; border-radius: 12px;" class="img-frame">
                <img src="{img_qr_repo}" alt="QR code repo" style="width: 100%; height: 100%; object-fit: contain;">
            </div>

            <div class="card" style="padding: 20px 30px; text-align: left;">
                <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase;">Репозиторий проекта на GitHub:</div>
                <div style="font-size: 17px; font-weight: 700; color: #38bdf8; margin-top: 3px; font-family:'JetBrains Mono', monospace;">
                    github.com/ezicvtumane/plant-stress-ndvi
                </div>
                <div style="font-size: 13px; color: #94a3b8; margin-top: 4px;">Схемы, чертежи бокса в САПР, код веб-станции и SciPy-анализа</div>
            </div>

            <div class="card" style="padding: 20px 30px; text-align: left;">
                <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase;">Контакты автора:</div>
                <div style="font-size: 17px; font-weight: 700; color: #f8fafc; margin-top: 3px;">Ковалева Алиса Ивановна</div>
                <div style="font-size: 13px; color: #34d399; margin-top: 2px;">Email: v1m@mail.ru</div>
            </div>
        </div>

        <div style="font-size: 14px; color: #64748b; margin-top: 10px;">
            Всероссийский конкурс научно-технологических проектов «Большие вызовы» • 2025/2026
        </div>
    </div>
</div>

</body>
</html>
"""

def main():
    print(f"Запись HTML-презентации: {HTML_PATH}...")
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(HTML_TEMPLATE)
    print("HTML успешно сохранен.")

    chrome_candidates = [
        r'/usr/bin/chromium',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
    ]
    browser = None
    for c in chrome_candidates:
        if os.path.exists(c):
            browser = c
            break

    if not browser:
        print("[ERROR] Не найден браузер Chrome/Edge для компиляции PDF!")
        return

    print(f"Печать PDF через {browser}...")
    cmd = [
        browser,
        '--headless',
        '--disable-gpu',
        '--no-sandbox',
        '--print-to-pdf-no-header',
        f'--print-to-pdf={PDF_PATH}',
        HTML_PATH
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode == 0 and os.path.exists(PDF_PATH):
        sz_kb = os.path.getsize(PDF_PATH) / 1024.0
        with open(PDF_PATH, 'rb') as f:
            c = f.read()
            pages = c.count(b'/Type /Page') - c.count(b'/Type /Pages')
        print(f"УСПЕХ! PDF сгенерирован: {PDF_PATH}")
        print(f"Слайдов: {pages} (требование: не более 15).")
        print(f"Размер: {sz_kb:.1f} Кб (требование: до 7000 Кб).")

        # Синхронизация со static/
        shutil_copy = True
        try:
            import shutil
            shutil.copy2(PDF_PATH, os.path.join(STATIC_DIR, os.path.basename(PDF_PATH)))
            shutil.copy2(HTML_PATH, os.path.join(STATIC_DIR, os.path.basename(HTML_PATH)))
            print("Файлы презентации скопированы в static/")
        except Exception as e:
            print("Ошибка копирования в static:", e)
    else:
        print("[ERROR] Ошибка генерации PDF:", res.stderr.decode('utf-8', errors='ignore'))

if __name__ == '__main__':
    main()
