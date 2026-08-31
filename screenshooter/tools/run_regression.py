"""
Скрипт комплексного регрессионного прогона.
Запускает:
  1. pytest
  2. diagnose_geometry.py
  3. check_ui_consistency.py
Использование: python screenshooter/tools/run_regression.py
"""

import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_command(cmd, description):
    print(f"\n=== {description} ===")
    result = subprocess.run(cmd, cwd=ROOT, shell=True)
    if result.returncode != 0:
        print(f"ОШИБКА: {description} завершилась с кодом {result.returncode}")
        sys.exit(result.returncode)

def main():
    # 1. pytest
    run_command("python -m pytest -v", "Автоматические тесты (pytest)")

    # 2. diagnose_geometry
    run_command("python diagnose_geometry.py", "Диагностика геометрии")

    # 3. check_ui_consistency
    run_command("python screenshooter/tools/check_ui_consistency.py", "Статический анализ UI")

    print("\nВсе проверки пройдены успешно.")

if __name__ == "__main__":
    main()