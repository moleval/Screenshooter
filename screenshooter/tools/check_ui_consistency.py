# tools/check_ui_consistency.py
"""
Простой статический анализ UI-кода:
- ищет setStyleSheet с HEX-цветами вне theme.py
- ищет хардкод размеров (59, 32, 360) вне layout_metrics.py
Запуск:
    python tools/check_ui_consistency.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENS_DIR = os.path.join(ROOT, 'screenshooter')

problems = []

# Проверка HEX-цветов в setStyleSheet
for dirpath, _, filenames in os.walk(SCREENS_DIR):
    if 'theme.py' in filenames:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, ROOT)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'setStyleSheet' in content:
                # Ищем "#XXXXXX"
                if re.search(r'#[0-9a-fA-F]{6}', content):
                    problems.append(f"{rel}: обнаружены HEX-цвета в setStyleSheet")

# Проверка хардкода размеров
hardcoded_numbers = [59, 32, 360]
for dirpath, _, filenames in os.walk(SCREENS_DIR):
    if 'layout_metrics.py' in filenames:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, ROOT)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            for num in hardcoded_numbers:
                if re.search(rf'\b{num}\b', content):
                    problems.append(f"{rel}: найдено число {num} (возможный хардкод размера)")

if problems:
    print("Найдены потенциальные нарушения UI-консистентности:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
else:
    print("Нарушений не обнаружено.")