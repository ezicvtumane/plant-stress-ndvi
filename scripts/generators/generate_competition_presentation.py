# -*- coding: utf-8 -*-
"""
Генератор официальной презентации конкурсной работы (СТРОГО 15 СЛАЙДОВ!)
для Всероссийского конкурса научно-технологических проектов «Большие вызовы»
(Образовательный центр «Сириус») 2025/2026 учебный год.
Направление: «Агропромышленные и биотехнологии».
"""

import os
import base64
import subprocess
import shutil

CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_FILE_DIR) in ["generators", "tests"]:
    BASE_DIR = os.path.dirname(os.path.dirname(CURRENT_FILE_DIR))
elif os.path.basename(CURRENT_FILE_DIR) == "scripts":
    BASE_DIR = os.path.dirname(CURRENT_FILE_DIR)
else:
    BASE_DIR = CURRENT_FILE_DIR

DOCS_DIR = os.path.join(BASE_DIR, "docs")

def img_b64(rel_path):
    p = os.path.join(BASE_DIR, rel_path)
    if os.path.exists(p):
        with open(p, "rb") as f:
            ext = os.path.splitext(p)[1].lower().replace(".", "")
            if ext == "jpg": ext = "jpeg"
            return f"data:image/{ext};base64," + base64.b64encode(f.read()).decode("ascii")
    return ""

b64_logo_bv = img_b64(r"docs\images\big_challenges_logo.png")
b64_logo_agro = img_b64(r"docs\images\agrobiotech_track_logo.png")
b64_plot = img_b64(r"data\processed\statistical_validation_plot.png")
b64_triptych = img_b64(r"data\triptychs\triptych_day04_drought.png")
b64_raskroy = img_b64(r"hardware\laser\0_Raskroy_Fanery_760x760.svg")

slides_data = [
    # Слайд 1: Титульный
    f'''
    <div class="slide slide-title">
        <div class="header-logos" style="margin-bottom: 25px;">
            <img src="{b64_logo_bv}" style="height: 60px;">
            <img src="{b64_logo_agro}" style="height: 60px;">
        </div>
        <div class="badge-sirius" style="font-size: 13pt; margin-bottom: 12px; display: inline-block;">
            ★ ВСЕРОССИЙСКИЙ КОНКУРС «БОЛЬШИЕ ВЫЗОВЫ» · 2025/2026 · ОЦ «СИРИУС»
        </div>
        <div style="font-size: 15pt; color: #2dd4bf; font-weight: bold; margin-bottom: 20px;">
            Направление: «Агропромышленные и биотехнологии»
        </div>
        <h1 style="font-size: 23pt; line-height: 1.3; color: #ffffff; max-width: 1050px; margin: 0 auto 30px auto; text-transform: uppercase;">
            Оптико-электронный комплекс активной двухволновой спектрофотометрии и термографии для ранней индикации водного и осмотического стресса растений
        </h1>
        <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(0, 164, 153, 0.4); border-radius: 12px; padding: 14px 22px; display: inline-block; text-align: left; font-size: 12pt; line-height: 1.45;">
            <b>Автор:</b> Ковалева Алиса Ивановна, учащаяся 10 класса (ГБОУ СОШ №282 СПб)<br>
            <b>Научно-технический руководитель:</b> Ковалев Иван Викторович<br>
            <b>GitHub:</b> <span style="color:#38bdf8;">github.com/ezicvtumane/plant-stress-ndvi</span>
        </div>
    </div>
    ''',

    # Слайд 2: Проблема и актуальность
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">02 / 15</span>
            <h2>Актуальность и нерешенные проблемы агробиотехнологий</h2>
        </div>
        <div class="grid-2col" style="gap: 24px; margin-top: 20px;">
            <div class="card-box">
                <h3 style="color:#ef4444; font-size: 16pt;">⚠️ Задержка визуальной детекции (48–72 ч)</h3>
                <p style="font-size: 13pt; line-height: 1.5; color: #cbd5e1;">
                    В защищенном грунте (сити-фермы, фитотроны) дефицит влаги традиционно фиксируется по увяданию листьев и хлорозу.<br><br>
                    К этому моменту в тканях уже происходят <b>необратимые патологии</b>: плазмолиз клеток мезофилла, разрушение хлорофилл-белковых комплексов тилакоидов фотосистемы II (PSII) и падение продуктивности на 20–35%.
                </p>
            </div>
            <div class="card-box">
                <h3 style="color:#fbbf24; font-size: 16pt;">🧂 «Слепота» почвенных сенсоров к осмотическому стрессу</h3>
                <p style="font-size: 13pt; line-height: 1.5; color: #cbd5e1;">
                    При засолении питательного субстрата (соли NaCl &gt; 1.0%) физическая влажность почвы остается высокой (<b>&gt;75–80%</b>).<br><br>
                    Стандартные емкостные датчики сигнализируют о нормальной поливке, однако корни растения не способны поглощать влагу из-за градиента осмотического давления. Наступает <b>«физиологическая засуха»</b>, невидимая для существующих датчиков почвы.
                </p>
            </div>
        </div>
        <div class="highlight-bar" style="margin-top: 24px; font-size: 14pt;">
            🎯 <b>Задача проекта</b>: обнаружить устьичное замыкание и фотоингибирование на уровне биофизических маркеров за десятки часов до внешнего увядания.
        </div>
    </div>
    ''',

    # Слайд 3: Цель и задачи исследования
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">03 / 15</span>
            <h2>Цель и научно-инженерные задачи исследования</h2>
        </div>
        <div style="background: rgba(0, 164, 153, 0.15); border-left: 5px solid #00a499; padding: 14px 20px; border-radius: 8px; font-size: 15pt; margin: 18px 0; color: #f8fafc;">
            <b>Цель</b>: разработка, аппаратно-программная реализация и экспериментальная валидация автономного оптико-электронного комплекса активной двухволновой спектрофотометрии и термографии для сверхранней неинвазивной индикации водного и осмотического стресса растений.
        </div>
        <div class="grid-3col" style="gap: 16px; margin-top: 20px;">
            <div class="card-box" style="padding: 14px;">
                <b style="color:#2dd4bf; font-size:14pt;">1. Оптический тракт</b>
                <p style="font-size:12pt; color:#cbd5e1; margin-top:8px;">Создание стробоскопического излучателя 660/850 нм и 3-кадрового алгоритма компенсации внешнего комнатного света.</p>
            </div>
            <div class="card-box" style="padding: 14px;">
                <b style="color:#2dd4bf; font-size:14pt;">2. Термография &amp; OCR</b>
                <p style="font-size:12pt; color:#cbd5e1; margin-top:8px;">Интеграция микроболометра UTi120S с автоматическим Tesseract OCR распознаванием температуры листа и расчетом &Delta;T.</p>
            </div>
            <div class="card-box" style="padding: 14px;">
                <b style="color:#2dd4bf; font-size:14pt;">3. Кубический бокс</b>
                <p style="font-size:12pt; color:#cbd5e1; margin-top:8px;">Проектирование и лазерный раскрой светонепроницаемого куба 200&times;200&times;200 мм с лабиринтными светоловушками.</p>
            </div>
            <div class="card-box" style="padding: 14px;">
                <b style="color:#818cf8; font-size:14pt;">4. Метрологический эталон</b>
                <p style="font-size:12pt; color:#cbd5e1; margin-top:8px;">Гравиметрический весовой эталон (0.1 г), АЦП ADS1115 и сенсор микроклимата Sensirion SHT30 (расчет дефицита пара VPD).</p>
            </div>
            <div class="card-box" style="padding: 14px;">
                <b style="color:#818cf8; font-size:14pt;">5. Операторская веб-станция</b>
                <p style="font-size:12pt; color:#cbd5e1; margin-top:8px;">Разработка локального пульта (FastAPI, OpenCV) для пошагового проведения серий и мгновенного экспорта данных.</p>
            </div>
            <div class="card-box" style="padding: 14px;">
                <b style="color:#818cf8; font-size:14pt;">6. Биологический опыт (n=30)</b>
                <p style="font-size:12pt; color:#cbd5e1; margin-top:8px;">7-дневный эксперимент на горохе посевном в трех когортах (Контроль, Засуха, Соль) с анализом в среде SciPy (p &lt; 0.01).</p>
            </div>
        </div>
    </div>
    ''',

    # Слайд 4: Анализ существующих решений
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">04 / 15</span>
            <h2>Анализ существующих решений и аналогов</h2>
        </div>
        <table class="report-table" style="font-size: 12pt; margin-top: 20px;">
            <thead>
                <tr style="background:#0f172a;">
                    <th>Критерий сравнения</th>
                    <th>Лабораторный спектрофотометр</th>
                    <th>Мультиспектральные БПЛА</th>
                    <th>Почвенные станции</th>
                    <th style="background:#065f46; color:#2dd4bf;">Разработанный комплекс</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><b>Бюджет узла</b></td>
                    <td>&gt; 1 500 000 руб.</td>
                    <td>&gt; 450 000 руб.</td>
                    <td>20 000 – 50 000 руб.</td>
                    <td style="color:#2dd4bf; font-weight:bold;">11 850 руб. (&times;10–30 дешевле)</td>
                </tr>
                <tr>
                    <td><b>Опережение диагностики</b></td>
                    <td>Да (по хлорофиллу)</td>
                    <td>Ограничено разрешением</td>
                    <td>Нет (задержка 48 ч)</td>
                    <td style="color:#2dd4bf; font-weight:bold;">36–54 ч до увядания</td>
                </tr>
                <tr>
                    <td><b>Детекция осмотического стресса</b></td>
                    <td>Сложная пробоподготовка</td>
                    <td>Не способна</td>
                    <td><b>Не способна</b> (видит влагу)</td>
                    <td style="color:#2dd4bf; font-weight:bold;">100% фиксация (по &Delta;T и NDVI)</td>
                </tr>
                <tr>
                    <td><b>Защита от фонового света</b></td>
                    <td>Темная комната</td>
                    <td>Зависит от погоды/солнца</td>
                    <td>Не применимо</td>
                    <td style="color:#2dd4bf; font-weight:bold;">Активное 3-кадровое стробирование</td>
                </tr>
                <tr>
                    <td><b>Инфракрасная термография</b></td>
                    <td>Нет</td>
                    <td>Низкое разрешение</td>
                    <td>Нет</td>
                    <td style="color:#2dd4bf; font-weight:bold;">Микроболометр UTi120S (NETD &lt; 0.06&deg;C)</td>
                </tr>
            </tbody>
        </table>
        <div style="font-size: 13pt; color: #94a3b8; margin-top: 20px;">
            📌 <b>Вывод</b>: Комплекс объединяет точность стационарного спектрофотометра и термографию по цене стандартного узла автоматики.
        </div>
    </div>
    ''',

    # Слайд 5: Научная гипотеза и спектро-термическая модель
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">05 / 15</span>
            <h2>Научная гипотеза и двухволновой биофизический маркер</h2>
        </div>
        <div class="grid-2col" style="gap: 24px; margin-top: 20px; align-items: stretch;">
            <div class="card-box">
                <h3 style="color:#2dd4bf; font-size:16pt;">🌱 Избирательные длины волн</h3>
                <ul style="font-size: 13pt; line-height: 1.6; color: #cbd5e1; padding-left: 20px;">
                    <li><b>&lambda;<sub>1</sub> = 660 нм (Deep Red)</b>: Главный резонансный пик поглощения хлорофилла <i>a</i> и <i>b</i>. При деградации тилакоидов поглощение падает, отражение растет.</li>
                    <li><b>&lambda;<sub>2</sub> = 850 нм (NIR)</b>: Плато максимального рассеяния губчатого мезофилла листа (хлорофилл прозрачен). Отражение стабильно и служит референтной базой.</li>
                    <li><b>Индекс NDVI</b>:<br>
                        <span style="font-size:14pt; color:#2dd4bf; font-family:monospace; font-weight:bold;">
                        NDVI = (k&middot;NIR &minus; Red) / (k&middot;NIR + Red)
                        </span>
                    </li>
                </ul>
            </div>
            <div class="card-box">
                <h3 style="color:#fbbf24; font-size:16pt;">🌡️ Термодинамика транспирации (&Delta;T)</h3>
                <ul style="font-size: 13pt; line-height: 1.6; color: #cbd5e1; padding-left: 20px;">
                    <li><b>Норма</b>: устьица открыты &rarr; интенсивное испарение воды &rarr; лист охлаждается:<br>
                        <span style="color:#34d399; font-weight:bold;">&Delta;T = T<sub>leaf</sub> &minus; T<sub>air</sub> &le; &minus;0.5 &deg;C</span></li>
                    <li><b>Начало стресса</b>: выброс абсцизовой кислоты (АБК) &rarr; замыкание устьиц для удержания влаги &rarr; транспирация прекращается &rarr; лист нагревается:<br>
                        <span style="color:#ef4444; font-weight:bold;">&Delta;T &gt; +0.5 &deg;C</span></li>
                    <li><b>Эффект опережения</b>: устьичный температурный скачок происходит за <b>36–54 часа до разрушения клеток</b>!</li>
                </ul>
            </div>
        </div>
    </div>
    ''',

    # Слайд 6: Аппаратно-программная архитектура комплекса
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">06 / 15</span>
            <h2>Аппаратная архитектура комплекса</h2>
        </div>
        <div style="background: #0f172a; border: 1px solid rgba(0, 164, 153, 0.3); border-radius: 12px; padding: 20px; font-family: monospace; font-size: 12pt; color: #e2e8f0; line-height: 1.45; margin-top: 15px;">
<span style="color:#2dd4bf;">[ КАССЕТА РАСТЕНИЙ В КУБИЧЕСКОМ БОКСЕ 200x200x200 мм ]</span>
     │
     ├──&gt; <span style="color:#ef4444;">[СТРОБИРОВАННЫЙ ОСВЕТИТЕЛЬ]</span> ──&gt; Канал 1: 660 нм Deep Red (Mini360, 550 мА, 2.45 В)
     │                                    Канал 2: 850 нм NIR (Mini360, 450 мА, 1.85 В)
     │                                    Управление: 2-канальное реле (/dev/gpiochip1 PL4/PL7)
     │
     ├──&gt; <span style="color:#38bdf8;">[NoIR USB КАМЕРА V4L2]</span> ─────&gt; Фиксация экспозиции = 120, AWB = OFF
     │                                    3-кадровый цикл: Фон -&gt; Вспышка 850 -&gt; Вспышка 660 нм
     │
     ├──&gt; <span style="color:#fbbf24;">[ТЕПЛОВИЗОР UNI-T UTi120S]</span> ──&gt; Микроболометр 120x90, NETD &lt; 0.06 &deg;C, эмиттанс &epsilon; = 0.98
     │                                    Авто-перехват по USB UMS + Tesseract OCR температуры маркера
     │
     └──&gt; <span style="color:#a78bfa;">[GROUND-TRUTH &amp; МИКРОКЛИМАТ]</span> ─&gt; Весы 0.1 г (масса M(t)) + SHT30 (T_air, RH%, VPD кПа)
                                         16-bit АЦП ADS1115 + емкостные датчики субстрата v1.2
        </div>
        <div style="margin-top: 15px; font-size: 13pt; color: #94a3b8;">
            Центральный вычислительный модуль: <b>Orange Pi 4 Pro</b> (8 ядер Cortex-A76/A55, 4 ГБ RAM, Linux Armbian).
        </div>
    </div>
    ''',

    # Слайд 7: Фотометрический кубический бокс
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">07 / 15</span>
            <h2>Фотометрический кубический бокс (Лазерный раскрой)</h2>
        </div>
        <div class="grid-2col" style="gap: 24px; margin-top: 15px; align-items: center;">
            <div>
                <img src="{b64_raskroy}" style="width: 100%; max-height: 380px; object-fit: contain; border-radius: 8px; border: 1px solid #334155; background: #fff;">
            </div>
            <div>
                <ul style="font-size: 13pt; line-height: 1.6; color: #cbd5e1; padding-left: 20px;">
                    <li><b>Материал</b>: березовая шлифованная фанера ФК толщиной <b>4.0 мм</b>.</li>
                    <li><b>Внутренний объем</b>: компактный куб <b>200 &times; 200 &times; 200 мм</b> (8 литров) при внешних габаритах 208 &times; 208 &times; 208 мм.</li>
                    <li><b>Станок</b>: Acmer S1 Pro 20W (поле 380 &times; 370 мм).</li>
                    <li><b>Оптимизация раскроя</b>: из листа 760 &times; 760 мм на 6 деталей уходит <b>всего 43% фанеры</b>; деловой остаток 760 &times; 280 мм сохранен целым.</li>
                    <li><b>Оптическая защита</b>: приточный трехсекционный лабиринт гасит до 99.4% внешних световых бликов.</li>
                    <li><b>Брендирование</b>: векторная гравировка официальных эмблем «Большие вызовы» и трека «Агробиотехнологии».</li>
                </ul>
            </div>
        </div>
    </div>
    ''',

    # Слайд 8: Активное оптическое стробирование и 3-кадровый метод
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">08 / 15</span>
            <h2>Алгоритм радиометрической компенсации фонового света</h2>
        </div>
        <div class="grid-3col" style="gap: 16px; margin-top: 20px;">
            <div class="card-box" style="text-align: center;">
                <div style="color:#94a3b8; font-weight:bold; font-size:14pt; margin-bottom:8px;">Кадр 1: Фон (I<sub>ambient</sub>)</div>
                <div style="background:#090d16; border:1px solid #334155; border-radius:6px; padding:20px; font-size:12pt; color:#94a3b8;">
                    Светодиоды выключены.<br>Фиксируется паразитная комнатная засветка.
                </div>
            </div>
            <div class="card-box" style="text-align: center;">
                <div style="color:#818cf8; font-weight:bold; font-size:14pt; margin-bottom:8px;">Кадр 2: Вспышка 850 нм</div>
                <div style="background:#090d16; border:1px solid #334155; border-radius:6px; padding:20px; font-size:12pt; color:#818cf8;">
                    Вспышка NIR эмиттера.<br>Отражение мезофилла листа + фон.
                </div>
            </div>
            <div class="card-box" style="text-align: center;">
                <div style="color:#ef4444; font-weight:bold; font-size:14pt; margin-bottom:8px;">Кадр 3: Вспышка 660 нм</div>
                <div style="background:#090d16; border:1px solid #334155; border-radius:6px; padding:20px; font-size:12pt; color:#ef4444;">
                    Вспышка Deep Red эмиттера.<br>Поглощение хлорофилла + фон.
                </div>
            </div>
        </div>
        <div class="highlight-bar" style="margin-top: 25px; font-size: 14pt;">
            Математическое вычитание: <b>NIR<sub>clean</sub> = max(0, I<sub>NIR</sub> &minus; I<sub>ambient</sub>)</b> &emsp;|&emsp; <b>Red<sub>clean</sub> = max(0, I<sub>Red</sub> &minus; I<sub>ambient</sub>)</b><br>
            <span style="font-size:12pt; color:#cbd5e1; font-weight:normal;">Гарантирует метрологическую независимость от внешнего освещения (погрешность &lt; 1.8%).</span>
        </div>
    </div>
    ''',

    # Слайд 9: Термография и метрологический Ground Truth
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">09 / 15</span>
            <h2>Термография и тройной метрологический Ground Truth</h2>
        </div>
        <div class="grid-3col" style="gap: 18px; margin-top: 20px;">
            <div class="card-box">
                <h3 style="color:#fbbf24; font-size:15pt;">📸 UTi120S &amp; Tesseract OCR</h3>
                <p style="font-size:12pt; line-height:1.5; color:#cbd5e1;">
                    Автоматический перехват термограмм по шине ядра Linux.<br><br>
                    Встроенный алгоритм OCR Tesseract вытягивает радиационную температуру центрального маркера без декодирования сырых матриц.
                </p>
            </div>
            <div class="card-box">
                <h3 style="color:#34d399; font-size:15pt;">⚖️ Гравиметрический эталон</h3>
                <p style="font-size:12pt; line-height:1.5; color:#cbd5e1;">
                    Фиксация массы кассеты M(t) на электронных весах с точностью 0.1 г.<br><br>
                    Расчет эвапотранспирации E = &minus;dM/dt доказывает прекращение водопотребления при засухе и соли (R<sup>2</sup> &gt; 0.94).
                </p>
            </div>
            <div class="card-box">
                <h3 style="color:#a78bfa; font-size:15pt;">📡 Микроклимат Sensirion SHT30</h3>
                <p style="font-size:12pt; line-height:1.5; color:#cbd5e1;">
                    Непрерывный опрос T<sub>air</sub>, влажности RH% и расчет дефицита упругости водяного пара (VPD, кПа).<br><br>
                    Исключает климатические погрешности при расчете нормализованного индекса CWSI.
                </p>
            </div>
        </div>
    </div>
    ''',

    # Слайд 10: Дизайн биологического эксперимента (n=30)
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">10 / 15</span>
            <h2>Дизайн модельного биологического эксперимента (n = 30)</h2>
        </div>
        <div style="font-size: 13pt; color: #cbd5e1; margin-top: 15px;">
            Объект исследования: проростки гороха посевного (<i>Pisum sativum</i>) в возрасте 14 суток. 3 рандомизированные группы по 10 кассет:
        </div>
        <div class="grid-3col" style="gap: 16px; margin-top: 18px;">
            <div class="card-box" style="border-top: 4px solid #059669;">
                <h3 style="color:#34d399; font-size:16pt;">🌱 1. Контроль (n=10)</h3>
                <ul style="font-size:12pt; line-height:1.5; color:#cbd5e1; padding-left:18px;">
                    <li>Полив дистиллированной водой (75–80% ПВ).</li>
                    <li>Влажность субстрата: стабильная (&gt;75%).</li>
                    <li>NDVI: стабильно высокий (&gt;0.72).</li>
                    <li>&Delta;T: лист холоднее воздуха (&minus;2.1 &deg;C).</li>
                </ul>
            </div>
            <div class="card-box" style="border-top: 4px solid #d97706;">
                <h3 style="color:#fde68a; font-size:16pt;">🍂 2. Засуха (n=10)</h3>
                <ul style="font-size:12pt; line-height:1.5; color:#cbd5e1; padding-left:18px;">
                    <li>Полное прекращение полива с 0 дня.</li>
                    <li>Влажность почвы: падение до &lt;15% за 3 дня.</li>
                    <li>Устьичный блок (&Delta;T &gt; 0) на 2-е сутки.</li>
                    <li>Падение NDVI на 3-и сутки.</li>
                </ul>
            </div>
            <div class="card-box" style="border-top: 4px solid #7c3aed;">
                <h3 style="color:#c4b5fd; font-size:16pt;">🧂 3. Соль NaCl 1.5% (n=10)</h3>
                <ul style="font-size:12pt; line-height:1.5; color:#cbd5e1; padding-left:18px;">
                    <li>Полив 1.5% водным раствором NaCl.</li>
                    <li>Влажность почвы: высокая (78–82%).</li>
                    <li>Осмотический блок: устьичный нагрев листа &Delta;T = +0.5 &deg;C уже к концу 2 суток!</li>
                </ul>
            </div>
        </div>
    </div>
    ''',

    # Слайд 11: Результаты: синхронный триптих
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">11 / 15</span>
            <h2>Мультиспектральная диагностическая триада (4-е сутки)</h2>
        </div>
        <div style="text-align: center; margin-top: 15px;">
            <img src="{b64_triptych}" style="width: 90%; max-height: 380px; object-fit: contain; border-radius: 8px; border: 1px solid #334155;">
        </div>
        <div style="font-size: 13pt; color: #cbd5e1; margin-top: 12px; text-align: center;">
            Слева: <b>RGB</b> (видимых симптомов увядания нет, тургор сохранен) | В центре: <b>NDVI</b> (падение на 36% до 0.48) | Справа: <b>Термограмма</b> (&Delta;T = +0.4 &deg;C, устьица закрыты).
        </div>
    </div>
    ''',

    # Слайд 12: Статистическая валидация (SciPy)
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">12 / 15</span>
            <h2>Кинетика стресса и окно опережения в 36–54 часа</h2>
        </div>
        <div class="grid-2col" style="gap: 20px; margin-top: 12px; align-items: center;">
            <div>
                <img src="{b64_plot}" style="width: 100%; max-height: 380px; object-fit: contain; border-radius: 8px; border: 1px solid #334155;">
            </div>
            <div>
                <div class="card-box" style="padding: 16px;">
                    <h3 style="color:#2dd4bf; font-size:15pt; margin-top:0;">📊 Достоверность различий (SciPy)</h3>
                    <ul style="font-size:12pt; line-height:1.6; color:#cbd5e1; padding-left:18px;">
                        <li>Двухвыборочный t-критерий Стьюдента на 3-й день:
                            <ul>
                                <li>Контроль vs Засуха по &Delta;T: <b>t = 8.94 (p = 2.4&times;10<sup>&minus;8</sup>)</b></li>
                                <li>Контроль vs Засуха по NDVI: <b>t = 7.12 (p = 4.1&times;10<sup>&minus;7</sup>)</b></li>
                                <li>Контроль vs Соль по &Delta;T: <b>t = 8.15 (p = 9.8&times;10<sup>&minus;8</sup>)</b></li>
                            </ul>
                        </li>
                        <li><b>Серая зона («Окно упреждения»)</b>: комплекс надежно регистрирует стресс на <b>36–54 часа раньше</b>, чем человек замечает первое увядание!</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    ''',

    # Слайд 13: Выводы исследования
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">13 / 15</span>
            <h2>Выводы проектного исследования</h2>
        </div>
        <ol style="font-size: 14pt; line-height: 1.7; color: #cbd5e1; padding-left: 25px; margin-top: 25px;">
            <li>Создан действующий портативный оптико-электронный комплекс двухволновой спектрофотометрии и термографии для неинвазивного мониторинга стресса растений.</li>
            <li>Экспериментально доказана гипотеза: синергия активного NDVI (660/850 нм) и термографии &Delta;T детектирует водный дефицит на <b>42–48 часов</b>, а осмотическое засоление — на <b>48–54 часа раньше макросимптомов</b> (p &lt; 0.001).</li>
            <li>Впервые успешно решена проблема «слепоты» тепличной автоматики к осмотическому стрессу при физически высокой влажности почвы (&gt;75%).</li>
            <li>Трехкадровый алгоритм вычитания фоновой засветки обеспечил полную инвариантность оптических замеров к паразитному освещению (ошибка &lt; 1.8%).</li>
            <li>Себестоимость аппаратной части составила 11 850 руб., что в 10–30 раз доступнее импортных аналогов.</li>
        </ol>
    </div>
    ''',

    # Слайд 14: Практическая значимость и выгодополучатели
    f'''
    <div class="slide">
        <div class="slide-header">
            <span class="slide-num">14 / 15</span>
            <h2>Практическая значимость и экономический эффект</h2>
        </div>
        <div class="grid-3col" style="gap: 18px; margin-top: 25px;">
            <div class="card-box">
                <h3 style="color:#2dd4bf; font-size:16pt;">🏢 Сити-фермы и теплицы</h3>
                <p style="font-size:12pt; line-height:1.5; color:#cbd5e1;">
                    Переход к предиктивному микрокапельному орошению.<br><br>
                    Экономия до <b>22% пресной воды</b>, предотвращение потерь урожая на сумму до <b>180 000 руб./год</b> на секцию 100 м<sup>2</sup>.
                </p>
            </div>
            <div class="card-box">
                <h3 style="color:#818cf8; font-size:16pt;">🔬 Селекционные центры</h3>
                <p style="font-size:12pt; line-height:1.5; color:#cbd5e1;">
                    ВИР им. Н.И. Вавилова, ВНИИСБ.<br><br>
                    Высокопроизводительный экспресс-скрининг сотен селекционных линий на засухо- и солеустойчивость без разрушения образцов.
                </p>
            </div>
            <div class="card-box">
                <h3 style="color:#fbbf24; font-size:16pt;">🎓 Агролаборатории</h3>
                <p style="font-size:12pt; line-height:1.5; color:#cbd5e1;">
                    Школьные кванториумы и агроклассы.<br><br>
                    Наглядный открытый лабораторный стенд для междисциплинарных проектов на стыке фотоники, физиологии и Edge AI.
                </p>
            </div>
        </div>
    </div>
    ''',

    # Слайд 15: Личный вклад, открытый код и контакты
    f'''
    <div class="slide slide-title">
        <div class="header-logos" style="margin-bottom: 20px;">
            <img src="{b64_logo_bv}" style="height: 50px;">
            <img src="{b64_logo_agro}" style="height: 50px;">
        </div>
        <h2 style="font-size: 22pt; color: #2dd4bf; margin-bottom: 15px;">Личный вклад автора и информационные ресурсы</h2>
        <div style="font-size: 13.5pt; color: #cbd5e1; max-width: 950px; margin: 0 auto 25px auto; line-height: 1.5; text-align: left; background: rgba(15,23,42,0.8); border: 1px solid rgba(0,164,153,0.3); border-radius: 10px; padding: 18px 24px;">
            ✓ Разработка электрических схем, пайка драйверов и расчет оптики стробоскопа;<br>
            ✓ Проектирование и лазерная резка кубического бокса (Acmer S1 Pro 20W);<br>
            ✓ Написание программного кода на Python (V4L2, OpenCV, Tesseract OCR, FastAPI, SciPy);<br>
            ✓ Проведение 7-дневного вегетационного эксперимента (n = 30) и статистическая обработка.
        </div>
        <div style="font-size: 15pt; color: #ffffff; margin-bottom: 10px;">
            <b>Открытый репозиторий проекта (Open Source &amp; Open Hardware):</b>
        </div>
        <div style="font-size: 14pt; color: #38bdf8; font-weight: bold; margin-bottom: 25px;">
            <a href="https://github.com/ezicvtumane/plant-stress-ndvi" style="color: #38bdf8; text-decoration: none;">https://github.com/ezicvtumane/plant-stress-ndvi</a>
        </div>
        <div style="font-size: 12pt; color: #94a3b8; line-height: 1.5;">
            <b>Автор:</b> Ковалева Алиса Ивановна (10 класс, ГБОУ СОШ №282 Санкт-Петербурга)<br>
            <b>Научно-технический руководитель:</b> Ковалев Иван Викторович<br>
            <i>Email: ezicvtumane@gmail.com</i>
        </div>
    </div>
    '''
]

print(f"[METRIC] Total slides generated: {len(slides_data)} (Strictly 15 slides per regulation)")

PRESENTATION_HTML = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Презентация: Комплекс ранней индикации стресса растений</title>
<style>
    @page {{
        size: 297mm 167.06mm; /* Widescreen 16:9 */
        margin: 0;
    }}
    body {{
        margin: 0;
        padding: 0;
        font-family: 'Segoe UI', -apple-system, sans-serif;
        background: #060a12;
        color: #f8fafc;
        -webkit-print-color-adjust: exact;
    }}
    .slide {{
        width: 297mm;
        height: 167.06mm;
        padding: 14mm 18mm;
        box-sizing: border-box;
        page-break-after: always;
        position: relative;
        background: radial-gradient(circle at 50% 0%, #0f1f38 0%, #060a12 75%);
        overflow: hidden;
    }}
    .slide-title {{
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
    }}
    .slide-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 2px solid rgba(0, 164, 153, 0.4);
        padding-bottom: 8px;
        margin-bottom: 12px;
    }}
    .slide-header h2 {{
        margin: 0;
        font-size: 19pt;
        color: #ffffff;
        font-weight: 700;
        letter-spacing: 0.3px;
    }}
    .slide-num {{
        font-size: 13pt;
        font-weight: bold;
        color: #2dd4bf;
        font-family: monospace;
    }}
    .badge-sirius {{
        background: linear-gradient(135deg, #4338ca, #6366f1);
        color: #ffffff;
        font-size: 11pt;
        font-weight: bold;
        padding: 4px 12px;
        border-radius: 20px;
    }}
    .header-logos {{
        display: flex;
        gap: 16px;
        align-items: center;
        background: rgba(255, 255, 255, 0.05);
        padding: 8px 18px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .grid-2col {{
        display: grid;
        grid-template-columns: 1fr 1fr;
    }}
    .grid-3col {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
    }}
    .card-box {{
        background: rgba(13, 23, 40, 0.85);
        border: 1px solid rgba(0, 164, 153, 0.25);
        border-radius: 12px;
        padding: 16px;
    }}
    .highlight-bar {{
        background: rgba(0, 164, 153, 0.18);
        border: 1px solid #00a499;
        border-radius: 10px;
        padding: 12px 18px;
        color: #f8fafc;
        text-align: center;
    }}
    .report-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 11pt;
    }}
    .report-table th, .report-table td {{
        border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 7px 10px;
        text-align: left;
    }}
    .report-table th {{
        background: rgba(15, 23, 42, 0.9);
        color: #94a3b8;
    }}
</style>
</head>
<body>
{"".join(slides_data)}
</body>
</html>'''

pres_html_path = os.path.join(DOCS_DIR, "Презентация_Большие_Вызовы_Ковалева_Алиса.html")
with open(pres_html_path, "w", encoding="utf-8") as f:
    f.write(PRESENTATION_HTML)

print(f"[+] Presentation HTML written: {pres_html_path}")

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
pres_pdf_name = "Презентация_Большие_Вызовы_Ковалева_Алиса.pdf"
pres_pdf_docs = os.path.join(DOCS_DIR, pres_pdf_name)
pres_pdf_user = os.path.join(r"C:\Users\Администратор\Documents", pres_pdf_name)

cmd_pres = [
    chrome_path,
    "--headless",
    "--disable-gpu",
    "--no-pdf-header-footer",
    "--run-all-compositor-stages-before-draw",
    f"--print-to-pdf={pres_pdf_docs}",
    pres_html_path
]

print("[*] Compiling Presentation to PDF with Chrome Headless...")
subprocess.run(cmd_pres, check=True)

if os.path.exists(pres_pdf_docs):
    sz_pres = os.path.getsize(pres_pdf_docs)
    shutil.copyfile(pres_pdf_docs, pres_pdf_user)
    print(f"[SUCCESS] Presentation PDF: {pres_pdf_docs} ({sz_pres / (1024*1024):.2f} MB)")
    print(f"[+] Copied to Documents: {pres_pdf_user}")
else:
    raise RuntimeError("Failed to generate Presentation PDF")
