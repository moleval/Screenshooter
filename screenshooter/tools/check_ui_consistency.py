"""
Статический анализ UI-кода.
Проверяет:
- HEX-цвета в строках, содержащих setStyleSheet, вне theme.py и widgets/
- хардкод размеров 59 и 360 вне layout_metrics.py, кроме widgets/ и tools/
- структуру EditorToolbarStrip (два разделителя)
- отсутствие setFixedWidth в ThicknessWidget и ColorPaletteWidget

Запуск: python screenshooter/tools/check_ui_consistency.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCREENS_DIR = os.path.join(ROOT, 'screenshooter')

# Директории, которые не проверяем на HEX-цвета (локальные стили)
EXCLUDE_HEX_DIRS = {'widgets', 'tools'}
# Директории, которые не проверяем на хардкод размеров
EXCLUDE_SIZE_DIRS = {'widgets', 'tools', 'capture', 'items', 'controllers', 'history', 'image_processing'}
HARDCODED_NUMBERS = {59, 360}

problems = []

for dirpath, dirnames, filenames in os.walk(SCREENS_DIR):
    current_dir = os.path.basename(dirpath)

    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, ROOT)

        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 1. HEX-цвета в строках, содержащих setStyleSheet
        if current_dir not in EXCLUDE_HEX_DIRS and 'theme.py' not in fn:
            for i, line in enumerate(lines):
                if 'setStyleSheet' in line and re.search(r'#[0-9a-fA-F]{6}', line):
                    problems.append(f"{rel}: HEX-цвет в setStyleSheet (строка {i+1})")
                    break  # достаточно одного нарушения на файл

        # 2. Хардкод размеров (59 и 360)
        if current_dir not in EXCLUDE_SIZE_DIRS and 'layout_metrics.py' not in fn:
            content = ''.join(lines)
            for num in HARDCODED_NUMBERS:
                if re.search(rf'\b{num}\b', content):
                    problems.append(f"{rel}: найдено число {num} (возможный хардкод размера)")

# 3. Проверка структуры EditorToolbarStrip
strip_path = os.path.join(SCREENS_DIR, 'ui', 'editor_toolbar_strip.py')
if os.path.exists(strip_path):
    with open(strip_path, 'r', encoding='utf-8') as f:
        content = f.read()
        sep_count = content.count('ToolbarSeparator()')
        if sep_count < 2:
            problems.append("editor_toolbar_strip.py: найдено менее двух ToolbarSeparator()")
else:
    problems.append("editor_toolbar_strip.py: файл не найден")

# 4. Проверка отсутствия setFixedWidth у ThicknessWidget и ColorPaletteWidget
for widget_name in ['thickness.py', 'color_palette.py']:
    widget_path = os.path.join(SCREENS_DIR, 'widgets', widget_name)
    if os.path.exists(widget_path):
        with open(widget_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'setFixedWidth' in content:
                problems.append(f"{widget_name}: найдено setFixedWidth в классе виджета")
    else:
        problems.append(f"{widget_name}: файл не найден")

if problems:
    print("Найдены потенциальные нарушения UI-консистентности:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
else:
    print("Нарушений не обнаружено.")