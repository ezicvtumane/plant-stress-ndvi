import os
import subprocess
import shutil

html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Схема подключения электроники Orange Pi 4 Pro</title>
<style>
    @page {
        size: A4 portrait;
        margin: 10mm 12mm 10mm 12mm;
    }
    body {
        font-family: 'Segoe UI', -apple-system, Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        margin: 0;
        padding: 0;
        font-size: 10.5px;
        line-height: 1.35;
    }
    .header {
        border-bottom: 2px solid #00a499;
        padding-bottom: 6px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }
    .title {
        font-size: 17px;
        font-weight: 800;
        color: #0f172a;
        margin: 0;
        letter-spacing: -0.3px;
    }
    .subtitle {
        font-size: 10.5px;
        color: #00a499;
        font-weight: 600;
        margin-top: 2px;
    }
    .meta {
        font-size: 9px;
        color: #64748b;
        text-align: right;
    }
    
    .section-title {
        font-size: 12px;
        font-weight: 700;
        color: #0f172a;
        border-left: 3.5px solid #00a499;
        padding-left: 7px;
        margin: 10px 0 6px 0;
    }

    .img-container {
        text-align: center;
        margin: 8px 0;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 6px;
    }
    .img-container img {
        max-width: 98%;
        max-height: 190px;
        object-fit: contain;
    }
    
    .pinout-container {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 6px 8px;
        margin-bottom: 8px;
    }
    .pin-table {
        border-collapse: collapse;
        width: 100%;
        font-size: 9px;
    }
    .pin-table th {
        background: #0f172a;
        color: #fff;
        padding: 3px 5px;
        text-align: center;
        font-size: 8.5px;
        letter-spacing: 0.5px;
    }
    .pin-table td {
        padding: 2.5px 5px;
        border-bottom: 1px solid #e2e8f0;
    }
    .pin-num {
        font-weight: 800;
        text-align: center;
        width: 22px;
        background: #e2e8f0;
        border-radius: 3px;
    }
    
    .p-3v3 { background: #ffedd5; color: #9a3412; font-weight: 700; }
    .p-5v  { background: #fee2e2; color: #991b1b; font-weight: 700; }
    .p-gnd { background: #1e293b; color: #f8fafc; font-weight: 700; }
    .p-i2c { background: #dbeafe; color: #1e40af; font-weight: 700; }
    .p-gpio{ background: #fef08a; color: #854d0e; font-weight: 700; }
    .p-nc  { color: #94a3b8; }

    /* Module Cards */
    .grid-2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 8px;
    }
    .card {
        background: #ffffff;
        border: 1.2px solid #e2e8f0;
        border-radius: 5px;
        padding: 6px 8px;
        box-sizing: border-box;
    }
    .card-title {
        font-weight: 700;
        font-size: 10.5px;
        margin-bottom: 5px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .badge {
        font-size: 8px;
        font-weight: 700;
        padding: 1.5px 5px;
        border-radius: 3px;
        text-transform: uppercase;
    }
    .badge-i2c { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
    .badge-ana { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
    .badge-pwr { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }

    table.conn-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 9px;
    }
    table.conn-table th {
        background: #f1f5f9;
        color: #475569;
        font-weight: 600;
        padding: 2.5px 4px;
        text-align: left;
        border-bottom: 1px solid #cbd5e1;
    }
    table.conn-table td {
        padding: 2.5px 4px;
        border-bottom: 1px solid #f1f5f9;
    }
    .wire-red { color: #dc2626; font-weight: 700; }
    .wire-black { color: #0f172a; font-weight: 700; }
    .wire-blue { color: #2563eb; font-weight: 700; }
    .wire-yellow { color: #ca8a04; font-weight: 700; }
    .wire-green { color: #16a34a; font-weight: 700; }

    .alert {
        background: #fffbeb;
        border: 1.2px solid #f59e0b;
        border-radius: 5px;
        padding: 6px 8px;
        margin: 6px 0;
        font-size: 9px;
    }
    .alert-danger {
        background: #fef2f2;
        border-color: #ef4444;
    }
</style>
</head>
<body>

<div class="header">
    <div>
        <h1 class="title">СХЕМА ПОДКЛЮЧЕНИЯ ЭЛЕКТРОНИКИ СТАНЦИИ</h1>
        <div class="subtitle">Микрокомпьютер: Orange Pi 4 Pro V1.3.2 | Проект экспресс-диагностики стресса (Сириус 2026)</div>
    </div>
    <div class="meta">
        Версия: 2.2 Hardware<br>
        Шина: TWI0 / I2C-0 (3.3V)<br>
        Дата: 01.10.2026
    </div>
</div>

<div class="img-container">
    <img src="opi4pro_pinout.png" alt="Orange Pi 4 Pro V1.3.2 Pinout">
</div>

<div class="alert alert-danger" style="margin-top:2px;">
    <b>КРИТИЧЕСКОЕ ПРАВИЛО:</b> Датчики SHT30, ADS1115 и датчик почвы питаются <b>СТРОГО от 3.3V (Пин 1)</b>! Подача 5.0V на линии TWI0 (SDA/SCL) выведет процессор Orange Pi из строя! Напряжение 5.0V (Пин 2) идёт <b>ТОЛЬКО</b> на клемму VCC реле.
</div>

<div class="section-title">1. Карта задействованных контактов 40-пиновой гребенки Orange Pi 4 Pro</div>

<div class="pinout-container">
    <table class="pin-table">
        <thead>
            <tr>
                <th colspan="2" style="background:#00a499;">НАРУЖНЫЙ РЯД (НЕЧЕТНЫЙ)</th>
                <th>№</th>
                <th>№</th>
                <th colspan="2" style="background:#0f766e;">ВНУТРЕННИЙ РЯД (ЧЕТНЫЙ)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td class="p-3v3">3.3V Power (Питание датчиков)</td>
                <td style="color:#059669; font-weight:bold;">К SHT30, ADS1115 и датчику почвы</td>
                <td class="pin-num p-3v3">1</td>
                <td class="pin-num p-5v">2</td>
                <td style="color:#dc2626; font-weight:bold;">К VCC модуля Реле (питание катушек)</td>
                <td class="p-5v">5.0V Power</td>
            </tr>
            <tr>
                <td class="p-i2c">PB3 / TWI0_SDA (Данные I2C)</td>
                <td style="color:#2563eb; font-weight:bold;">К SDA на SHT30 и ADS1115</td>
                <td class="pin-num p-i2c">3</td>
                <td class="pin-num p-nc">4</td>
                <td class="p-nc">— (Не задействован)</td>
                <td class="p-nc">5V / NC</td>
            </tr>
            <tr>
                <td class="p-i2c">PB2 / TWI0_SCK (Такты I2C)</td>
                <td style="color:#ca8a04; font-weight:bold;">К SCL на SHT30 и ADS1115</td>
                <td class="pin-num p-i2c">5</td>
                <td class="pin-num p-gnd">6</td>
                <td style="color:#1e293b; font-weight:bold;">К GND на SHT30, ADS1115 и почве</td>
                <td class="p-gnd">GND (Общая земля)</td>
            </tr>
            <tr>
                <td class="p-gpio">PL4 / S_PWM0_2 (Line 4 на gpiochip1)</td>
                <td style="color:#854d0e; font-weight:bold;">К IN1 Реле (Строб ИК 850 нм)</td>
                <td class="pin-num p-gpio">7</td>
                <td class="pin-num p-nc">8</td>
                <td class="p-nc">PL6 / UART7_TX (Свободен)</td>
                <td class="p-nc">UART7_TX</td>
            </tr>
            <tr>
                <td class="p-gnd">GND (Земля модуля реле)</td>
                <td style="color:#1e293b; font-weight:bold;">К GND модуля Реле</td>
                <td class="pin-num p-gnd">9</td>
                <td class="pin-num p-gpio">10</td>
                <td style="color:#854d0e; font-weight:bold;">К IN2 Реле (Строб Red 660 нм)</td>
                <td class="p-gpio">PL7 / UART7_RX (Line 7 на gpiochip1)</td>
            </tr>
        </tbody>
    </table>
</div>

<div class="section-title">2. Детальная раскладка подключения по модулям</div>

<div class="grid-2">
    <!-- Card SHT30 -->
    <div class="card">
        <div class="card-title">
            <span>1. Датчик микроклимата SHT30</span>
            <span class="badge badge-i2c">I2C (0x44)</span>
        </div>
        <table class="conn-table">
            <thead><tr><th>Пин SHT30</th><th>Провод</th><th>Пин Orange Pi 4 Pro</th><th>Назначение</th></tr></thead>
            <tbody>
                <tr><td><b>VIN</b></td><td class="wire-red">Красный</td><td><b>Пин 1 (3.3V)</b></td><td>Питание 3.3V</td></tr>
                <tr><td><b>GND</b></td><td class="wire-black">Черный</td><td><b>Пин 6 (GND)</b></td><td>Общий минус</td></tr>
                <tr><td><b>SDA</b></td><td class="wire-blue">Синий</td><td><b>Пин 3 (PB3 / TWI0_SDA)</b></td><td>Данные I2C</td></tr>
                <tr><td><b>SCL</b></td><td class="wire-yellow">Желтый</td><td><b>Пин 5 (PB2 / TWI0_SCK)</b></td><td>Такты I2C</td></tr>
                <tr><td>ADDR / ALR</td><td>—</td><td>Не подключать</td><td>По умолч. адрес 0x44</td></tr>
            </tbody>
        </table>
    </div>

    <!-- Card ADS1115 -->
    <div class="card">
        <div class="card-title">
            <span>2. 16-битный АЦП ADS1115</span>
            <span class="badge badge-i2c">I2C (0x48)</span>
        </div>
        <table class="conn-table">
            <thead><tr><th>Пин ADS1115</th><th>Провод</th><th>Куда подключить</th><th>Назначение</th></tr></thead>
            <tbody>
                <tr><td><b>VDD</b></td><td class="wire-red">Красный</td><td><b>Пин 1 (3.3V)</b></td><td>Питание 3.3V</td></tr>
                <tr><td><b>GND</b></td><td class="wire-black">Черный</td><td><b>Пин 6 (GND)</b></td><td>Общий минус</td></tr>
                <tr><td><b>SDA</b></td><td class="wire-blue">Синий</td><td><b>Пин 3 (PB3 / TWI0_SDA)</b></td><td>Параллельно к шине I2C</td></tr>
                <tr><td><b>SCL</b></td><td class="wire-yellow">Желтый</td><td><b>Пин 5 (PB2 / TWI0_SCK)</b></td><td>Параллельно к шине I2C</td></tr>
                <tr><td><b>ADDR</b></td><td class="wire-black">Черный</td><td><b>К GND модуля</b> (перемычка)</td><td>Фиксация адреса 0x48</td></tr>
                <tr><td><b>A0</b></td><td class="wire-green">Зеленый</td><td><b>К сигнальному проводу почвы</b></td><td>Аналоговый вход (0..3V)</td></tr>
            </tbody>
        </table>
    </div>
</div>

<div class="grid-2">
    <!-- Card Soil Sensor -->
    <div class="card">
        <div class="card-title">
            <span>3. Емкостной датчик влажности v1.2</span>
            <span class="badge badge-ana">Аналог (0..3.0V)</span>
        </div>
        <table class="conn-table">
            <thead><tr><th>Контакт</th><th>Цвет</th><th>Куда подключать</th></tr></thead>
            <tbody>
                <tr><td><b>VCC</b></td><td class="wire-red">Красный</td><td><b>3.3V</b> (Пин 1 или контакт VDD на плате ADS1115)</td></tr>
                <tr><td><b>GND</b></td><td class="wire-black">Черный</td><td><b>GND</b> (Пин 6 или контакт GND на плате ADS1115)</td></tr>
                <tr><td><b>AOUT (Signal)</b></td><td class="wire-yellow">Желтый</td><td><b>Пин A0</b> на плате АЦП ADS1115</td></tr>
            </tbody>
        </table>
        <div style="font-size:8px; color:#64748b; margin-top:4px;">
            *Лезвие постоянно находится в субстрате кассеты. К станции подключается только 3-пиновый разъем при установке кассеты.
        </div>
    </div>

    <!-- Card Relay -->
    <div class="card">
        <div class="card-title">
            <span>4. Модуль реле подсветки (2 канала)</span>
            <span class="badge badge-pwr">5.0V / GPIO</span>
        </div>
        <table class="conn-table">
            <thead><tr><th>Пин Реле</th><th>Провод</th><th>Пин Orange Pi 4 Pro</th><th>Назначение</th></tr></thead>
            <tbody>
                <tr><td><b>VCC</b></td><td class="wire-red">Красный</td><td><b>Пин 2 (5.0V)</b></td><td>Питание катушек реле</td></tr>
                <tr><td><b>GND</b></td><td class="wire-black">Черный</td><td><b>Пин 9 (GND)</b></td><td>Общая земля</td></tr>
                <tr><td><b>IN1</b></td><td class="wire-blue">Синий</td><td><b>Пин 7 (PL4, Line 4)</b></td><td>Управление ИК 850 нм</td></tr>
                <tr><td><b>IN2</b></td><td class="wire-yellow">Желтый</td><td><b>Пин 10 (PL7, Line 7)</b></td><td>Управление Red 660 нм</td></tr>
            </tbody>
        </table>
        <div style="font-size:8px; color:#64748b; margin-top:4px;">
            *Пины 7, 9, 10 расположены компактным треугольником на плате, что удобно для стандартного шлейфа.
        </div>
    </div>
</div>

<div class="section-title">3. Силовая цепь коммутации светодиодов (Вспышка)</div>

<div class="card" style="margin-bottom: 8px;">
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; font-size:9px;">
        <div>
            <b>Канал 1: Ближний ИК строб (850 нм):</b>
            <ul style="margin:2px 0 0 14px; padding:0;">
                <li>Источник +5V БП $\rightarrow$ клемма <b>COM1</b> реле.</li>
                <li>Клемма <b>NO1</b> $\rightarrow$ <b>Резистор 4.7–6.8 Ом (5 Вт)</b> $\rightarrow$ Анод (+) 3W 850NM.</li>
                <li>Катод (-) светодиода $\rightarrow$ Минус источника (GND).</li>
            </ul>
        </div>
        <div>
            <b>Канал 2: Красный спектральный строб (660 нм):</b>
            <ul style="margin:2px 0 0 14px; padding:0;">
                <li>Источник +5V БП $\rightarrow$ клемма <b>COM2</b> реле.</li>
                <li>Клемма <b>NO2</b> $\rightarrow$ <b>Резистор 3.3–4.7 Ом (5 Вт)</b> $\rightarrow$ Анод (+) Red 660nm.</li>
                <li>Катод (-) светодиода $\rightarrow$ Минус источника (GND).</li>
            </ul>
        </div>
    </div>
</div>

<div class="section-title">4. Пошаговая проверка после сборки</div>

<ol style="margin: 0; padding-left: 16px; font-size: 9px; line-height: 1.4;">
    <li><b>Прозвонка мультиметром (до подачи питания!):</b> Проверьте сопротивление между Пином 1 (3.3V) и Пином 6 (GND). Оно должно быть бесконечным/высоким (не коротит).</li>
    <li><b>Подача питания:</b> Включите Orange Pi. Выполните команду сканирования шины: <code>i2cdetect -y 0</code>.</li>
    <li><b>Верификация адресов:</b> В сетке должны отобразиться <b>0x44</b> (микроклимат SHT30) и <b>0x48</b> (АЦП ADS1115).</li>
    <li><b>Проверка влажности:</b> На воздухе датчик выдает ~2.8–3.0 В (0%). При опускании в воду напряжение падает до ~1.2–1.4 В (100%).</li>
    <li><b>Проверка реле:</b> При нажатии кнопки «Выполнить замер» в веб-интерфейсе станции реле должно сделать два синхронных щелчка со стробом 0.4 с.</li>
</ol>

</body>
</html>
"""

html_path = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\docs\Схема_подключения_электроники.html"
pdf_path = r"c:\Users\Администратор\Documents\Coglet\plant-stress-ndvi\docs\Схема_подключения_электроники_Orange_Pi.pdf"
doc_pdf = r"C:\Users\Администратор\Documents\Схема_подключения_электроники_Orange_Pi.pdf"

os.makedirs(os.path.dirname(html_path), exist_ok=True)
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)
print("Saved HTML:", html_path)

chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(chrome_exe):
    chrome_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

cmd = [
    chrome_exe,
    "--headless",
    "--disable-gpu",
    f"--print-to-pdf={pdf_path}",
    html_path
]

print("Running headless PDF print...")
res = subprocess.run(cmd, capture_output=True, text=True)
print("Returncode:", res.returncode)

if os.path.exists(pdf_path):
    print("PDF successfully generated! Size:", os.path.getsize(pdf_path), "bytes")
    shutil.copy(pdf_path, doc_pdf)
    print("Copied to user Documents:", doc_pdf)
else:
    print("Error: PDF not found!")
