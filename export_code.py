import os
import fnmatch
from pathlib import Path

# --- НАСТРОЙКИ ---
PROJECT_ROOT = Path('.')
OUTPUT_DIR = Path('export')

# Папки, которые полностью игнорируем
IGNORE_DIRS = [
    'venv', '__pycache__', '.git', '.vscode',
    'dist', 'build', 'export', 'logs', 'temp'
]

# Расширения / паттерны файлов, которые игнорируем
IGNORE_PATTERNS = [
    '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe',
    '*.pyd', '*.spec', '*.log', '*.db', '*.sqlite3'
]

# Расширения, которые считаем текстовыми (чтобы читать)
TEXT_EXTENSIONS = {'.py', '.txt', '.md', '.json', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.gitignore'}
# --- КОНЕЦ НАСТРОЕК ---

def is_ignored(path):
    """Проверяет, нужно ли игнорировать файл или папку."""
    # Проверяем, не входит ли путь в IGNORE_DIRS (или его часть)
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    # Проверяем расширение / паттерн
    for pattern in IGNORE_PATTERNS:
        if fnmatch.fnmatch(path.name, pattern):
            return True
    return False

def read_file_content(filepath):
    """Читает текстовый файл с автоопределением кодировки."""
    encodings = ['utf-8', 'cp1251', 'latin-1']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            return f"[Ошибка чтения: {e}]"
    return f"[Не удалось декодировать файл {filepath}]"

def collect_files():
    """Собирает все подходящие файлы, группируя их по родительской папке."""
    groups = {}  # ключ: имя группы (например, 'root', 'core', 'capture')
    all_files = []

    # Обходим все файлы в проекте
    for root, dirs, files in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        
        # Удаляем из обхода игнорируемые папки (чтобы не заходить в них)
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            file_path = root_path / file
            rel_path = file_path.relative_to(PROJECT_ROOT)
            
            if is_ignored(file_path):
                continue
            
            # Пропускаем бинарные файлы (не текстовые), но можно читать любые текстовые
            # Если расширение не в TEXT_EXTENSIONS, но это важный файл (например, .gitignore) — читаем,
            # иначе пропускаем, если размер большой или расширение бинарное.
            if file_path.suffix not in TEXT_EXTENSIONS:
                # Пропускаем неизвестные расширения, кроме отдельных служебных файлов
                if file_path.name not in ['.gitignore', '.dockerignore', 'Dockerfile']:
                    continue
            
            all_files.append(rel_path)
    
    # Группируем собранные файлы
    for rel_path in all_files:
        parent = rel_path.parent
        # Если файл лежит в корневой папке проекта
        if parent == Path('.'):
            group_key = '00_root'
        # Если файл лежит непосредственно в папке screenshooter/ (но не в подпапках)
        elif parent == Path('screenshooter'):
            group_key = '01_core'
        # Если файл лежит внутри screenshooter/подпапка/
        elif parent.parts[0] == 'screenshooter' and len(parent.parts) == 2:
            # Имя подпапки, например 'capture'
            subfolder_name = parent.parts[1]
            group_key = f'02_{subfolder_name}'
        else:
            # На всякий случай для других структур (например, корневые папки)
            group_key = f'99_{parent.parts[0]}'
        
        groups.setdefault(group_key, []).append(rel_path)
    
    # Сортируем группы и файлы внутри каждой группы
    sorted_groups = {}
    for key in sorted(groups.keys()):
        sorted_groups[key] = sorted(groups[key])
    
    return sorted_groups

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    groups = collect_files()
    
    if not groups:
        print("Не найдено ни одного файла для экспорта. Проверьте структуру.")
        return
    
    # Сохраняем каждую группу в отдельный файл
    for group_key, files in groups.items():
        # Имя файла: например, 00_root.txt или 02_capture.txt
        safe_name = group_key.replace(' ', '_').replace('/', '_')
        output_path = OUTPUT_DIR / f"{safe_name}.txt"
        
        with open(output_path, 'w', encoding='utf-8') as out:
            out.write(f"# ГРУППА: {group_key}\n")
            out.write(f"# Количество файлов: {len(files)}\n\n")
            
            for rel_path in files:
                full_path = PROJECT_ROOT / rel_path
                out.write(f"# --- Файл: {rel_path} ---\n")
                content = read_file_content(full_path)
                out.write(content)
                out.write('\n\n')
        
        print(f"Создан: {output_path}")
    
    print("\nГотово! Файлы лежат в папке 'export/'.")

if __name__ == '__main__':
    main()