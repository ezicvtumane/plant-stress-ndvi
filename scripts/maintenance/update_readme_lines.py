with open('/home/pi/plant-stress-ndvi/README.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_block = [
    "### 🎯 Радиометрическая калибровка по белому диффузному эталону PTFE (White Reference)\n",
    "\n",
    "Для компенсации неравномерности спектральной чувствительности кремниевой матрицы NoIR (Logitech C270) в диапазонах 660 нм и 850 нм, температурного дрейфа светодиодов и погрешностей драйверов Mini360 используется эталон из **чистого фторопласта (PTFE / ФУМ-лента 15–20 слоев)**. Он обеспечивает идеальное ламбертовское рассеивание света без зеркального клиппинга (0.0% пересвеченных пикселей) и строго нулевой базовый уровень $\\text{NDVI}_{\\text{ref}} \\equiv 0.000$.\n",
    "\n",
    "* **Аппаратный калиброванный коэффициент**: натурно измеренные значения чистых сигналов $DN_{660} = 195.2$, $DN_{850} = 48.0$ определяют базовый баланс излучателей:\n",
    "\n",
    "$$\n",
    "k_{\\text{bal}} = \\frac{DN_{660}^{\\text{white}}}{DN_{850}^{\\text{white}}} = \\frac{195.2}{48.0} \\approx 4.07\n",
    "$$\n",
    "\n",
    "* **Двухуровневая архитектура**:\n",
    "  1. *Штатный режим (когорты 1–5)*: автоматическая загрузка $k_{\\text{bal}} = 4.07$ из `data/calibrated_k_bal.txt` без необходимости размещения эталона в кадре;\n",
    "  2. *Режим перекалибровки («Стенд №0», маркер ArUco #6)*: автоматическая локализация мишени по пику яркости (`cv2.minMaxLoc`), расчет актуального отношения $RED/NIR$ и обновление персистентного файла.\n",
    "\n"
]

start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if "### 🎯 Радиометрическая калибровка" in line:
        start_idx = i
    if "### 🏷️ Оптическая фидуциальная маркировка" in line:
        end_idx = i

if start_idx is not None and end_idx is not None:
    lines = lines[:start_idx] + new_block + lines[end_idx:]
    with open('/home/pi/plant-stress-ndvi/README.md', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("README.md replaced successfully by line index!")
else:
    print(f"Indices not found: start={start_idx}, end={end_idx}")
